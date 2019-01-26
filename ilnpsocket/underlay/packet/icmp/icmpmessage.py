import struct

from ilnpsocket.underlay.packet.icmp.locatorupdate import LocatorUpdateHeader

icmp_type_to_class = {LocatorUpdateHeader.TYPE: LocatorUpdateHeader}


class ICMPMessage:
    NEXT_HEADER_VALUE = 58
    HEADER_DESCRIPTION_FORMAT = "!BBH"
    HEADER_SIZE = struct.calcsize(HEADER_DESCRIPTION_FORMAT)

    def __init__(self, message_type, code, checksum, body):
        self.message_type = message_type
        self.code = code
        self.checksum = checksum
        self.body = body

    def is_error(self):
        return self.message_type < 127

    def to_bytes(self):
        return struct.pack(self.HEADER_DESCRIPTION_FORMAT, self.message_type, self.code, self.checksum) \
               + self.body.to_bytes()

    @classmethod
    def parse_message(cls, message_bytes):
        vals = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, message_bytes[:cls.HEADER_SIZE])
        message_type = vals[0]
        body = icmp_type_to_class[message_type].parse_message(message_bytes[cls.HEADER_SIZE:])
        return ICMPMessage(message_type, vals[1], vals[2], body)


