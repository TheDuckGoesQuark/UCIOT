import collections
import logging
import random

from underlay.routing.dsrmessages import RouteRequest, RouteReply, RouteList
from ilnpsocket.underlay.routing.forwardingtable import ForwardingTable


class DSRService:
    """
    DSR service handles route request and reply messages, and updates the forwarding table with relevant information
    """

    def __init__(self, router, forwarding_table_refresh_secs):
        """
        Initializes DSRService with forwarding table which it will maintain with information it gains from routing
        messages.
        :param forwarding_table_refresh_secs: time between each forwarding table refresh
        :type router: Router
        :param router: router that can be used to forward any control messages
        """
        self.awaiting_route = {}
        self.router = router
        self.forwarding_table = ForwardingTable(forwarding_table_refresh_secs)
        # Fixed size list of request ids to track those that have already been seen
        self.recent_request_ids = collections.deque(5 * [0], 5)
        self.network_graph = NetworkGraph(self.router.interfaced_locators)

    def is_recently_seen_id(self, request_id):
        return request_id in self.recent_request_ids

    def find_route_for_packet(self, packet):
        request_id = create_request_id()
        self.awaiting_route[request_id] = packet
        request_packet = self.build_route_request_packet(request_id, (packet.dest_locator, packet.dest_identifier))
        self.router.flood_to_neighbours(request_packet)

    def build_route_request_packet(self, request_id, destination):
        rreq = RouteRequest(0, request_id, [])
        icmp_message = ICMPHeader(rreq.TYPE, 0, 0, bytes(rreq))
        packet = self.router.construct_host_packet(bytes(icmp_message), destination)
        packet.next_header = ICMPHeader.NEXT_HEADER_VALUE
        return packet

    def build_route_reply_packet(self, rreq, destination):
        rrply = RouteReply(rreq.num_of_locs, rreq.request_id, rreq.locators)
        icmp_message = ICMPHeader(rrply.TYPE, 0, 0, bytes(rrply))
        packet = self.router.construct_host_packet(bytes(icmp_message), destination)
        packet.next_header = ICMPHeader.NEXT_HEADER_VALUE
        return packet

    def handle_message(self, packet, locator_interface):
        packet.payload = ICMPHeader.from_bytes(packet.payload)

        if packet.payload.message_type is RouteRequest.TYPE:
            logging.debug("Received route request")
            self.handle_route_request(packet, locator_interface)
        elif packet.payload.message_type is RouteReply.TYPE:
            logging.debug("Received route reply")
            self.handle_route_reply(packet, locator_interface)

    def handle_route_request(self, packet, arriving_locator):
        rreq = packet.payload.body
        self.add_path_to_forwarding_table(rreq.locators, arriving_locator)

        if self.router.is_for_me(packet):
            logging.debug("Replying to route request")
            rreq.append_locator(arriving_locator)

            if arriving_locator != packet.dest_locator:
                rreq.append_locator(packet.dest_locator)

            self.reply_to_route_request(rreq, (packet.src_locator, packet.src_identifier))
        elif not self.is_recently_seen_id(rreq.request_id) and not rreq.already_in_list(arriving_locator):
            known_path = self.network_graph.get_path_between(arriving_locator, packet.dest_locator)

            if known_path is None:
                logging.debug("Forwarding route request")
                self.forward_route_request(packet, arriving_locator)
            else:
                logging.debug("Replying to route request with cached path {}".format(known_path))
                rreq.append_locators(known_path)
                self.reply_to_route_request(rreq, (packet.src_locator, packet.src_identifier))

    def forward_route_request(self, packet, arriving_locator):
        logging.debug("Appending arriving locator and forwarding route request")
        packet.payload.body.append_locator(arriving_locator)
        packet.payload_length = packet.payload_length + RouteList.LOCATOR_SIZE
        self.router.flood_to_neighbours(packet, arriving_locator)

    def add_path_to_forwarding_table(self, locators, arriving_locator):
        logging.debug("Adding the following path to forwarding table: {}".format(locators))
        length_of_path = len(locators)

        for index, locator in enumerate(locators):
            self.forwarding_table.add_entry(locator, arriving_locator, length_of_path)
            if index < len(locators) - 1:
                self.network_graph.add_vertex(locator, locators[index + 1])

            length_of_path -= 1

    def handle_route_reply(self, packet, arriving_locator):
        rrep = packet.payload.body
        self.add_path_to_forwarding_table(rrep.locators, arriving_locator)

        if self.router.is_for_me(packet):
            if rrep.request_id in self.awaiting_route:
                logging.debug("Found path for packet from route reply, routing now!")
                waiting_packet = self.awaiting_route.pop(rrep.request_id)
                self.router.route_packet(waiting_packet, None)

                # Route any other packets for same destination
                logging.debug("Routing other packets for the given destination")
                also_waiting_for_dest = self.pop_packets_waiting_for_dest(packet.dest_locator)
                for packet in also_waiting_for_dest:
                    self.router.route_packet(packet)

            else:
                logging.debug("Discarding route reply as old request_id present")
        else:
            logging.debug("Forwarding route reply")
            self.router.route_packet(packet, arriving_locator)

    def pop_packets_waiting_for_dest(self, locator):
        """
        Removes and returns a list of all packets with the given locator as a destination.
        :param locator: destination locator
        :return: A list of all packets currently waiting on a route reply for the given locator destination
        """
        request_ids_for_dest = [request_id for request_id, packet in self.awaiting_route.items()
                                if packet.dest_locator == locator]
        return [self.awaiting_route.pop(request_id) for request_id in request_ids_for_dest]

    def reply_to_route_request(self, rreq, destination):
        reply = self.build_route_reply_packet(rreq, destination)
        self.router.route_packet(reply)

    def get_next_hop(self, dest_locator, arriving_interface):
        """
        Provides a set of next hops to send the packet to get it to its destination. The arriving interface if provided
        will be removed to avoid the packet being pointlessly sent the way it came.

        :param dest_locator: locator address packet is destined for
        :param arriving_interface: locator interface that packet arrived on
        :return: list of viable next hops that should lead to the packets destination
        """
        # TODO
        next_hops = self.forwarding_table.get_next_hop_list(dest_locator)

        if arriving_interface in next_hops:
            next_hops.remove(arriving_interface)

        if len(next_hops) > 0:
            return random.choice(next_hops)
        else:
            return None

    def backwards_learn(self, src_loc: int, arriving_loc: int):
        # TODO
        pass

    def stop(self):
        # TODO
        pass


class NetworkGraph:
    def __init__(self, initial_locators):
        self.nodes = {}

        for locator in initial_locators:
            self.nodes[locator] = {loc for loc in initial_locators if loc != locator}

    def get_path_between(self, start, end, path=None):
        """Finds a path between the start and end node. Not necessarily the shortest"""
        if path is None:
            path = []

        path.append(start)

        if start == end:
            return path
        if not self.node_exists(start):
            return None

        for node in self.nodes[start]:
            if node not in path:
                new_path = self.get_path_between(node, end, path)
                if new_path:
                    return new_path

        return None

    def node_exists(self, node):
        return node in self.nodes

    def add_node(self, node):
        self.nodes[node] = set()

    def add_vertex(self, start, end):
        if not self.node_exists(start):
            self.add_node(start)

        if not self.node_exists(end):
            self.add_node(end)

        self.nodes[start].add(end)
        self.nodes[end].add(start)

    def remove_vertex(self, start, end):
        if self.node_exists(start) and self.node_exists(end):
            self.nodes[start].remove(end)


def create_request_id():
    """
    Generates a request id and increments the current value, ensuring that it can be stored in a single byte.
    :return: request_id
    """
    return random.getrandbits(8)
