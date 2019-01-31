import struct

from ilnpsocket.underlay.packet.icmp.icmpheader import ICMPHeader, calc_checksum
from ilnpsocket.underlay.packet.packet import Packet


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
        header_description = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, packet_bytes[:cls.HEADER_DESCRIPTION_SIZE])

        num_of_locs = header_description[0]
        request_id = header_description[1]

        list_format = cls.LOCATOR_FORMAT.format(num_of_locs)
        locator_list = []
        start = cls.HEADER_DESCRIPTION_SIZE
        for value in range(num_of_locs):
            end = start + cls.LOCATOR_SIZE
            locator_list.append(struct.unpack(cls.LOCATOR_FORMAT, packet_bytes[start:end]))
            start += cls.LOCATOR_SIZE

        return RouteList(num_of_locs, request_id, list_format)

    def __bytes__(self):
        return struct.pack(self.HEADER_DESCRIPTION_FORMAT, self.num_of_locs, self.request_id, self.locators_to_bytes())

    def locators_to_bytes(self):
        tuple_bytes = bytearray(self.num_of_locs * self.LOCATOR_SIZE)
        start = 0
        for i in range(self.num_of_locs):
            end = start + self.LOCATOR_SIZE
            tuple_bytes[start:end] = struct.pack(self.LOCATOR_FORMAT, self.locators[i])

        return tuple_bytes

    def append_locator(self, locator):
        self.locators.append(locator)

    def already_in_list(self, locator):
        return locator in self.locators

    def calc_checksum(self):
        return 0


class RouteReply(RouteList):

    TYPE = 163

    def apply_function(self, packet, router):
        pass


class RouteRequest(RouteList):

    TYPE = 162

    def apply_function(self, packet, router, arriving_interface):
        # cache path so far
        self.update_routing_table(router, arriving_interface)

        if router.is_for_me(packet):
            self.send_route_reply(router, packet.src_locator)
        else:
            self.add_self_and_forward(packet, router, arriving_interface)

    def update_routing_table(self, router, arriving_interface):
        length_of_path = len(self.locators)

        for locator in self.locators:
            router.routing_table.record_path(locator, length_of_path, arriving_interface)
            length_of_path -= 1

    def send_route_reply(self, router, origin):
        packet = self.construct_reply(router, origin)
        router.forward_packet(packet, router.get_next_hops(origin))

    def construct_reply(self, router, origin):
        reply = RouteReply(self.num_of_locs, self.request_id, self.locators)
        icmp_msg = ICMPHeader(self.TYPE, 0, calc_checksum(self.TYPE, 0, self.calc_checksum()), reply)
        return router.construct_host_packet(bytes(icmp_msg), origin)

    def add_self_and_forward(self, arriving_interface):
        self.append_locator(arriving_interface)
        # TODO change flow? feeling a bit spaghetti...
        return router.construct_host_packet(bytes(icmp_msg), origin)
