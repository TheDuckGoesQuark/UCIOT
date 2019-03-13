import struct
from typing import Tuple

DSR_NEXT_HEADER_VALUE = 48
NO_NEXT_HEADER_VALUE = 59


class IPPacket:
    MAX_PAYLOAD_SIZE: int = 65535
    ILNPv6_HEADER_FORMAT: str = "!IHBB4Q"
    HEADER_SIZE: int = struct.calcsize(ILNPv6_HEADER_FORMAT)

    def __init__(self, src: Tuple, dest: Tuple, next_header: int = 0,
                 hop_limit: int = 32, version: int = 6, traffic_class: int = 0,
                 flow_label: int = 0, payload_length: int = 0,
                 payload: memoryview = None):
        # First octet
        self.version: int = version
        self.traffic_class: int = traffic_class
        self.flow_label: int = flow_label

        # Second Octet
        self.payload_length: int = payload_length
        self.next_header: int = next_header
        self.hop_limit: int = hop_limit

        # Third Octet
        self.src_locator: int = src[0]
        self.src_identifier: int = src[1]

        # Fourth Octet
        self.dest_locator: int = dest[0]
        self.dest_identifier: int = dest[1]

        self.payload: bytearray = payload

    @classmethod
    def from_bytes(cls, packet_bytes: bytearray) -> 'IPPacket':
        view = memoryview(packet_bytes)
        values = struct.unpack(cls.ILNPv6_HEADER_FORMAT, view[:cls.HEADER_SIZE])

        flow_label: int = values[0] & 1048575
        traffic_class: int = (values[0] >> 20 & 255)
        version: int = values[0] >> 28
        payload_length: int = values[1]
        next_header: int = values[2]
        hop_limit: int = values[3]
        src: Tuple = (values[4], values[5])
        dest: Tuple = (values[6], values[7])

        payload = view[cls.HEADER_SIZE:payload_length]

        return IPPacket(src, dest, next_header, hop_limit, version, traffic_class, flow_label, payload_length, payload)

    def decrement_hop_limit(self) -> None:
        self.hop_limit -= 1

    def __bytes__(self) -> bytes:
        first_octet = self.flow_label | (self.traffic_class << 20) | (self.version << 28)
        header_bytes = struct.pack(self.ILNPv6_HEADER_FORMAT,
                                   first_octet,
                                   self.payload_length, self.next_header, self.hop_limit,
                                   self.src_locator, self.src_identifier,
                                   self.dest_locator,
                                   self.dest_identifier)

        return header_bytes + self.payload

    def __str__(self) -> str:
        return "+---------------Start------------------+ \n" \
               "ILNP Source: {}-{}\n" \
               "ILNP Dest  : {}-{}\n" \
               "Hop limit  : {}\n" \
               "Payload    : {}\n" \
               "+----------------End-------------------+".format(self.src_locator, self.src_identifier,
                                                                 self.dest_locator, self.dest_identifier,
                                                                 self.hop_limit, self.payload)
