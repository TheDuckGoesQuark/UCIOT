from math import ceil
import struct

from ilnpsocket.underlay.packet.icmp.icmpmessage import ICMPMessage

NEXT_HEADER_CLASSES = {
    ICMPMessage.NEXT_HEADER_VALUE, ICMPMessage
}


class Packet:
    MAX_PAYLOAD_SIZE = 65535
    ILNPv6_HEADER_FORMAT = "!IHBB4Q"
    HEADER_SIZE = struct.calcsize(ILNPv6_HEADER_FORMAT)

    def __init__(self, src, dest, next_header=0,
                 hop_limit=32, version=6, traffic_class=0,
                 flow_label=0, payload_length=0,
                 payload=None):
        # First octet
        self.version = version
        self.traffic_class = traffic_class
        self.flow_label = flow_label

        # Second Octet
        self.payload_length = payload_length
        self.next_header = next_header
        self.hop_limit = hop_limit

        # Third Octet
        self.src_locator = src[0]
        self.src_identifier = src[1]

        # Fourth Octet
        self.dest_locator = dest[0]
        self.dest_identifier = dest[1]

        self.payload = payload

    @classmethod
    def parse_header(cls, packet_bytes):
        values = struct.unpack(cls.ILNPv6_HEADER_FORMAT, packet_bytes[:cls.HEADER_SIZE])

        flow_label = values[0] & 1048575
        traffic_class = (values[0] >> 20 & 255)
        version = values[0] >> 28
        payload_length = values[1]
        next_header = values[2]
        hop_limit = values[3]
        src = (values[4], values[5])
        dest = (values[6], values[7])

        return Packet(src, dest, next_header, hop_limit, version, traffic_class, flow_label, payload_length)

    def decrement_hop_limit(self):
        self.hop_limit -= 1

    def to_bytes(self):
        first_octet = self.flow_label | (self.traffic_class << 20) | (self.version << 28)
        header_bytes = struct.pack(self.ILNPv6_HEADER_FORMAT,
                                   first_octet,
                                   self.payload_length, self.next_header, self.hop_limit,
                                   self.src_locator, self.src_identifier,
                                   self.dest_locator,
                                   self.dest_identifier)
        header_bytes += self.payload
        return header_bytes

    def print_packet(self):
        print("+---------------Start------------------+")
        print("ILNP Source: {}-{}".format(self.src_locator, self.src_identifier))
        print("ILNP Dest  : {}-{}".format(self.dest_locator, self.dest_identifier))
        print("Hop limit  : {}".format(self.hop_limit))
        print("Payload    : {}".format(self.payload))
        print("+---------------End-------------------+")
