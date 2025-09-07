from bumble.sdp import ServiceAttribute, DataElement
from bumble.core import UUID
SDP_SERVICE_RECORDS = {
    0x4f49ffb0: [
        ServiceAttribute(0x0000, DataElement.unsigned_integer_32(0x4f49ffb0)),  # ServiceRecordHandle
        ServiceAttribute(0x0001, DataElement.sequence([  # ServiceClassIDList
            DataElement.uuid(UUID.from_bytes(bytes.fromhex('1ff31936572e4b36a2bfb2409b1aa6f4')))
        ])),
        ServiceAttribute(0x0002, DataElement.unsigned_integer_32(0x00000000)),  # ServiceRecordState
        ServiceAttribute(0x0004, DataElement.sequence([  # ProtocolDescriptorList
            DataElement.sequence([
                DataElement.uuid(UUID.from_16_bits(0x0100)),  # L2CAP
                DataElement.unsigned_integer_16(0x1007)
            ])
        ])),
        ServiceAttribute(0x0005, DataElement.sequence([  # BrowseGroupList
            DataElement.uuid(UUID.from_16_bits(0x1002))  # PublicBrowseGroup
        ])),
        ServiceAttribute(0x0006, DataElement.sequence([  # LanguageBaseAttributeIDList
            DataElement.unsigned_integer_16(0x656e), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0100),
            DataElement.unsigned_integer_16(0x6672), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0110),
            DataElement.unsigned_integer_16(0x6465), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0120),
            DataElement.unsigned_integer_16(0x6a61), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0130)
        ])),
        ServiceAttribute(0x0008, DataElement.unsigned_integer_8(0xff)),  # ServiceAvailability
        ServiceAttribute(0x0009, DataElement.sequence([  # BluetoothProfileDescriptorList
            DataElement.sequence([
                DataElement.uuid(UUID.from_bytes(bytes.fromhex('4b6f7c7407f449deb0b9ab4304728f29'))),
                DataElement.unsigned_integer_16(0x0100)
            ])
        ])),
        ServiceAttribute(0x0100, DataElement.text_string('AAP Client'))
    ],
    0x4f491101: [
        ServiceAttribute(0x0000, DataElement.unsigned_integer_32(0x4f491101)),
        ServiceAttribute(0x0001, DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x1101))])),
        ServiceAttribute(0x0002, DataElement.unsigned_integer_32(0x00000000)),
        ServiceAttribute(0x0004, DataElement.sequence([
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0100))]),
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0003)), DataElement.unsigned_integer_8(0x03)])
        ])),
        ServiceAttribute(0x0005, DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x1002))])),
        ServiceAttribute(0x0006, DataElement.sequence([
            DataElement.unsigned_integer_16(0x656e), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0100),
            DataElement.unsigned_integer_16(0x6672), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0110),
            DataElement.unsigned_integer_16(0x6465), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0120),
            DataElement.unsigned_integer_16(0x6a61), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0130)
        ])),
        ServiceAttribute(0x0008, DataElement.unsigned_integer_8(0xff)),
        ServiceAttribute(0x0009, DataElement.sequence([
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x1101)), DataElement.unsigned_integer_16(0x0102)])
        ])),
        ServiceAttribute(0x0100, DataElement.text_string('COM5'))
    ],
    0x4f49110a: [
        ServiceAttribute(0x0000, DataElement.unsigned_integer_32(0x4f49110a)),
        ServiceAttribute(0x0001, DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x110a))])),
        ServiceAttribute(0x0002, DataElement.unsigned_integer_32(0x00000000)),
        ServiceAttribute(0x0004, DataElement.sequence([
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0100)), DataElement.unsigned_integer_16(0x0019)]),
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0019)), DataElement.unsigned_integer_16(0x0103)])
        ])),
        ServiceAttribute(0x0005, DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x1002))])),
        ServiceAttribute(0x0006, DataElement.sequence([
            DataElement.unsigned_integer_16(0x656e), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0100),
            DataElement.unsigned_integer_16(0x6672), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0110),
            DataElement.unsigned_integer_16(0x6465), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0120),
            DataElement.unsigned_integer_16(0x6a61), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0130)
        ])),
        ServiceAttribute(0x0008, DataElement.unsigned_integer_8(0xff)),
        ServiceAttribute(0x0009, DataElement.sequence([
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x110d)), DataElement.unsigned_integer_16(0x0103)])
        ])),
        ServiceAttribute(0x0100, DataElement.text_string('Audio Source')),
        ServiceAttribute(0x0311, DataElement.unsigned_integer_16(0x0001))
    ],
    0x4f49110c: [
        ServiceAttribute(0x0000, DataElement.unsigned_integer_32(0x4f49110c)),
        ServiceAttribute(0x0001, DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x110c))])),
        ServiceAttribute(0x0002, DataElement.unsigned_integer_32(0x00000000)),
        ServiceAttribute(0x0004, DataElement.sequence([
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0100)), DataElement.unsigned_integer_16(0x0017)]),
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0017)), DataElement.unsigned_integer_16(0x0104)])
        ])),
        ServiceAttribute(0x0005, DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x1002))])),
        ServiceAttribute(0x0006, DataElement.sequence([
            DataElement.unsigned_integer_16(0x656e), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0100),
            DataElement.unsigned_integer_16(0x6672), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0110),
            DataElement.unsigned_integer_16(0x6465), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0120),
            DataElement.unsigned_integer_16(0x6a61), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0130)
        ])),
        ServiceAttribute(0x0008, DataElement.unsigned_integer_8(0xff)),
        ServiceAttribute(0x0009, DataElement.sequence([
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x110e)), DataElement.unsigned_integer_16(0x0106)])
        ])),
        ServiceAttribute(0x000d, DataElement.sequence([
            DataElement.sequence([
                DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0100)), DataElement.unsigned_integer_16(0x001b)]),
                DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0017)), DataElement.unsigned_integer_16(0x0104)])
            ]),
            DataElement.sequence([
                DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0100)), DataElement.unsigned_integer_16(0x1005)]),
                DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0008))])
            ])
        ])),
        ServiceAttribute(0x0100, DataElement.text_string('AVRCP Device')),
        ServiceAttribute(0x0101, DataElement.text_string('Remote Control Device')),
        ServiceAttribute(0x0311, DataElement.unsigned_integer_16(0x0011))
    ],
    0x4f49110e: [
        ServiceAttribute(0x0000, DataElement.unsigned_integer_32(0x4f49110e)),
        ServiceAttribute(0x0001, DataElement.sequence([
            DataElement.uuid(UUID.from_16_bits(0x110e)), DataElement.uuid(UUID.from_16_bits(0x110f))
        ])),
        ServiceAttribute(0x0002, DataElement.unsigned_integer_32(0x00000000)),
        ServiceAttribute(0x0004, DataElement.sequence([
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0100)), DataElement.unsigned_integer_16(0x0017)]),
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0017)), DataElement.unsigned_integer_16(0x0104)])
        ])),
        ServiceAttribute(0x0005, DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x1002))])),
        ServiceAttribute(0x0006, DataElement.sequence([
            DataElement.unsigned_integer_16(0x656e), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0100),
            DataElement.unsigned_integer_16(0x6672), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0110),
            DataElement.unsigned_integer_16(0x6465), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0120),
            DataElement.unsigned_integer_16(0x6a61), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0130)
        ])),
        ServiceAttribute(0x0008, DataElement.unsigned_integer_8(0xff)),
        ServiceAttribute(0x0009, DataElement.sequence([
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x110e)), DataElement.unsigned_integer_16(0x0105)])
        ])),
        ServiceAttribute(0x0100, DataElement.text_string('AVRCP Device')),
        ServiceAttribute(0x0101, DataElement.text_string('Remote Control Device')),
        ServiceAttribute(0x0311, DataElement.unsigned_integer_16(0x0002))
    ],
    0x4f49111f: [
        ServiceAttribute(0x0000, DataElement.unsigned_integer_32(0x4f49111f)),
        ServiceAttribute(0x0001, DataElement.sequence([
            DataElement.uuid(UUID.from_16_bits(0x111f)), DataElement.uuid(UUID.from_16_bits(0x1203))
        ])),
        ServiceAttribute(0x0002, DataElement.unsigned_integer_32(0x00000000)),
        ServiceAttribute(0x0004, DataElement.sequence([
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0100))]),
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x0003)), DataElement.unsigned_integer_8(0x08)])
        ])),
        ServiceAttribute(0x0005, DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x1002))])),
        ServiceAttribute(0x0006, DataElement.sequence([
            DataElement.unsigned_integer_16(0x656e), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0100),
            DataElement.unsigned_integer_16(0x6672), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0110),
            DataElement.unsigned_integer_16(0x6465), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0120),
            DataElement.unsigned_integer_16(0x6a61), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0130)
        ])),
        ServiceAttribute(0x0008, DataElement.unsigned_integer_8(0xff)),
        ServiceAttribute(0x0009, DataElement.sequence([
            DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x111e)), DataElement.unsigned_integer_16(0x0107)])
        ])),
        ServiceAttribute(0x0100, DataElement.text_string('Handsfree Gateway')),
        ServiceAttribute(0x0301, DataElement.unsigned_integer_8(0x01)),
        ServiceAttribute(0x0311, DataElement.unsigned_integer_16(0x002f))
    ],
    0x4f491200: [
        ServiceAttribute(0x0000, DataElement.unsigned_integer_32(0x4f491200)),
        ServiceAttribute(0x0001, DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x1200))])),
        ServiceAttribute(0x0002, DataElement.unsigned_integer_32(0x00000000)),
        ServiceAttribute(0x0005, DataElement.sequence([DataElement.uuid(UUID.from_16_bits(0x1002))])),
        ServiceAttribute(0x0006, DataElement.sequence([
            DataElement.unsigned_integer_16(0x656e), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0100),
            DataElement.unsigned_integer_16(0x6672), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0110),
            DataElement.unsigned_integer_16(0x6465), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0120),
            DataElement.unsigned_integer_16(0x6a61), DataElement.unsigned_integer_16(0x006a), DataElement.unsigned_integer_16(0x0130)
        ])),
        ServiceAttribute(0x0008, DataElement.unsigned_integer_8(0xff)),
        ServiceAttribute(0x0101, DataElement.text_string('PnP Information')),
        # ServiceAttribute(0x0200, DataElement.unsigned_integer_16(0x0102)),
        ServiceAttribute(0x0201, DataElement.unsigned_integer_16(0x004c)),
        # ServiceAttribute(0x0202, DataElement.unsigned_integer_16(0x0000)),
        # ServiceAttribute(0x0203, DataElement.unsigned_integer_16(0x0f60)),
        # ServiceAttribute(0x0204, DataElement.boolean(True)),
        ServiceAttribute(0x0205, DataElement.unsigned_integer_16(0x0001)),
        # ServiceAttribute(0xa000, DataElement.unsigned_integer_32(0x00a026c4)),
        # ServiceAttribute(0xafff, DataElement.unsigned_integer_16(0x0001))
    ]
}