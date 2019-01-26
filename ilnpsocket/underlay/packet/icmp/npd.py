"""
Each class can be used as the body of an ICMPHeader, and are all relevant to the neighbour discovery protocol
as in RFC4861
"""
import struct


class RouterSolicitation:
    """
    When an interface becomes enabled, hosts may send out Router solicitations that request routers to generate
    router advertisements immediately, rather than at their next scheduled time.
    """
    HEADER_DESCRIPTION_FORMAT = "!4x"
    HEADER_DESCRIPTION_SIZE = struct.calcsize(HEADER_DESCRIPTION_FORMAT)
    TYPE = 133

    def __init__(self, options):
        self.options = options

    @classmethod
    def parse_message(cls, packet_bytes):
        # TODO parse options?
        header_description = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, packet_bytes[:cls.HEADER_DESCRIPTION_SIZE])
        return RouterSolicitation(None)

    def to_bytes(self):
        # TODO options to bytes
        return struct.pack(self.HEADER_DESCRIPTION_FORMAT)


class RouterAdvertisement:
    """
    Routers advertise their presence together with various link and internet parameters either periodically or in
    response to a router solicitation message.
    """
    HEADER_FORMAT = "!2BH2I"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    TYPE = 134

    def __init__(self, current_hop_limit, m_flag, o_flag, router_lifetime, reachable_time, retrans_time, options):
        self.current_hop_limit = current_hop_limit
        self.m_flag = m_flag
        self.o_flag = o_flag
        self.router_lifetime = router_lifetime
        self.reachable_time = reachable_time
        self.retrans_time = retrans_time
        self.options = options

    @classmethod
    def parse_message(cls, packet_bytes):
        # TODO parse options?
        values = struct.unpack(cls.HEADER_FORMAT, packet_bytes[:cls.HEADER_SIZE])
        m_flag = (values[1] & 128) >> 7
        o_flag = (values[1] & 64) >> 6

        return RouterAdvertisement(values[0], m_flag, o_flag, values[2], values[3], values[4], None)

    def to_bytes(self):
        # TODO options to bytes
        second_byte = (self.m_flag << 7) | (self.o_flag << 6)
        return struct.pack(self.HEADER_FORMAT, self.current_hop_limit, second_byte, self.router_lifetime,
                           self.reachable_time, self.retrans_time)


class NeighborSolicitation:
    """
    Sent by a node to determine the link-layer address of a neighbour, or to verify that a neighbour is
    still reachable via a cached link-layer address. Also used for duplicate address detection
    """


class NeighborAdvertisement:
    """
    A response to a neighbour solicitation message. A node may also send unsolicited neighbor advertisements to
    announce a link-layer address change.
    """


class Redirect:
    """
    Used by routers to inform hosts of a better first hop for a destination
    """

