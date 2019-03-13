import struct
from typing import Tuple

from underlay.routing.ilnpaddress import ILNPAddress

DSR_NEXT_HEADER_VALUE = 48
NO_NEXT_HEADER_VALUE = 59


class ILNPPacket:
    MAX_PAYLOAD_SIZE: int = 65535
    ILNPv6_HEADER_FORMAT: str = "!IHBB4Q"
    HEADER_SIZE: int = struct.calcsize(ILNPv6_HEADER_FORMAT)

    def __init__(self, src: ILNPAddress, dest: ILNPAddress, next_header: int = 0,
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
        self.src: ILNPAddress = src

        # Fourth Octet
        self.dest: ILNPAddress = dest

        self.payload: bytearray = payload

    @classmethod
    def from_bytes(cls, packet_bytes: bytearray) -> 'ILNPPacket':
        view = memoryview(packet_bytes)
        values = struct.unpack(cls.ILNPv6_HEADER_FORMAT, view[:cls.HEADER_SIZE])

        flow_label: int = values[0] & 1048575
        traffic_class: int = (values[0] >> 20 & 255)
        version: int = values[0] >> 28
        payload_length: int = values[1]
        next_header: int = values[2]
        hop_limit: int = values[3]
        src: ILNPAddress = ILNPAddress(values[4], values[5])
        dest: ILNPAddress = ILNPAddress(values[6], values[7])

        payload = view[cls.HEADER_SIZE:payload_length]

        return ILNPPacket(src, dest, next_header, hop_limit, version, traffic_class, flow_label, payload_length,
                          payload)

    def decrement_hop_limit(self) -> None:
        self.hop_limit -= 1

    def __bytes__(self) -> bytes:
        first_octet = self.flow_label | (self.traffic_class << 20) | (self.version << 28)
        header_bytes = struct.pack(self.ILNPv6_HEADER_FORMAT,
                                   first_octet,
                                   self.payload_length, self.next_header, self.hop_limit,
                                   self.src.loc, self.src.id, self.dest.loc, self.dest.id)

        return header_bytes + self.payload
