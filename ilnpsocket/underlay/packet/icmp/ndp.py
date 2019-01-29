"""
Each class can be used as the body of an ICMPHeader, and are all relevant to the neighbour discovery protocol
as in RFC4861
"""
import struct

from ilnpsocket.underlay.packet.icmp.icmpmessage import ICMPMessage


class RouterSolicitation:
    """
    When an interface becomes enabled, hosts may send out Router solicitations that request routers to generate
    router advertisements immediately, rather than at their next scheduled time.

    Routers are considered nodes that interfaces for multiple locators (i.e. are capable of forwarding packets)

    Router solicitation will be forwarded by each router to all interfaces it knows
    about other than the arriving interface.
    """
    HEADER_DESCRIPTION_FORMAT = "!4x"
    HEADER_DESCRIPTION_SIZE = struct.calcsize(HEADER_DESCRIPTION_FORMAT)
    TYPE = 133
    CODE = 0

    def __init__(self, options):
        self.options = options

    @classmethod
    def parse_message(cls, packet_bytes):
        header_description = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, packet_bytes[:cls.HEADER_DESCRIPTION_SIZE])
        return RouterSolicitation(None)

    def __bytes__(self):
        return struct.pack(self.HEADER_DESCRIPTION_FORMAT)

    def apply_function_to_router(self, router):
        """
        Carries out required routing operations for router solicitation
        :param router: router requested to advertise
        :return:
        """
        advertisement = RouterAdvertisement(0, False, False, 0, 0, 0, None)
        icmp = ICMPMessage(self.TYPE, self.CODE, )

    def calc_checksum(self):
        # TODO checksum
        pass


class RouterAdvertisement:
    """
    Routers advertise their presence together with various link and internet parameters either periodically or in
    response to a router solicitation message.

    Routers are considered nodes that interfaces for multiple locators (i.e. are capable of forwwarding packets)
    """
    HEADER_FORMAT = "!2BH2I"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    TYPE = 134
    CODE = 0

    def __init__(self, current_hop_limit, m_flag, o_flag, router_lifetime, reachable_time, retrans_time, options):
        """
        :param current_hop_limit: the default value that should be placed in the hop count field of the IP header for
        outgoing IP packets. A value of 0 means unspecified.
        :param m_flag: "Managed Address Configuration" flag.
        :param o_flag: "Other configuration" flag.
        :param router_lifetime:
        :param reachable_time: the lifetime associated with the default router in units of seconds. A value of 0
        indicates that the router is not a default router and should not appear on the default router list.
        :param retrans_time: The time in milliseconds that a node assumes a neighbor is reachable after having received
        a reachability confirmation. A value of 0 means unspecified by this router.
        :param options:
        """
        self.current_hop_limit = current_hop_limit
        self.m_flag = m_flag
        self.o_flag = o_flag
        self.router_lifetime = router_lifetime
        self.reachable_time = reachable_time
        self.retrans_time = retrans_time
        self.options = options

    @classmethod
    def parse_message(cls, packet_bytes):
        values = struct.unpack(cls.HEADER_FORMAT, packet_bytes[:cls.HEADER_SIZE])
        m_flag = (values[1] >> 7) & 1
        o_flag = (values[1] >> 6) & 1

        return RouterAdvertisement(values[0], m_flag, o_flag, values[2], values[3], values[4], None)

    def __bytes__(self):
        second_byte = (self.m_flag << 7) | (self.o_flag << 6)
        return struct.pack(self.HEADER_FORMAT, self.current_hop_limit, second_byte, self.router_lifetime,
                           self.reachable_time, self.retrans_time)

    def calc_checksum(self):
        # TODO checksum
        pass

class NeighborSolicitation:
    """
    Sent by a node to determine the link-layer address of a neighbour, or to verify that a neighbour is
    still reachable via a cached link-layer address. Also used for duplicate address detection

    A neighbor is considered any node within the same locator.
    """
    HEADER_FORMAT = "!4x2Q"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    TYPE = 135
    CODE = 0

    def __init__(self, target_locator, target_identifier, options):
        """
        :param target_locator: the locator of the target of the solicitation
        :param target_identifier: the identifier of the target of the solicitation
        :param options:
        """
        self.target_locator = target_locator
        self.target_identifier = target_identifier
        self.options = options

    @classmethod
    def parse_message(cls, packet_bytes):
        values = struct.unpack(cls.HEADER_FORMAT, packet_bytes[:cls.HEADER_SIZE])
        return NeighborSolicitation(values[0], values[1], None)

    def __bytes__(self):
        return struct.pack(self.HEADER_FORMAT, self.target_locator, self.target_identifier)

    def calc_checksum(self):
        # TODO checksum
        pass


class NeighborAdvertisement:
    """
    A response to a neighbour solicitation message. A node may also send unsolicited neighbor advertisements to
    announce a link-layer address change.
    """
    HEADER_FORMAT = "!B3x2Q"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    TYPE = 136
    CODE = 0

    def __init__(self, router_flag, solicited_flag, override_flag, target_locator, target_identifier, options):
        """
        :param router_flag: true indicates that the sender is a router
        :param solicited_flag: true indicates that this was sent in response to a neighbor solicitation
        :param override_flag: true indicates that the advertisement should override an existin cache entry.
        :param target_locator: the locator of the target of the solicitation
        :param target_identifier: the identifier of the target of the solicitation
        :param options:
        """
        self.router_flag = router_flag
        self.solicited_flag = solicited_flag
        self.override_flag = override_flag
        self.target_locator = target_locator
        self.target_identifier = target_identifier
        self.options = options

    @classmethod
    def parse_message(cls, packet_bytes):
        values = struct.unpack(cls.HEADER_FORMAT, packet_bytes[:cls.HEADER_SIZE])
        r_flag = (values[0] >> 7) & 1
        s_flag = (values[0] >> 6) & 1
        o_flag = (values[0] >> 5) & 1
        return NeighborAdvertisement(r_flag, s_flag, o_flag, values[1], values[2], None)

    def __bytes__(self):
        flag_byte = (self.router_flag << 7) | (self.solicited_flag << 6) | (self.override_flag << 5)
        return struct.pack(self.HEADER_FORMAT, flag_byte, self.target_locator, self.target_identifier)

    def calc_checksum(self):
        # TODO checksum
        pass


class Redirect:
    """
    Used by routers to inform hosts of a better first hop for a destination
    """
    HEADER_FORMAT = "!4x4Q"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
    TYPE = 137
    CODE = 0

    def __init__(self, target_locator, target_identifier, dest_locator, dest_identifier, options):
        """
        :param target_locator: locator of address that is a better first hop
        :param target_identifier: identifier of address that is a better first hop
        :param dest_locator: locator of the destination that is redirected to the target
        :param dest_identifier: identifier of the destination that is redirected to the target
        :param options:
        """
        self.target_locator = target_locator
        self.target_identifier = target_identifier
        self.dest_locator = dest_locator
        self.dest_identifier = dest_identifier
        self.options = options

    @classmethod
    def parse_message(cls, packet_bytes):
        values = struct.unpack(cls.HEADER_FORMAT, packet_bytes[:cls.HEADER_SIZE])
        return NeighborAdvertisement(values[0], values[1], values[2], values[3], None)

    def __bytes__(self):
        return struct.pack(self.HEADER_FORMAT, self.target_locator, self.target_identifier,
                           self.dest_locator, self.dest_identifier)

    def calc_checksum(self):
        # TODO checksum
        pass


