import struct

from ilnpsocket.underlay.packet.icmp.icmpheader import ICMPHeader
from ilnpsocket.underlay.packet.packet import Packet


class LocatorUpdateHeader(ICMPHeader):
    HEADER_BODY_FORMAT = "!"

    def __init__(self, type, code, checksum, num_of_locs, operation, preference_tuples, reserved=0):
        super().__init__(type, code, checksum)

    @classmethod
    def parse_packet(cls, packet_bytes):
        vals = struct.unpack(cls.HEADER_BODY_FORMAT, packet_bytes[:cls.HEADER_SIZE])

        flow_label = vals[0] & 1048575
        traffic_class = (vals[0] >> 20 & 255)
        version = vals[0] >> 28
        payload_length = vals[1]
        next_header = vals[2]
        hop_limit = vals[3]
        src = (vals[4], vals[5])
        dest = (vals[6], vals[7])

        payload = packet_bytes[cls.HEADER_SIZE:cls.HEADER_SIZE + payload_length]

        return Packet(payload, src, dest, next_header, hop_limit, version, traffic_class, flow_label)

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
