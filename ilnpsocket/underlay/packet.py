from math import ceil
import struct


def parse_payload(offset_bits, payload_length, data):
    # Assume padding
    first_byte_index = ceil(offset_bits / 8)
    last_byte_index = first_byte_index + payload_length
    return data[first_byte_index:last_byte_index]


class Packet:
    HEADER_FORMAT = "!IHBB4Q"
    MIN_SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self, payload, src, dest, next_header=0,
                 hop_limit=32, version=1, traffic_class=1, flow_label=1, payload_length=None):
        # First octet
        self.version = version
        self.traffic_class = traffic_class
        self.flow_label = flow_label

        # Second Octet
        if payload_length is not None:
            self.payload_length = len(payload_length)
        else:
            self.payload_length = len(payload)

        self.next_header = next_header
        self.hop_limit = hop_limit

        # Third Octet
        self.src_locator = src[0]
        self.src_identifier = src[1]

        # Fourth Octet
        self.dest_locator = dest[0]
        self.dest_identifier = dest[1]

        # Payload
        self.payload = payload

    @classmethod
    def parse_packet(cls, packet_bytes):
        vals = struct.unpack(cls.HEADER_FORMAT, packet_bytes[:cls.MIN_SIZE])

        flow_label = vals[0] & 1048575
        traffic_class = (vals[0] >> 20 & 255)
        version = vals[0] >> 28
        payload_length = vals[1]
        next_header = vals[2]
        hop_limit = vals[3]
        src = (vals[4], vals[5])
        dest = (vals[6], vals[7])

        payload = packet_bytes[cls.MIN_SIZE:cls.MIN_SIZE + payload_length]

        return Packet(payload, src, dest, next_header, hop_limit, version, traffic_class, flow_label)

    def decrement_hop_limit(self):
        self.hop_limit -= 1

    def print_packet(self):
        print("ILNP Source: {}-{}".format(self.src_locator, self.src_identifier))
        print("ILNP Dest  : {}-{}".format(self.dest_locator, self.dest_identifier))
        print("Hop limit  : {}".format(self.hop_limit))
        print("Payload    : {}".format(self.payload))

    def to_bytes(self):
        first_octet = self.flow_label | (self.traffic_class << 20) | (self.version << 28)
        header_bytes = struct.pack(self.HEADER_FORMAT,
                                   first_octet,
                                   self.payload_length, self.next_header, self.hop_limit,
                                   self.src_locator, self.src_identifier,
                                   self.dest_locator,
                                   self.dest_identifier)
        header_bytes += self.payload
        return header_bytes
