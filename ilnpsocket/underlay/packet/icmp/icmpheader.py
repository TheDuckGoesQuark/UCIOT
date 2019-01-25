import struct


class ICMPHeader:
    HEADER_DESCRIPTION_FORMAT = "!BB"
    MIN_SIZE = struct.calcsize(HEADER_DESCRIPTION_FORMAT)

    def __init__(self, type, code, checksum):
        self.type = type
        self.code = code
        self.checksum = checksum

    @classmethod
    def parse_header(cls, packet_bytes):
        vals = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, packet_bytes[:cls.MIN_SIZE])

        # TODO

        flow_label = vals[0] & 1048575
        traffic_class = (vals[0] >> 20 & 255)
        version = vals[0] >> 28
        payload_length = vals[1]
        next_header = vals[2]
        hop_limit = vals[3]
        dest = (vals[6], vals[7])


