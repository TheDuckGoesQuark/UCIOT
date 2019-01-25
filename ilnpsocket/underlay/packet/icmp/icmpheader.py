import struct


class ICMPHeader:
    HEADER_DESCRIPTION_FORMAT = "!BBH"
    HEADER_SIZE = struct.calcsize(HEADER_DESCRIPTION_FORMAT)

    def __init__(self, type, code, checksum):
        self.type = type
        self.code = code
        self.checksum = checksum

    def is_error(self):
        return self.type < 127

    @classmethod
    def parse_header(cls, message_bytes):
        vals = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, message_bytes[:cls.HEADER_SIZE])
        return ICMPHeader(vals[0], vals[1], vals[2])


