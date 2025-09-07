#!/usr/bin/env python3

# Needs https://github.com/google/bumble on Windows
# See https://github.com/google/bumble/blob/main/docs/mkdocs/src/platforms/windows.md for usage.
# You need to associate WinUSB with your Bluetooth interface. Once done, you can roll back to the original driver from Device Manager.

import asyncio
import argparse
import logging

from colorama import Fore, Style, init as colorama_init
from glm import log
colorama_init(autoreset=True)

import os, sys

sys.path.insert(0, os.path.dirname(__file__))
import channel_extensions
from channel_extensions import _make_reader

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

logger = logging.getLogger("main")

async def run_bumble(bdaddr: str):
    try:
        from bumble.l2cap import ClassicChannelSpec, ClassicChannel
        from bumble.transport import open_transport
        from bumble.device import Device, Connection
        from bumble.host import Host
        from bumble.core import PhysicalTransport
        from bumble.pairing import PairingConfig, PairingDelegate
        from bumble.hci import HCI_Error
        from bumble.keys import JsonKeyStore
        from records import SDP_SERVICE_RECORDS
        from bumble.avdtp import Listener as AvdtpListener, MediaCodecCapabilities, AVDTP_AUDIO_MEDIA_TYPE, Protocol as AvdtpProtocol, MediaPacketPump, MediaCodecCapabilities
        from bumble.a2dp import SbcMediaCodecInformation, A2DP_SBC_CODEC_TYPE, SbcPacketSource, A2DP_MPEG_2_4_AAC_CODEC_TYPE, AacMediaCodecInformation, AacPacketSource
        from bumble.avrcp import Protocol as AvrcpProtol, Delegate as AvrcpDelegate, EventId as AvrcpEventId

    except ImportError:
        logger.error("Bumble not installed")
        return 1
    
    async def get_device():
        logger.info("Opening transport...")
        transport = await open_transport("usb:0")
        device = Device(host=Host(controller_source=transport.source, controller_sink=transport.sink))
        device.classic_enabled = True
        device.le_enabled = False
        device.keystore = JsonKeyStore.from_device(device, "./keys.json")
        device.pairing_config_factory = lambda conn: PairingConfig(
            sc=True, mitm=False, bonding=True,
            delegate=PairingDelegate(io_capability=PairingDelegate.NO_OUTPUT_NO_INPUT)
        )
        await device.power_on()
        logger.info("Device powered on")
        
        def on_l2cap_connection(channel: ClassicChannel):
            logger.info("Incoming L2CAP connection on PSM %d", channel.psm)
            async def handle_data():
                try:
                    reader, restore = _make_reader(channel)
                    while True:
                        data = await reader()
                        print(f"Received PDU on PSM {channel.psm}: {data}")
                    if restore:
                        restore()
                except Exception as e:
                    logger.info("L2CAP channel on PSM %d closed: %s", channel.psm, e)
            asyncio.create_task(handle_data())
        
        server_spec = ClassicChannelSpec(psm=3, mtu=672)
        logger.info("Registering L2CAP server on PSM = %d", server_spec.psm)
        device.create_l2cap_server(server_spec, handler=on_l2cap_connection)
        logger.info("Dummy L2CAP server registered on PSM 3")
        
        aap_client_spec = ClassicChannelSpec(psm=0x1007, mtu=1000)
        logger.info("Registering AAP client on PSM = 0x%04X", aap_client_spec.psm)
        device.create_l2cap_server(aap_client_spec, handler=on_l2cap_connection)
        logger.info("AAP client registered on PSM 0x%04X", aap_client_spec.psm)
        
        device.sdp_service_records = SDP_SERVICE_RECORDS
        logger.info("SDP service records set up")
        
        return transport, device

    async def setup_avdtp_avrcp(conn: Connection):
        avdtp_listener = AvdtpListener.for_device(device=device, version=(1, 2))
        
        def codec_capabilities(codec_type=A2DP_SBC_CODEC_TYPE):
            if codec_type == A2DP_SBC_CODEC_TYPE:
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
            elif codec_type == A2DP_MPEG_2_4_AAC_CODEC_TYPE:
                return MediaCodecCapabilities(
                    media_type=AVDTP_AUDIO_MEDIA_TYPE,
                    media_codec_type=A2DP_MPEG_2_4_AAC_CODEC_TYPE,
                    media_codec_information=AacMediaCodecInformation(
                        object_type=AacMediaCodecInformation.ObjectType.MPEG_2_AAC_LC,
                        sampling_frequency=AacMediaCodecInformation.SamplingFrequency.SF_44100,
                        channels=AacMediaCodecInformation.Channels.STEREO,
                        vbr=True,
                        bitrate=256000,
                    ),
                )
        
        def on_avdtp_connection(protocol: AvdtpProtocol):
            logger.info("Incoming AVDTP connection on PSM 25")
            sbc_capabilities = MediaCodecCapabilities(
                media_type=AVDTP_AUDIO_MEDIA_TYPE,
                media_codec_type=A2DP_SBC_CODEC_TYPE,
                media_codec_information=SbcMediaCodecInformation(
                    sampling_frequency=SbcMediaCodecInformation.SamplingFrequency.SF_44100,
                    channel_mode=SbcMediaCodecInformation.ChannelMode.JOINT_STEREO,
                    block_length=SbcMediaCodecInformation.BlockLength.BL_16,
                    subbands=SbcMediaCodecInformation.Subbands.S_8,
                    allocation_method=SbcMediaCodecInformation.AllocationMethod.SNR,
                    minimum_bitpool_value=2,
                    maximum_bitpool_value=53,
                ),
            )
            sink = protocol.add_sink(sbc_capabilities)
            logger.info(f"Added AVDTP sink endpoint with SEID {sink.seid}")
        
        avdtp_listener.on('connection', on_avdtp_connection)
        
        avrcp_delegate = AvrcpDelegate(
            supported_events=[
                AvrcpEventId.PLAYBACK_STATUS_CHANGED,
                AvrcpEventId.TRACK_CHANGED,
                AvrcpEventId.TRACK_REACHED_END,
                AvrcpEventId.TRACK_REACHED_START,
                AvrcpEventId.PLAYBACK_POS_CHANGED,
                AvrcpEventId.BATT_STATUS_CHANGED,
                AvrcpEventId.SYSTEM_STATUS_CHANGED,
                AvrcpEventId.PLAYER_APPLICATION_SETTING_CHANGED,
                AvrcpEventId.NOW_PLAYING_CONTENT_CHANGED,
                AvrcpEventId.AVAILABLE_PLAYERS_CHANGED,
                AvrcpEventId.ADDRESSED_PLAYER_CHANGED,
                AvrcpEventId.UIDS_CHANGED,
                AvrcpEventId.VOLUME_CHANGED
            ]
        )
        avrcp_protocol = AvrcpProtol(delegate=avrcp_delegate)
        await avrcp_protocol.connect(conn)
        
        async def stream_packets(read_function, protocol: AvdtpProtocol, preferred_codec=A2DP_SBC_CODEC_TYPE):
            endpoints = await protocol.discover_remote_endpoints()
            sink = protocol.find_remote_sink_by_codec(AVDTP_AUDIO_MEDIA_TYPE, preferred_codec)
            if sink is None:
                logger.error(f"No {preferred_codec} sink found")
                return
            media_codec_cap: MediaCodecCapabilities = sink.capabilities[1]
            actual_codec = media_codec_cap.media_codec_type
            if actual_codec == A2DP_MPEG_2_4_AAC_CODEC_TYPE:
                packet_source = AacPacketSource(read_function, protocol.l2cap_channel.peer_mtu)
            else:
                packet_source = SbcPacketSource(read_function, protocol.l2cap_channel.peer_mtu)
            packet_pump = MediaPacketPump(packet_source.packets)
            source = protocol.add_source(codec_capabilities(actual_codec), packet_pump)
            stream = await protocol.create_stream(source, sink)
            await stream.start()
    
    async def setup_aacp(conn: Connection):
        spec = ClassicChannelSpec(psm=4097, mtu=2048)
        logger.info("Requesting L2CAP channel on PSM = 0x%04X", spec.psm)
        if not conn.is_encrypted:
            logger.info("Enabling link encryption...")
            await conn.encrypt()
            await asyncio.sleep(0.05)
        channel: ClassicChannel = await conn.create_l2cap_channel(spec=spec)
        
        logger.info("AAC proxy server listening on /tmp/aacp.sock")
        
        asyncio.create_task(channel.bridge_to_unix_socket("./aacp.sock"))
        logger.info("AAC proxy bridge started in background (socket: /tmp/aacp.sock)")
    
    async def setup_att(conn: Connection):
        spec = ClassicChannelSpec(psm=31, mtu=512)
        logger.info("Requesting L2CAP channel on PSM = 0x%04X", spec.psm)
        if not conn.is_encrypted:
            logger.info("Enabling link encryption...")
            await conn.encrypt()
            await asyncio.sleep(0.05)
        channel: ClassicChannel = await conn.create_l2cap_channel(spec=spec)
        logger.info("ATT server listening on /tmp/att.sock")
        asyncio.create_task(channel.bridge_to_unix_socket("./att.sock"))
        pass
    
    transport, device = await get_device()
    logger.info("Connecting to %s (BR/EDR)...", bdaddr)
    try:
        connection = await device.connect(bdaddr, PhysicalTransport.BR_EDR)
        logger.info("Connected to %s (handle %s)", connection.peer_address, connection.handle)
        logger.info("Authenticating...")
        await connection.authenticate()
        if not connection.is_encrypted:
            logger.info("Encrypting link...")
            await connection.encrypt()
        await setup_aacp(connection)
        await setup_att(connection)
        await setup_avdtp_avrcp(connection)
        logger.info("Bridges started; process will keep running. Press Ctrl-C to exit.")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass
    except HCI_Error as e:
        if "PAIRING_NOT_ALLOWED_ERROR" in str(e):
            logger.error("Put your device into pairing mode and run the script again")
        else:
            logger.error("HCI error: %s", e)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
    finally:
        if hasattr(transport, "close"):
            logger.info("Closing transport...")
            await transport.close()
        logger.info("Transport closed")
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bdaddr")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    logging.getLogger().setLevel(logging.DEBUG if args.debug else logging.INFO)

    asyncio.run(run_bumble(args.bdaddr))

if __name__ == "__main__":
    main()
