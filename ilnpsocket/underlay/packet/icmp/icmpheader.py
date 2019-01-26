import struct

from ilnpsocket.underlay.packet.icmp.locatorupdate import LocatorUpdateHeader

icmp_type_to_class = {LocatorUpdateHeader.TYPE: LocatorUpdateHeader}


class ICMPHeader:
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
               + self.body

    @classmethod
    def parse_message(cls, message_bytes):
        vals = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, message_bytes[:cls.HEADER_SIZE])
        return ICMPHeader(vals[0], vals[1], vals[2])


