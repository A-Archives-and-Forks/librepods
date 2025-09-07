import asyncio
import sys
import threading
import subprocess
import queue
import math
import struct
from pathlib import Path
import logging
import os

from bumble.avdtp import Listener

from bumble.a2dp import (
    A2DP_SBC_CODEC_TYPE,
    SbcMediaCodecInformation,
    SbcPacketSource,
    make_audio_source_service_sdp_records,
)
from bumble.avdtp import (
    AVDTP_AUDIO_MEDIA_TYPE,
    MediaCodecCapabilities,
    MediaPacketPump,
    Protocol,
    find_avdtp_service_with_connection,
)
from bumble.core import PhysicalTransport
from bumble.transport import open_transport
from bumble.host import Host
from bumble.device import Device
from bumble.keys import JsonKeyStore
from bumble.pairing import PairingConfig, PairingDelegate

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("stream_tone")

# ffmpeg: read PCM from pipe:0 and write SBC to pipe:1
FFMPEG_CMD = [
    "ffmpeg",
    "-hide_banner", "-loglevel", "warning",
    "-f", "s16le", "-ar", "44100", "-ac", "2",    # changed 48000 -> 44100
    "-i", "pipe:0",
    "-c:a", "sbc", "-f", "sbc", "pipe:1",
]

SAMPLERATE = 44100   # changed 48000 -> 44100
CHANNELS = 2
DTYPE_BYTES = 2  # int16

def sdp_records():
    handle = 0x00010001
    return {handle: make_audio_source_service_sdp_records(handle)}

def codec_capabilities():
    return MediaCodecCapabilities(
        media_type=AVDTP_AUDIO_MEDIA_TYPE,
        media_codec_type=A2DP_SBC_CODEC_TYPE,
        media_codec_information=SbcMediaCodecInformation(
            sampling_frequency=SbcMediaCodecInformation.SamplingFrequency.SF_44100,
            channel_mode=SbcMediaCodecInformation.ChannelMode.JOINT_STEREO,
            block_length=SbcMediaCodecInformation.BlockLength.BL_16,
            subbands=SbcMediaCodecInformation.Subbands.S_8,
            allocation_method=SbcMediaCodecInformation.AllocationMethod.LOUDNESS,
            minimum_bitpool_value=2,
            maximum_bitpool_value=53,
        ),
    )

def start_ffmpeg_and_feed_pcm(duration_seconds: float, freq_hz: float = 440.0):
    """Start ffmpeg process and return the Popen object.
    PCM feeding is performed by feed_pcm_to_proc() after reader threads are running.
    """
    logger.info("Starting ffmpeg: %s", " ".join(FFMPEG_CMD))
    proc = subprocess.Popen(FFMPEG_CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    return proc

def feed_pcm_to_proc(proc: subprocess.Popen, duration_seconds: float, freq_hz: float = 440.0, chunk_frames: int = 1024):
    """Write generated PCM to proc.stdin from a background thread in chunks."""
    def feeder():
        try:
            frames = int(SAMPLERATE * duration_seconds)
            total_bytes = 0
            # write in chunks to avoid blocking main thread and make readers likely to be active
            i = 0
            while i < frames:
                end = min(i + chunk_frames, frames)
                pcm = bytearray()
                for j in range(i, end):
                    s = int(0.5 * 32767.0 * math.sin(2 * math.pi * freq_hz * (j / SAMPLERATE)))
                    pcm.extend(struct.pack("<h", s))
                    pcm.extend(struct.pack("<h", s))
                try:
                    proc.stdin.write(pcm)
                    proc.stdin.flush()
                    total_bytes += len(pcm)
                except Exception as e:
                    logger.error("Feeder failed writing to ffmpeg stdin: %s", e)
                    break
                i = end
            try:
                proc.stdin.close()
            except Exception:
                pass
            logger.info("Feeder exiting, wrote %d PCM bytes", total_bytes)
        except Exception as e:
            logger.exception("Feeder thread exception: %s", e)
    t = threading.Thread(target=feeder, daemon=True)
    t.start()
    return t

def ffmpeg_stdout_reader(proc_stdout, q: queue.Queue, stop_event: threading.Event):
    total = 0
    # dump file for offline inspection (pid in name to avoid clobbering concurrent runs)
    dump_path = Path(f"/tmp/ffmpeg_sbc_dump_{os.getpid()}.sbc")
    try:
        dump_f = dump_path.open("wb")
    except Exception as e:
        dump_f = None
        logger.warning("Could not open SBC dump file %s: %s", dump_path, e)
    try:
        logger.info("ffmpeg stdout reader dumping to %s", dump_path)
        while not stop_event.is_set():
            data = proc_stdout.read(4096)
            if not data:
                break
            total += len(data)
            q.put(data)
            # write to dump file for offline analysis
            if dump_f:
                try:
                    dump_f.write(data)
                    dump_f.flush()
                except Exception:
                    logger.exception("Failed writing to dump file")
            logger.info("ffmpeg stdout read %d bytes (total %d)", len(data), total)
    finally:
        logger.info("ffmpeg stdout reader exiting (total_bytes=%d)", total)
        if dump_f:
            try:
                dump_f.close()
                logger.info("ffmpeg stdout dumped to %s (%d bytes)", dump_path, total)
            except Exception:
                pass
        stop_event.set()

def ffmpeg_stderr_reader(proc_stderr, stop_event: threading.Event):
    try:
        while not stop_event.is_set():
            line = proc_stderr.readline()
            if not line:
                break
            logger.warning("ffmpeg: %s", line.decode(errors="ignore").rstrip())
    finally:
        logger.info("ffmpeg stderr reader exiting")
        stop_event.set()

def make_async_read_from_queue(read_q: queue.Queue, stop_event: threading.Event):
    buffer = bytearray()
    def sync_read(n):
        nonlocal buffer
        # keep attempting to fill buffer until we have enough bytes,
        # but if the producer has stopped (stop_event) and the queue
        # is empty, give up and return whatever we've got.
        while len(buffer) < n:
            try:
                chunk = read_q.get(timeout=0.1)
            except queue.Empty:
                # if producer finished and there's nothing left to read, break
                if stop_event.is_set() and read_q.empty():
                    break
                # otherwise keep waiting for data
                continue
            if chunk:
                buffer.extend(chunk)
        if not buffer:
            return b""
        out = bytes(buffer[:n])
        buffer[:] = buffer[n:]
        return out
    async def read(n):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_read, n)
    return read

def make_logged_async_read(read_fn):
    async def logged_read(n):
        logger.info("SBC read request for %d bytes", n)
        data = await read_fn(n)
        logger.info("SBC read returned %d bytes", len(data) if data else 0)
        return data
    return logged_read

# helper to avoid hanging on discover_remote_endpoints
async def discover_remote_endpoints_with_timeout(protocol, timeout=5.0):
    try:
        endpoints = await asyncio.wait_for(protocol.discover_remote_endpoints(), timeout=timeout)
        logger.info("discover_remote_endpoints: found %d endpoint(s)", len(endpoints))
    except asyncio.TimeoutError:
        logger.error("discover_remote_endpoints timed out after %.1fs", timeout)
        endpoints = getattr(protocol, "remote_endpoints", []) or []
        logger.info("Falling back to protocol.remote_endpoints: %d", len(endpoints))
    except Exception as e:
        logger.exception("discover_remote_endpoints failed: %s", e)
        endpoints = []
    for ep in endpoints:
        try:
            logger.info("endpoint: seid=%s, direction=%s, codec=%s", getattr(ep, "seid", None), getattr(ep, "direction", None), getattr(ep, "codec", None))
        except Exception:
            logger.debug("endpoint detail error for: %s", ep)
    return endpoints

async def stream_to_bdaddr(protocol: Protocol, read_func):
    # find SBC sink (discover with timeout)
    logger.info("Discovering remote endpoints...")
    endpoints = await discover_remote_endpoints_with_timeout(protocol, timeout=5.0)
    logger.info("Discovered endpoints: %s", endpoints)
    for ep in endpoints:
        logger.info("endpoint: %s", ep)

    sink = protocol.find_remote_sink_by_codec(AVDTP_AUDIO_MEDIA_TYPE, A2DP_SBC_CODEC_TYPE)
    if sink is None:
        logger.error("No SBC sink found")
        return
    logger.info("Selected sink SEID=%s; peer_mtu=%s", sink.seid, getattr(protocol.l2cap_channel, "peer_mtu", None))
    # wrap read_func with logging and pass to SbcPacketSource
    packet_source = SbcPacketSource(make_logged_async_read(read_func), protocol.l2cap_channel.peer_mtu)
    packet_pump = MediaPacketPump(packet_source.packets)
    source = protocol.add_source(codec_capabilities(), packet_pump)
    stream = await protocol.create_stream(source, sink)
    await stream.start()
    logger.info("Streaming tone...")
    # wait until read source indicates EOF (ffmpeg stop_event)
    try:
        while True:
            await asyncio.sleep(0.1)
            # SbcPacketSource will read until EOF, we detect if read_func yields empty by checking task cancellations externally
            # We'll just let ffmpeg reader set stop_event and exit when that happens (handled by main)
            pass
    finally:
        logger.info("Stopping stream...")
        await stream.stop()
        await stream.close()

async def main():
    # Usage:
    #   stream_tone.py <bdaddr> [<transport-spec>]     -> client mode (connect to BDADDR)
    #   stream_tone.py           [<transport-spec>]     -> listener mode (accept incoming AVDTP)
    bdaddr = sys.argv[1] if len(sys.argv) >= 2 else None
    transport_spec = sys.argv[2] if len(sys.argv) > 2 else "usb:0"

    logger.info("Using transport: %s", transport_spec)
    # Defer starting ffmpeg until after AVDTP protocol is connected
    proc = None
    stop_event = None
    read_q = None
    read_func = None

    # Connect HCI and A2DP similar to main.py
    async with await open_transport(transport_spec) as hci_transport:
        host = Host(controller_source=hci_transport.source, controller_sink=hci_transport.sink)
        device = Device(host=host)
        device.classic_enabled = True
        keys_path = Path.home() / ".config" / "bumble" / "keys.json"
        keys_path.parent.mkdir(parents=True, exist_ok=True)
        device.keystore = JsonKeyStore.from_device(device, str(keys_path))
        device.pairing_config_factory = lambda conn: PairingConfig(
            sc=True, mitm=False, bonding=True,
            delegate=PairingDelegate(io_capability=PairingDelegate.NO_OUTPUT_NO_INPUT),
        )
        device.sdp_service_records = sdp_records()
        await device.power_on()
        logger.info("Device powered on, connecting to %s", bdaddr if bdaddr else "LISTEN")

        # If no bdaddr provided, act as listener (copying example behavior).
        if not bdaddr:
            listener = Listener.for_device(device=device, version=(1, 2))

            async def on_connection(protocol):
                logger.info("Incoming AVDTP connection (listener mode)")
                # small settle delay as in example
                await asyncio.sleep(0.05)
                # start ffmpeg pipeline for this incoming connection
                proc_local = start_ffmpeg_and_feed_pcm(duration_seconds=30.0, freq_hz=440.0)
                stop_event_local = threading.Event()
                read_q_local = queue.Queue()
                t_out_local = threading.Thread(target=ffmpeg_stdout_reader, args=(proc_local.stdout, read_q_local, stop_event_local), daemon=True)
                t_err_local = threading.Thread(target=ffmpeg_stderr_reader, args=(proc_local.stderr, stop_event_local), daemon=True)
                t_out_local.start()
                t_err_local.start()
                # start feeding PCM after readers are active
                feed_thread_local = feed_pcm_to_proc(proc_local, duration_seconds=30.0, freq_hz=440.0)
                read_func_local = make_async_read_from_queue(read_q_local, stop_event_local)

                try:
                    await stream_to_bdaddr(protocol, read_func_local)
                finally:
                    stop_event_local.set()
                    try:
                        proc_local.kill()
                    except Exception:
                        pass

            listener.on("connection", lambda protocol: asyncio.create_task(on_connection(protocol)))
            await device.set_discoverable(True)
            await device.set_connectable(True)
            logger.info("Listener active, waiting for incoming AVDTP connections...")
            # wait until transport terminates (or user interrupts)
            await hci_transport.source.wait_for_termination()
            # cleanup and return
            if stop_event:
                stop_event.set()
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            return

        # client-mode connect to bdaddr
        conn = await device.connect(bdaddr, transport=PhysicalTransport.BR_EDR)
        # allow the link to settle after connect
        await asyncio.sleep(0.1)
        logger.info("Connected to %s", conn.peer_address)
        await conn.authenticate()
        # small pause after authenticate
        await asyncio.sleep(0.05)
        if not conn.is_encrypted:
            await conn.encrypt()
            # small pause after enabling encryption
            await asyncio.sleep(0.05)
        logger.info("Connection encrypted=%s", conn.is_encrypted)
        avdtp_version = await find_avdtp_service_with_connection(conn)
        # brief delay so service discovery stabilizes
        await asyncio.sleep(0.05)
        if not avdtp_version:
            logger.error("No A2DP service on remote")
            if stop_event:
                stop_event.set()
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            return
        logger.info("Remote AVDTP version: %d.%d", avdtp_version[0], avdtp_version[1])
        protocol = await Protocol.connect(conn, avdtp_version)
        logger.info("AVDTP protocol connected")
        # allow protocol to settle
        await asyncio.sleep(0.05)

        # Now start ffmpeg/readers/feeder since the protocol is ready:
        proc = start_ffmpeg_and_feed_pcm(duration_seconds=30.0, freq_hz=440.0)
        stop_event = threading.Event()
        read_q = queue.Queue()
        t_out = threading.Thread(target=ffmpeg_stdout_reader, args=(proc.stdout, read_q, stop_event), daemon=True)
        t_err = threading.Thread(target=ffmpeg_stderr_reader, args=(proc.stderr, stop_event), daemon=True)
        t_out.start()
        t_err.start()
        feed_thread = feed_pcm_to_proc(proc, duration_seconds=30.0, freq_hz=440.0)
        read_func = make_async_read_from_queue(read_q, stop_event)

        # Start streaming task (moved inside the open_transport context so the
        # transport/protocol remain valid during discovery/streaming)
        logger.info("Starting streaming task")
        
        await stream_to_bdaddr(protocol, read_func)
        # give a little time for the stream to start
        await asyncio.sleep(0.05)

        # Wait for ffmpeg to finish producing SBC (stop_event), then cleanup
        while not (stop_event and stop_event.is_set()):
            await asyncio.sleep(0.1)

        if proc:
            try:
                proc.kill()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted")
