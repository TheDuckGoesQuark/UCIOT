import collections
import threading
import logging
from os import urandom
from queue import Queue
from struct import unpack

from ilnpsocket.underlay.listeningthread import ListeningThread
from ilnpsocket.underlay.icmp.dsr import RouteRequest, RouteReply
from ilnpsocket.underlay.icmp.icmpheader import ICMPHeader
from ilnpsocket.underlay.packet import Packet
from ilnpsocket.underlay.routing.forwardingtable import ForwardingTable
from ilnpsocket.underlay.sockets.listeningsocket import ListeningSocket
from ilnpsocket.underlay.sockets.sendingsocket import SendingSocket


def create_receivers(locators_to_ipv6, port_number):
    """Creates a listening socket instance for each locator-ipv6 key value pair"""
    return [ListeningSocket(address, port_number, int(locator))
            for locator, address
            in locators_to_ipv6.items()]


def create_random_id():
    """
    Uses the OSs RNG to produce an id for this node.
    :return: a 64 bit id with low likelihood of collision
    """
    return unpack("!Q", urandom(8))[0]


class Router(threading.Thread):
    def __init__(self, conf, received_packets_queue):
        super(Router, self).__init__()

        self.hop_limit = conf.hop_limit

        # Assign addresses to this node
        if conf.my_id:
            self.my_id = conf.my_id
        else:
            self.my_id = create_random_id()

        self.hop_limit = conf.hop_limit
        self.interfaced_locators = {int(l) for l in conf.locators_to_ipv6}

        # packets awaiting routing or route reply
        self.__to_be_routed_queue = Queue()

        # packets for the current node
        self.__received_packets_queue = received_packets_queue

        # Create sending socket
        self.__sender = SendingSocket(conf.port, conf.locators_to_ipv6, conf.loopback)

        # Configures listening thread
        receivers = create_receivers(conf.locators_to_ipv6, conf.port)
        self.__listening_thread = ListeningThread(receivers, self, conf.packet_buffer_size_bytes)

        # Ensures that child threads die with parent
        self.__listening_thread.daemon = True
        self.__listening_thread.start()

        # Configures routing service and forwarding table
        self.forwarding_table = ForwardingTable(conf.router_refresh_delay_secs)
        self.dsr_service = DSRService(self.forwarding_table, self)

    def add_to_route_queue(self, packet_to_route, arriving_locator=None):
        """
        Adds the given packet to the queue waiting to be routed, alongside the locator value the packet arrived from.
        Defaults to None when the packet was created locally.

        :param packet_to_route: packet instance to be routed
        :param arriving_locator: locator value that packet arrived from
        """
        self.__to_be_routed_queue.put((packet_to_route, arriving_locator))

    def get_addresses(self):
        """
        If no interfaces are configured, a ValueError is raised as no address exists.
        :return: a list of tuples of locator:identifier pairs that can be used as an address for this host.
        """
        if self.interfaced_locators is None or len(self.interfaced_locators) == 0:
            raise ValueError("An address cannot be obtained as this router has no interfaces.")
        else:
            return [(locator, self.my_id) for locator in self.interfaced_locators]

    def construct_host_packet(self, payload, destination):
        """
        Constructs a packet from this host to the given destination with the given payload
        :param payload: bytes to be sent
        :param destination: destination as (locator:identifier) tuple
        :return: Packet from this host to the given destination carrying the given payload
        """
        if len(payload) > Packet.MAX_PAYLOAD_SIZE:
            raise ValueError("Payload cannot exceed {} bytes. "
                             "Provided payload size: {} bytes. ".format(Packet.MAX_PAYLOAD_SIZE, len(payload)))

        packet = Packet(self.get_addresses()[0], destination,
                        payload=payload, payload_length=len(payload), hop_limit=self.hop_limit)

        return packet

    def run(self):
        """Polls for messages."""
        while True:
            logging.debug("Polling for packet...")
            packet, locator_interface = self.__to_be_routed_queue.get(block=True)

            if type(packet) is not Packet:
                continue

            if not self.is_from_me(packet):
                self.forwarding_table.record_entry(packet.src_locator, locator_interface, self.hop_limit - packet.hop_limit)

            if packet.is_control_message():
                logging.debug("Received control message from {}-{} for {} {} on interface {}"
                              .format(packet.src_locator, packet.src_identifier,
                                      packet.dest_locator, packet.dest_identifier, locator_interface))
                self.dsr_service.handle_message(packet, locator_interface)
            else:
                logging.debug("Received normal packet from {}-{} for {} {} on interface {}"
                              .format(packet.src_locator, packet.src_identifier,
                                      packet.dest_locator, packet.dest_identifier, locator_interface))
                self.route_packet(packet, locator_interface)

            self.__to_be_routed_queue.task_done()

    def is_my_address(self, locator, identifier):
        return (locator in self.interfaced_locators) and identifier == self.my_id

    def is_from_me(self, packet):
        return self.is_my_address(packet.src_locator, packet.src_identifier)

    def is_for_me(self, packet):
        return self.is_my_address(packet.dest_locator, packet.dest_identifier)

    def interface_exists_for_locator(self, locator):
        return locator in self.interfaced_locators

    def get_next_hops(self, dest_locator, arriving_interface):
        """
        Provides a set of next hops to send the packet to get it to its destination. The arriving interface if provided
        will be removed to avoid the packet being pointlessly sent the way it came.

        :param dest_locator: locator address packet is destined for
        :param arriving_interface: locator interface that packet arrived on
        :return: list of viable next hops that should lead to the packets destination
        """
        next_hops = self.forwarding_table.find_next_hops(dest_locator)

        if arriving_interface in next_hops:
            next_hops.remove(arriving_interface)

        return next_hops

    def route_packet(self, packet, arriving_interface=None):
        """
        Attempts to either receive packets for this node, or to forward packets to their destination.

        If a path isn't found, its handed over to the DSR service to find a path.
        :param arriving_interface: interface packet arrived on. If not given or None, packet will be assumed
        to have been created by the host.

        :param packet: packet to be routed
        """
        if self.interface_exists_for_locator(packet.dest_locator):
            if self.is_for_me(packet):
                logging.debug("Packet added to received queue")
                self.__received_packets_queue.put(packet)
            elif packet.dest_locator is not arriving_interface:
                logging.debug("Packet being forwarded to final destination")
                # Packet needs forwarded to destination
                self.forward_packet_to_addresses(packet, [packet.dest_locator])
            elif self.is_from_me(packet) and arriving_interface is None:
                logging.debug("Packet being broadcast to my locator group {}".format(packet.dest_locator))
                # Packet from host needing broadcast to locator
                self.forward_packet_to_addresses(packet, [packet.dest_locator])
        else:
            next_hop_locators = self.get_next_hops(packet.dest_locator, arriving_interface)

            if len(next_hop_locators) is 0 and arriving_interface is None:
                logging.debug("No route found, requesting one.")
                self.dsr_service.find_route_for_packet(packet)
            else:
                self.forward_packet_to_addresses(packet, next_hop_locators)

    def flood(self, packet, arriving_interface):
        logging.debug("Flooding packet")
        next_hops = self.interfaced_locators

        if arriving_interface in next_hops:
            next_hops.remove(arriving_interface)

        self.forward_packet_to_addresses(packet, next_hops)

    def forward_packet_to_addresses(self, packet, next_hop_locators):
        """
        Forwards packet to locator with given value if hop limit is still greater than 0.
        Decrements hop limit by one before forwarding.
        :param packet: packet to forward
        :param next_hop_locators: set of locators (interfaces) to forward packet to
        """
        if packet.hop_limit > 0:
            logging.debug("Forwarding packet to the following locator(s): {}".format(next_hop_locators))
            packet.decrement_hop_limit()
            packet_bytes = bytes(packet)
            for locator in next_hop_locators:
                self.__sender.sendTo(packet_bytes, locator)
        else:
            logging.debug("Packet dropped. Hop limit reached")

    def __exit__(self):
        """Closes sockets and joins thread upon exit"""
        self.__listening_thread.stop()
        self.__listening_thread.join()
        self.__sender.close()


class DSRService:
    """
    DSR service handles route request and reply messages, and updates the forwarding table with relevant information
    """

    def __init__(self, forwarding_table, router):
        """
        Initializes DSRService with forwarding table which it will maintain with information it gains from routing
        messages.
        :type router: Router
        :param router: router that can be used to forward any control messages
        :type forwarding_table: ForwardingTable
        :param forwarding_table: forwarding table to update when routing information is available
        """
        self.awaiting_route = {}
        self.router = router
        self.forwarding_table = forwarding_table
        self.request_id_counter = 1
        # Fixed size list of request ids to track those that have already been seen
        self.recent_request_ids = collections.deque(5 * [0], 5)
        self.network_graph = NetworkGraph(self.router.interfaced_locators)

    def is_recently_seen_id(self, request_id):
        return request_id in self.recent_request_ids

    def create_request_id(self):
        """
        Generates a request id and increments the current value, ensuring that it can be stored in a single byte.
        :return: request_id
        """
        current_val = self.request_id_counter
        self.request_id_counter = (current_val + 1) % 255

        if self.request_id_counter == 0:
            self.request_id_counter += 1

        return current_val

    def find_route_for_packet(self, packet):
        request_id = self.create_request_id()
        self.awaiting_route[request_id] = packet
        request_packet = self.build_route_request_packet(request_id, (packet.dest_locator, packet.dest_identifier))
        self.router.forward_packet_to_addresses(request_packet, self.router.interfaced_locators)

    def build_route_request_packet(self, request_id, destination):
        rreq = RouteRequest(0, request_id, [])
        icmp_message = ICMPHeader(rreq.TYPE, 0, 0, bytes(rreq))
        packet = self.router.construct_host_packet(bytes(icmp_message), destination)
        packet.next_header = ICMPHeader.NEXT_HEADER_VALUE
        return packet

    def build_route_reply_packet(self, rreq, destination, arriving_locator):
        rrply = RouteReply(0, rreq.request_id, rreq.locators)
        rrply.append_locator(arriving_locator)
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
            self.reply_to_route_request(rreq, (packet.src_locator, packet.src_identifier), arriving_locator)
        elif not self.is_recently_seen_id(rreq.request_id) and not rreq.already_in_list(arriving_locator):
            known_path = self.network_graph.get_path_between(arriving_locator, packet.dest_locator)

            if known_path is None:
                logging.debug("Forwarding route request")
                self.forward_route_request(packet, arriving_locator)
            else:
                logging.debug("Replying to route request with cached path")
                rreq.locators.extend(known_path) # TODO doesnt add self when path is literally beside them!
                self.reply_to_route_request(rreq, (packet.src_locator, packet.src_identifier), arriving_locator)

    def forward_route_request(self, packet, arriving_locator):
        logging.debug("Appending arriving locator and forwarding route request")
        packet.payload.body.append_locator(arriving_locator)
        self.router.flood(packet, arriving_locator)

    def add_path_to_forwarding_table(self, locators, arriving_locator):
        logging.debug("Adding the following path to forwarding table: {}".format(locators))
        length_of_path = len(locators)

        for index, locator in enumerate(locators):
            self.forwarding_table.record_entry(locator, arriving_locator, length_of_path)
            if index < len(locator) - 1:
                self.network_graph.add_vertex(locator, locators[index+1])

            length_of_path -= 1

    def handle_route_reply(self, packet, arriving_locator):
        rrep = packet.payload.body
        self.add_path_to_forwarding_table(rrep.locators, arriving_locator)

        if self.router.is_for_me(packet):
            if rrep.request_id in self.awaiting_route:
                logging.debug("Found path for packet from route reply, routing now!")
                waiting_packet = self.awaiting_route.pop(rrep.request_id)
                self.router.route_packet(waiting_packet, None)
            else:
                logging.debug("Discarding route reply as old request_id present")
        else:
            logging.debug("Forwarding route reply")
            self.router.route_packet(packet, arriving_locator)

    def reply_to_route_request(self, rreq, destination, arriving_locator):
        reply = self.build_route_reply_packet(rreq, destination, arriving_locator)
        self.router.route_packet(reply)


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

