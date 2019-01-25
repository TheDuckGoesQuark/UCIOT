import struct

from ilnpsocket.underlay.packet.icmp.locatorupdate import LocatorUpdateHeader

icmp_type_to_class = {LocatorUpdateHeader.TYPE: LocatorUpdateHeader}


class ICMPHeader:
    HEADER_DESCRIPTION_FORMAT = "!BBH"
    HEADER_SIZE = struct.calcsize(HEADER_DESCRIPTION_FORMAT)

    def __init__(self, type, code, checksum):
        self.type = type
        self.code = code
        self.checksum = checksum

    def is_error(self):
        return self.type < 127

    def to_bytes(self):
        return struct.pack(self.HEADER_DESCRIPTION_FORMAT, self.type, self.code, self.checksum)

    @classmethod
    def parse_header(cls, message_bytes):
        vals = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, message_bytes[:cls.HEADER_SIZE])
        return ICMPHeader(vals[0], vals[1], vals[2])


