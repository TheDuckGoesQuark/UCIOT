from math import ceil
import struct


def parse_payload(offset_bits, payload_length, data):
    # Assume padding
    first_byte_index = ceil(offset_bits / 8)
    last_byte_index = first_byte_index + payload_length
    return data[first_byte_index:last_byte_index]


class Packet:
    def __init__(self, payload, src, dest, header=None):
        if header is None:
            self.header = PacketHeader(src[0], src[1], dest[0], dest[1], len(payload))
        else:
            self.header = header

        self.payload = payload

    def decrement_hop_limit(self):
        self.header.hop_limit -= 1

    def print_packet(self):
        self.header.print_header()
        print("Payload    : {}".format(self.payload))

    @classmethod
    def from_bytes(cls, packet_bytes):
        header = PacketHeader.parse_header(packet_bytes)
        payload = parse_payload(header.length, header.payload_length, packet_bytes)
        return Packet(payload, None, None, header)

    def to_bytes(self):
        packet_bytes = self.header.to_bytes()
        packet_bytes += self.payload
        return packet_bytes

    def get_payload(self):
        return self.payload


class PacketHeader:
    """
    The header of the ILNP packet.
    """

    HEADER_FORMAT = "!IHBB4Q"

    def __init__(self, src_locator, src_identifier, dest_locator, dest_identifier, payload_length, next_header=0,
                 hop_limit=32, version=1, traffic_class=1, flow_label=1):
        self.version = version
        self.traffic_class = traffic_class
        self.flow_label = flow_label
        self.payload_length = payload_length
        self.next_header = next_header
        self.hop_limit = hop_limit
        self.src_locator = src_locator
        self.src_identifier = src_identifier
        self.dest_locator = dest_locator
        self.dest_identifier = dest_identifier
        self.length = struct.calcsize(self.HEADER_FORMAT)

    def to_bytes(self):
        first_octet = self.flow_label | (self.traffic_class << 20) | (self.version << 28)
        return struct.pack(self.HEADER_FORMAT, first_octet, self.payload_length, self.next_header, self.hop_limit,
                           self.src_locator, self.src_identifier, self.dest_locator, self.dest_identifier)

    def print_header(self):
        print("ILNP Source: {}-{}".format(self.src_locator, self.src_identifier))
        print("ILNP Dest  : {}-{}".format(self.dest_locator, self.dest_identifier))
        print("Hop limit  : {}".format(self.hop_limit))

    @classmethod
    def parse_header(cls, packet_bytes):
        vals = struct.unpack(cls.HEADER_FORMAT, packet_bytes[:struct.calcsize(cls.HEADER_FORMAT)])

        flow_label = vals[0] & 1048575
        traffic_class = (vals[0] >> 20 & 255)
        version = vals[0] >> 28

        return PacketHeader(vals[4], vals[5], vals[6], vals[7], vals[1], vals[2], vals[3],
                            version, traffic_class, flow_label)
