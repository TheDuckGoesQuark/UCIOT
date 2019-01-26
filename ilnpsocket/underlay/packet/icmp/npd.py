"""
Each class can be used as the body of an ICMPHeader, and are all relevant to the neighbour discovery protocol
as in RFC4861
"""
import struct


class RouterSolicitation:
    """
    When an interface becomes enabled, hosts may send out Router solications that request routers to generate
    router advertisements immediately, rather than at their next scheduled time.
    """
    HEADER_DESCRIPTION_FORMAT = "!BB2x"
    HEADER_DESCRIPTION_SIZE = struct.calcsize(HEADER_DESCRIPTION_FORMAT)
    LOCATOR_TUPLE_FORMAT = "!LHH"
    LOCATOR_TUPLE_SIZE = struct.calcsize(LOCATOR_TUPLE_FORMAT)
    TYPE = 133

    def __init__(self, num_of_locs, operation, preference_tuples):
        """
        Locator Update Header as described in RFC6743 for ILNPv6.
        :param num_of_locs: The number of 64 bit locator values that are advertised in this message
        :param operation: whether or not this is a locator update advertisement or ack
        :param preference_tuples: the set of (locator, preference, lifetime) tuples
        """
        self.num_of_locs = num_of_locs
        self.operation = operation
        self.preference_tuples = preference_tuples

    @classmethod
    def parse_message(cls, packet_bytes):
        header_description = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, packet_bytes[:cls.HEADER_DESCRIPTION_SIZE])

        num_of_locs = header_description[0]
        operation = header_description[1]
        preference_tuples = []
        start = cls.HEADER_DESCRIPTION_SIZE
        for i in range(num_of_locs):
            end = start + cls.LOCATOR_TUPLE_SIZE
            preference_tuple = struct.unpack(cls.LOCATOR_TUPLE_FORMAT, packet_bytes[start:end])
            preference_tuples.append(preference_tuple)
            start = end

        return LocatorUpdateHeader(num_of_locs, operation, preference_tuples)

    def to_bytes(self):
        return struct.pack(self.HEADER_DESCRIPTION_FORMAT, self.num_of_locs, self.operation) \
               + self.preference_tuples_to_bytes()

    def preference_tuples_to_bytes(self):
        tuple_bytes = bytearray(self.num_of_locs * self.LOCATOR_TUPLE_SIZE)
        start = 0
        for i in range(self.num_of_locs):
            end = start + self.LOCATOR_TUPLE_SIZE
            tuple_bytes[start:end] = struct.pack(self.LOCATOR_TUPLE_FORMAT, self.preference_tuples[i])

        return tuple_bytes


class RouterAdvertisment:
    """
    Routers advertise their presence together with various link and internet parameters either periodically or in
    response to a router solicitation message.
    """


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

