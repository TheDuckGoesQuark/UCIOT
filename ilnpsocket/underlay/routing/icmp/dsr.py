from ilnpsocket.underlay.routing.icmp.icmpheader import *


class RouteList:
    HEADER_DESCRIPTION_FORMAT = "!BB2x"
    HEADER_DESCRIPTION_SIZE = struct.calcsize(HEADER_DESCRIPTION_FORMAT)
    LOCATOR_FORMAT = "!Q"
    LOCATOR_SIZE = struct.calcsize(LOCATOR_FORMAT)

    def __init__(self, num_of_locs, request_id, locators):
        """
        When a route is not known between two nodes, a route discovery request can be sent.
        Each node forwarding the request will append their own locator to the packet, and
        increment the num_of_locs counter. Once received at the destination, a route reply
        must be generated and sent to the requesting node.

        The route reply is the same, returning the list of locators back to the destination.
        Since nodes can learn the reverse path along the way, then they should have next_hop
        cached for the packet.

        # TODO handle loss?

        :param num_of_locs: number of locators appended to path so far. Can also be considered the hop count
        :param request_id: unique identifier used by the requester
        :param locators: list of locator hops in order of occurrence.
        """
        self.num_of_locs = num_of_locs
        self.request_id = request_id
        self.locators = locators

    @classmethod
    def from_bytes(cls, packet_bytes):
        num_of_locs, request_id = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, packet_bytes[:cls.HEADER_DESCRIPTION_SIZE])

        locator_list = []
        start = cls.HEADER_DESCRIPTION_SIZE
        for value in range(num_of_locs):
            end = start + cls.LOCATOR_SIZE
            locator_list.append(struct.unpack(cls.LOCATOR_FORMAT, packet_bytes[start:end])[0])
            start += cls.LOCATOR_SIZE

        return RouteList(num_of_locs, request_id, locator_list)

    def __bytes__(self):
        return struct.pack(self.HEADER_DESCRIPTION_FORMAT, self.num_of_locs, self.request_id) + self.locators_to_bytes()

    def locators_to_bytes(self):
        tuple_bytes = bytearray(self.num_of_locs * self.LOCATOR_SIZE)
        start = 0
        for i in range(self.num_of_locs):
            end = start + self.LOCATOR_SIZE
            tuple_bytes[start:end] = struct.pack(self.LOCATOR_FORMAT, self.locators[i])
            start = end

        return tuple_bytes

    def append_locator(self, locator):
        self.locators.append(locator)
        self.num_of_locs = self.num_of_locs + 1

    def append_locators(self, locators):
        self.locators.extend(locators)
        self.num_of_locs = self.num_of_locs + len(locators)

    def already_in_list(self, locator):
        return locator in self.locators

    def calc_checksum(self):
        return 0


class RouteReply(RouteList):
    TYPE = 163


class RouteRequest(RouteList):
    TYPE = 162
