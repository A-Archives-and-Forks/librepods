# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------
import asyncio
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("example")

from bumble.a2dp import (
    A2DP_SBC_CODEC_TYPE,
    A2DP_MPEG_2_4_AAC_CODEC_TYPE,
    SbcMediaCodecInformation,
    SbcPacketSource,
    AacMediaCodecInformation,
    make_audio_source_service_sdp_records,
    AacPacketSource
)
from bumble.avrcp import (
    make_controller_service_sdp_records,
    Protocol as AvrcpProtocol,
    avc
)
from bumble.avdtp import (
    AVDTP_AUDIO_MEDIA_TYPE,
    MediaCodecCapabilities,
    MediaPacketPump,
    Protocol,
    find_avdtp_service_with_connection,
)
from bumble.colors import color
from bumble.core import PhysicalTransport
from bumble.device import Device
from bumble.transport import open_transport

# Add JsonKeyStore and Host/pairing imports
from pathlib import Path
from bumble.keys import JsonKeyStore
from bumble.host import Host
from bumble.pairing import PairingConfig, PairingDelegate

# Add imports for HFP and RFCOMM to replicate BlueZ
from bumble.rfcomm import Client as RfcommClient, DLC
from bumble.hfp import (
    make_hf_sdp_records as make_hands_free_service_sdp_records,
    HfProtocol as HandsFreeProtocol,
    HfConfiguration,
    HfFeature,
    AudioCodec,
    HfIndicator
    )

# -----------------------------------------------------------------------------
def sdp_records():
    service_record_handle = 0x00010001
    # Create HFP configuration with basic features
    hfp_config = HfConfiguration(
        supported_hf_features={HfFeature.REMOTE_VOLUME_CONTROL, HfFeature.THREE_WAY_CALLING},
        supported_audio_codecs={AudioCodec.CVSD},
        supported_hf_indicators={
            HfIndicator.BATTERY_LEVEL,
            HfIndicator.ENHANCED_SAFETY
        }
    )
    return {
        service_record_handle: make_audio_source_service_sdp_records(service_record_handle),
        service_record_handle + 1: make_controller_service_sdp_records(service_record_handle + 1),
        service_record_handle + 2: make_hands_free_service_sdp_records(service_record_handle + 2, rfcomm_channel=7, configuration=hfp_config),  # Use channel 7 from SDP browse
    }

# -----------------------------------------------------------------------------
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
                allocation_method=SbcMediaCodecInformation.AllocationMethod.SNR,
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
                vbr=True,  # Match remote's VBR=1
                bitrate=256000,  # Match remote's bitrate
            ),
        )

# -----------------------------------------------------------------------------
def on_avdtp_connection(read_function, protocol):
    packet_source = SbcPacketSource(read_function, protocol.l2cap_channel.peer_mtu)
    packet_pump = MediaPacketPump(packet_source.packets)
    protocol.add_source(codec_capabilities(), packet_pump)

# -----------------------------------------------------------------------------
async def stream_packets(read_function, protocol, preferred_codec, avrcp_protocol):
    # Discover all endpoints on the remote device (matches BlueZ AVDTP Discover)
    endpoints = await protocol.discover_remote_endpoints()
    for endpoint in endpoints:
        logger.info(f"Discovered endpoint: {endpoint}")

    # Try preferred codec first
    sink = protocol.find_remote_sink_by_codec(AVDTP_AUDIO_MEDIA_TYPE, preferred_codec)
    if sink is None:
        logger.info(color(f'!!! No {preferred_codec} sink found, falling back...', 'yellow'))
        fallback_codec = A2DP_SBC_CODEC_TYPE if preferred_codec == A2DP_MPEG_2_4_AAC_CODEC_TYPE else A2DP_MPEG_2_4_AAC_CODEC_TYPE
        sink = protocol.find_remote_sink_by_codec(AVDTP_AUDIO_MEDIA_TYPE, fallback_codec)
    if sink is None:
        logger.info(color('!!! No compatible sink found', 'red'))
        return
    logger.info(color('*** Found compatible sink', 'green'))
    logger.info(sink)
    logger.info(f'### Selected sink: {sink.seid}')
    
    # Get codec type from capabilities
    media_codec_cap = sink.capabilities[1]
    actual_codec = media_codec_cap.media_codec_type
    logger.info(f'### Actual codec: {actual_codec}')
    
    # Use appropriate packet source
    if actual_codec == A2DP_MPEG_2_4_AAC_CODEC_TYPE:
        packet_source = AacPacketSource(read_function, protocol.l2cap_channel.peer_mtu)
    else:
        packet_source = SbcPacketSource(read_function, protocol.l2cap_channel.peer_mtu)
    packet_pump = MediaPacketPump(packet_source.packets)
    source = protocol.add_source(codec_capabilities(actual_codec), packet_pump)
    stream = await protocol.create_stream(source, sink)
    
    # Explicit open and start (matches BlueZ)
    await stream.open()
    await asyncio.sleep(10)  # Wait for setup
    logger.info(color('*** Starting stream', 'green'))
    await stream.start()
    
    # Send AVRCP PLAY command (matches BlueZ AVCTP)
    await avrcp_protocol.send_key_event(avc.PassThroughCommandFrame.OperationId.PLAY, pressed=True)
    await asyncio.sleep(0.1)
    await avrcp_protocol.send_key_event(avc.PassThroughCommandFrame.OperationId.PLAY, pressed=False)
    
    # Stream for 10 seconds
    await asyncio.sleep(10)
    await stream.stop()
    await stream.close()

# -----------------------------------------------------------------------------
async def main() -> None:
    transport_spec = "usb:0"
    audio_path = "test.aac"  # Change to your AAC file; or "test.sbc" for SBC
    target_address = "28:2D:7F:C2:05:5B"
    logger.info("<<< connecting to HCI...")
    async with await open_transport(transport_spec) as hci_transport:
        logger.info("<<< connected")

        # Create a Host/device
        host = Host(controller_source=hci_transport.source, controller_sink=hci_transport.sink)
        device = Device(host=host)
        device.classic_enabled = True

        # Persist keys
        keys_path = Path.home() / ".config" / "bumble" / "keys.json"
        keys_path.parent.mkdir(parents=True, exist_ok=True)
        device.keystore = JsonKeyStore.from_device(device, str(keys_path))

        # Pairing config to match BlueZ (host: DisplayYesNo, device: NoInputNoOutput)
        device.pairing_config_factory = lambda conn: PairingConfig(
            sc=True,
            mitm=False,
            bonding=True,
            delegate=PairingDelegate(io_capability=PairingDelegate.DISPLAY_OUTPUT_AND_YES_NO_INPUT),  # Updated for BlueZ match
        )

        # Setup SDP records
        device.sdp_service_records = sdp_records()
        device.name = "Bumble A2DP Source"

        # Start device
        await device.power_on()

        with open(audio_path, "rb") as audio_file:
            async def read(byte_count):
                return audio_file.read(byte_count)
            
            # Determine codec
            if audio_path.endswith('.aac'):
                preferred_codec = A2DP_MPEG_2_4_AAC_CODEC_TYPE
            elif audio_path.endswith('.sbc'):
                preferred_codec = A2DP_SBC_CODEC_TYPE
            else:
                logger.info(color('!!! Unsupported file format', 'red'))
                return
            
            try:
                logger.info(f"=== Connecting to {target_address}...")
                connection = await device.connect(target_address, transport=PhysicalTransport.BR_EDR)
                logger.info(f'=== Connected to {connection.peer_address}!')

                # Authenticate and encrypt
                logger.info('*** Authenticating...')
                await connection.authenticate()
                logger.info('*** Authenticated')
                logger.info('*** Enabling encryption...')
                await connection.encrypt()
                logger.info('*** Encryption on')

                # Explicit SDP searches (placeholder; Bumble handles via find_avdtp_service_with_connection)
                logger.info('*** Performing SDP searches...')

                # AVDTP setup
                avdtp_version = await find_avdtp_service_with_connection(connection)
                if not avdtp_version:
                    logger.info(color('!!! No A2DP service found', 'red'))
                logger.info(color(f'*** Found A2DP service, version {avdtp_version}', 'green'))
                protocol = await Protocol.connect(connection, avdtp_version)

                # AVRCP setup
                avrcp_protocol = AvrcpProtocol()
                await avrcp_protocol.connect(connection)
                logger.info(color('*** AVRCP connected', 'green'))

                # Start streaming
                await stream_packets(read, protocol, preferred_codec, avrcp_protocol)

            except Exception as e:
                logger.warning(f"Connection failed: {e}")

        await hci_transport.source.wait_for_termination()

# -----------------------------------------------------------------------------
asyncio.run(main())