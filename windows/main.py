#!/usr/bin/env python3

# Copyright 2021-2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
import asyncio
import sys
import threading
import subprocess
import queue
from pathlib import Path
import logging
import sounddevice as sd

# color logging similar to proximity_keys
from colorama import Fore, Style, init as colorama_init
colorama_init(autoreset=True)

handler = logging.StreamHandler()
class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: Fore.BLUE,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }
    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        prefix = f"{color}[{record.levelname}:{record.name}]{Style.RESET_ALL}"
        return f"{prefix} {record.getMessage()}"
handler.setFormatter(ColorFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("a2dp_source_main")

from bumble.a2dp import (
    A2DP_SBC_CODEC_TYPE,
    SbcMediaCodecInformation,
    SbcPacketSource,
    make_audio_source_service_sdp_records,
)
from bumble.avdtp import (
    AVDTP_AUDIO_MEDIA_TYPE,
    Listener,
    MediaCodecCapabilities,
    MediaPacketPump,
    Protocol,
    find_avdtp_service_with_connection,
)
from bumble.colors import color
from bumble.core import PhysicalTransport
from bumble.device import Device
from bumble.transport import open_transport

# Use JsonKeyStore from bumble.keystore
from bumble.keys import JsonKeyStore
# Pairing pieces from proximity_keys
from bumble.host import Host
from bumble.pairing import PairingConfig, PairingDelegate


# -----------------------------------------------------------------------------
# New main that merges persistent keystore, proximity/connect logic and PCM->SBC streaming
# -----------------------------------------------------------------------------

# SDP & codec helper functions (kept minimal, adapted from the example)
def sdp_records():
    service_record_handle = 0x00010001
    return {service_record_handle: make_audio_source_service_sdp_records(service_record_handle)}


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

# PCM -> SBC via ffmpeg:
# Requires ffmpeg installed and an SBC encoder available (ffmpeg -codecs | findstr sbc).
# Use explicit pipe:0 / pipe:1 on Windows and request SBC codec + SBC raw format.
FFMPEG_CMD = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel",
    "warning",
    "-f",
    "s16le",   # input raw PCM format
    "-ar",
    "48000",
    "-ac",
    "2",
    "-i",
    "pipe:0",   # read PCM from stdin (pipe:0)
    "-c:a",
    "sbc",      # encoder; ensure ffmpeg build has sbc encoder
    "-f",
    "sbc",      # output raw SBC frames
    "pipe:1",   # write SBC to stdout (pipe:1)
]

# Audio capture settings (match ffmpeg input)
SAMPLERATE = 48000
CHANNELS = 2
DTYPE = "int16"
BLOCKSIZE = 1024

def find_vb_cable_device():
    for i, dev in enumerate(sd.query_devices()):
        if "CABLE Output" in dev["name"]:
            return i
    return None

# add helper to avoid hanging on discover_remote_endpoints
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
    # log endpoint codec info for debugging
    for ep in endpoints:
        try:
            logger.info("endpoint: seid=%s, direction=%s, codec=%s", getattr(ep, "seid", None), getattr(ep, "direction", None), getattr(ep, "codec", None))
        except Exception:
            logger.debug("endpoint detail error for: %s", ep)
    return endpoints

async def stream_pcm_to_avdtp(read_function, protocol):
    # Discover endpoints (with timeout to avoid hanging)
    endpoints = await discover_remote_endpoints_with_timeout(protocol, timeout=5.0)
    logger.info("Remote endpoints discovered: %s", endpoints)
    for endpoint in endpoints:
        logger.debug("endpoint: %s", endpoint)

    sink = protocol.find_remote_sink_by_codec(AVDTP_AUDIO_MEDIA_TYPE, A2DP_SBC_CODEC_TYPE)
    if sink is None:
        print("!!! no SBC sink found")
        return

    print(f"### Selected sink: {sink.seid}")

    logger.info("Selected sink SEID=%s; peer_mtu=%s", sink.seid, getattr(protocol.l2cap_channel, "peer_mtu", None))

    # wrap read_function to add logging for read requests/returns
    def make_logged_read(fn):
        async def logged_read(n):
            logger.debug("SBC read request for %d bytes", n)
            data = await fn(n)
            logger.debug("SBC read returned %d bytes", len(data) if data else 0)
            return data
        return logged_read

    packet_source = SbcPacketSource(make_logged_read(read_function), protocol.l2cap_channel.peer_mtu)
    packet_pump = MediaPacketPump(packet_source.packets)
    source = protocol.add_source(codec_capabilities(), packet_pump)
    stream = await protocol.create_stream(source, sink)
    await stream.start()
    print("Streaming... press Ctrl-C to stop")
    try:
        # just run until cancelled
        while True:
            await asyncio.sleep(1)
    finally:
        print("Stopping A2DP stream...")
        await stream.stop()
        await stream.close()

def start_ffmpeg_process():
    # Use blocking Popen with pipes; we'll write PCM to stdin and read SBC from stdout.
    logger.info("Starting ffmpeg: %s", " ".join(FFMPEG_CMD))
    proc = subprocess.Popen(
        FFMPEG_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    logger.debug("ffmpeg pid=%s", getattr(proc, "pid", None))
    return proc

def start_sounddevice_writer(proc, stop_event):
    # proc is subprocess.Popen; we'll write to proc.stdin and monitor proc.poll()
    q = queue.Queue(maxsize=64)
    dropped_count = 0
    written_bytes = 0
    dev_name = None

    def callback(indata, frames, time, status):
        if status:
            logger.warning("Audio status: %s", status)
        try:
            q.put_nowait(indata.tobytes())
        except queue.Full:
            # drop if ffmpeg can't keep up
            nonlocal dropped_count
            dropped_count += 1
            if dropped_count % 50 == 0:
                logger.warning("Dropped audio chunks: %d", dropped_count)
            return

    device = find_vb_cable_device()
    if device is None:
        raise RuntimeError("VB-Audio CABLE Output not found; select it as the input device")
    try:
        dev_name = sd.query_devices()[device]["name"]
    except Exception:
        dev_name = f"index {device}"
    logger.info("Using input device %s (index=%s)", dev_name, device)

    def writer_thread():
        try:
            with sd.InputStream(
                samplerate=SAMPLERATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCKSIZE,
                callback=callback,
                device=device,
            ):
                while not stop_event.is_set():
                    try:
                        chunk = q.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    # don't attempt writes if ffmpeg exited
                    if proc.poll() is not None:
                        logger.error("ffmpeg exited with returncode=%s; stopping audio writer", proc.returncode)
                        stop_event.set()
                        break
                    try:
                        proc.stdin.write(chunk)
                        proc.stdin.flush()
                        written_bytes_local = len(chunk)
                        nonlocal written_bytes
                        written_bytes += written_bytes_local
                        if written_bytes % (SAMPLERATE * CHANNELS * 2 * 1) < written_bytes_local:
                            # log roughly once per second of audio written
                            logger.debug("Wrote ~1s of PCM to ffmpeg (total bytes=%d)", written_bytes)
                    except (BrokenPipeError, OSError) as e:
                        logger.error("Error writing to ffmpeg stdin: %s", e)
                        stop_event.set()
                        break
        finally:
            try:
                if proc.stdin:
                    proc.stdin.flush()
            except Exception:
                pass
            try:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
            except Exception:
                pass
            logger.info("Audio writer exiting (written_bytes=%d, dropped=%d)", written_bytes, dropped_count)

    t = threading.Thread(target=writer_thread, daemon=True)
    t.start()
    return t

def ffmpeg_stdout_reader(proc_stdout, read_q, stop_event):
    # Read raw SBC frames from ffmpeg stdout and push to a queue.
    # We don't know SBC frame boundaries reliably; read in chunks and let SbcPacketSource consume bytes.
    total = 0
    try:
        while not stop_event.is_set():
            data = proc_stdout.read(4096)
            if not data:
                break
            total += len(data)
            read_q.put(data)
            if total % (1024 * 50) < len(data):
                logger.debug("ffmpeg -> stdout: total %d bytes read", total)
    finally:
        logger.info("ffmpeg stdout reader exiting (total_bytes=%d)", total)
        stop_event.set()

def ffmpeg_stderr_reader(proc_stderr, stop_event):
    try:
        while not stop_event.is_set():
            line = proc_stderr.readline()
            if not line:
                break
            try:
                logger.warning("ffmpeg: %s", line.decode(errors="ignore").rstrip())
            except Exception:
                logger.warning("ffmpeg (raw): %s", line)
    finally:
        logger.info("ffmpeg stderr reader exiting")
        stop_event.set()

def make_sync_read_from_queue(read_q, stop_event):
    # returns an async function read(byte_count) -> bytes (awaitable, offloads blocking queue ops)
    buffer = bytearray()

    def sync_read(byte_count):
        nonlocal buffer
        while len(buffer) < byte_count and not stop_event.is_set():
            try:
                chunk = read_q.get(timeout=0.1)
            except queue.Empty:
                continue
            buffer.extend(chunk)
        if not buffer:
            logger.debug("make_sync_read_from_queue: EOF/empty read for %d bytes", byte_count)
            return b""
        out = bytes(buffer[:byte_count])
        buffer[:] = buffer[byte_count:]
        logger.debug("make_sync_read_from_queue: returning %d bytes (requested %d)", len(out), byte_count)
        return out

    async def read(byte_count):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_read, byte_count)

    return read

async def main():
    # Usage: main.py [<transport-spec>] [<bdaddr>]
    # default transport -> "usb:0"
    transport_spec = "usb:0"
    target_bdaddr = None
    if len(sys.argv) >= 2:
        transport_spec = sys.argv[1]
    if len(sys.argv) >= 3:
        target_bdaddr = sys.argv[2]

    logger.info("Using transport: %s", transport_spec)
    logger.info("<<< connecting to HCI...")

    async with await open_transport(transport_spec) as hci_transport:
        logger.info("<<< connected")

        # Create Device using Host like proximity_keys so no config file is required.
        host = Host(controller_source=hci_transport.source, controller_sink=hci_transport.sink)
        device = Device(host=host)
        device.classic_enabled = True

        # Persist keys using JsonKeyStore
        keys_path = Path.home() / ".config" / "bumble" / "keys.json"
        keys_path.parent.mkdir(parents=True, exist_ok=True)
        device.keystore = JsonKeyStore.from_device(device, str(keys_path))

        # Pairing config so we do Secure Connections + bonding like proximity_keys example.
        device.pairing_config_factory = lambda conn: PairingConfig(
            sc=True,
            mitm=False,
            bonding=True,
            delegate=PairingDelegate(io_capability=PairingDelegate.NO_OUTPUT_NO_INPUT),
        )

        # Expose A2DP SRC SDP
        device.sdp_service_records = sdp_records()

        await device.power_on()
        logger.info("Device powered on")

        # Connect or listen
        if target_bdaddr:
            logger.info("=== Connecting to %s...", target_bdaddr)
            conn = await device.connect(target_bdaddr, transport=PhysicalTransport.BR_EDR)
            # give the controller/remote a short moment to settle after connect
            await asyncio.sleep(0.1)
            logger.info("=== Connected to %s!", conn.peer_address)
            logger.info("*** Authenticating...")
            await conn.authenticate()
            # small pause after authenticate so link state updates propagate
            await asyncio.sleep(0.05)
            logger.info("*** Authenticated")
            if not conn.is_encrypted:
                logger.info("*** Enabling encryption...")
                await conn.encrypt()
                # pause after enabling encryption
                await asyncio.sleep(0.05)
                logger.info("*** Encryption on")

            avdtp_version = await find_avdtp_service_with_connection(conn)
            # allow a short delay for SDP/AVDTP service discovery to stabilize
            await asyncio.sleep(0.05)
            if not avdtp_version:
                logger.error("!!! no A2DP service found")
                return

            protocol = await Protocol.connect(conn, avdtp_version)
            # small pause after creating protocol connection
            await asyncio.sleep(0.05)

            # Start ffmpeg and audio capture, wire stdout into SbcPacketSource
            proc = start_ffmpeg_process()
            stop_event = threading.Event()
            read_q = queue.Queue()
            stdout_thread = threading.Thread(target=ffmpeg_stdout_reader, args=(proc.stdout, read_q, stop_event), daemon=True)
            stdout_thread.start()
            stderr_thread = threading.Thread(target=ffmpeg_stderr_reader, args=(proc.stderr, stop_event), daemon=True)
            stderr_thread.start()
            writer_thread = start_sounddevice_writer(proc, stop_event)
            read_func = make_sync_read_from_queue(read_q, stop_event)

            try:
                await stream_pcm_to_avdtp(read_func, protocol)
            except asyncio.CancelledError:
                pass
            finally:
                stop_event.set()
                try:
                    proc.kill()
                except Exception:
                    pass
                await asyncio.sleep(0.1)
        else:
            # act as listener (server) — waiting for remote to connect and then we attach the ffmpeg pipeline
            listener = Listener.for_device(device=device, version=(1, 2))

            async def on_connection(protocol):
                logger.info("Incoming AVDTP connection")
                # give a short moment before starting the capture/encoder pipeline
                await asyncio.sleep(0.05)
                proc = start_ffmpeg_process()
                stop_event = threading.Event()
                read_q = queue.Queue()
                stdout_thread = threading.Thread(target=ffmpeg_stdout_reader, args=(proc.stdout, read_q, stop_event), daemon=True)
                stdout_thread.start()
                stderr_thread = threading.Thread(target=ffmpeg_stderr_reader, args=(proc.stderr, stop_event), daemon=True)
                stderr_thread.start()
                writer_thread = start_sounddevice_writer(proc, stop_event)
                read_func = make_sync_read_from_queue(read_q, stop_event)

                try:
                    await stream_pcm_to_avdtp(read_func, protocol)
                finally:
                    stop_event.set()
                    try:
                        proc.kill()
                    except Exception:
                        pass

            listener.on("connection", lambda protocol: asyncio.create_task(on_connection(protocol)))
            await device.set_discoverable(True)
            await device.set_connectable(True)
            logger.info("Waiting for incoming connections...")

        # Wait until transport terminates (or user interrupts)
        try:
            await hci_transport.source.wait_for_termination()
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted, exiting.")