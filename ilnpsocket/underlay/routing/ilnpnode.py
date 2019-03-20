import logging
import random
import threading
import time
from os import urandom
from struct import unpack
from typing import Dict, List, Iterable, Optional

from experiment.config import Config
from experiment.tools import Monitor
from ilnpsocket.underlay.routing.dsrmessages import DSRHeader, DSRMessage, LOCATOR_SIZE, RouteRequest, RouteReply, \
    RouteError
from ilnpsocket.underlay.routing.dsrutil import NetworkGraph, RequestRecords, RecentRequestBuffer, DestinationQueues, \
    RequestIdGenerator
from ilnpsocket.underlay.routing.forwardingtable import ForwardingTable, NextHopList, ForwardingEntry
from ilnpsocket.underlay.routing.ilnp import ILNPPacket, DSR_NEXT_HEADER_VALUE, AddressHandler, ILNPAddress, \
    is_control_packet
from ilnpsocket.underlay.routing.listeningthread import ListeningThread
from ilnpsocket.underlay.routing.queues import ReceivedQueue, PacketQueue
from ilnpsocket.underlay.routing.serializable import Serializable
from ilnpsocket.underlay.sockets.listeningsocket import ListeningSocket
from ilnpsocket.underlay.sockets.sendingsocket import SendingSocket


def create_receivers(locators_to_ipv6: Dict[int, str], port_number: int) -> List[ListeningSocket]:
    """Creates a listening socket instance for each locator-ipv6 key value pair"""
    return [ListeningSocket(ipv6_address, port_number, locator)
            for locator, ipv6_address
            in locators_to_ipv6.items()]


def create_random_id() -> int:
    """
    Uses the OSs RNG to produce an id for this node.
    :return: a 64 bit id with low likelihood of collision
    """
    return unpack("!Q", urandom(8))[0]


class ILNPNode(threading.Thread):
    def __init__(self, conf: Config, received_packets_queue: ReceivedQueue, monitor: Monitor):
        super(ILNPNode, self).__init__()

        self.__stop_event: threading.Event() = threading.Event()

        logging.debug("Configuring address handler")
        self.address_handler: AddressHandler = AddressHandler(
            conf.my_id if conf.my_id is not None else create_random_id(), {int(l) for l in conf.locators_to_ipv6})

        self.__to_be_routed_queue: PacketQueue = PacketQueue()
        self.__received_packets_queue = received_packets_queue

        # Configures listening thread
        receivers = create_receivers(conf.locators_to_ipv6, conf.port)
        self.__listening_thread = ListeningThread(receivers, self.__to_be_routed_queue, conf.packet_buffer_size_bytes)

        # Ensures that child threads die with parent
        logging.debug("Starting listening thread")
        self.__listening_thread.daemon = True
        self.__listening_thread.start()
        self.monitor = monitor

        # Configures router
        logging.debug("Configuring router")
        self.router = Router(self.address_handler, self.__received_packets_queue, conf, monitor)

    def run(self):
        """Polls for messages."""
        while not self.__stop_event.is_set() and (self.monitor is None or self.monitor.max_sends > 0):
            logging.debug("Polling for packet...")

            packet: ILNPPacket
            arriving_loc: int
            packet, arriving_loc = self.__to_be_routed_queue.get(block=True)

            logging.debug("from %s, packet arrived: %s", arriving_loc, packet)

            self.handle_packet(packet, arriving_loc)
            self.__to_be_routed_queue.task_done()

    def stop(self):
        logging.debug("Terminating")
        self.__stop_event.set()
        logging.debug("Ending listening thread")
        self.__listening_thread.stop()
        logging.debug("Waiting for listening thread to join")
        self.__listening_thread.join()
        logging.debug("Closing sending socket")
        self.router.sender.close()
        logging.debug("Terminating maintenance thread")
        self.router.maintenance_thread.stop()

    def handle_packet(self, packet: ILNPPacket, arriving_loc: int):
        if not self.address_handler.is_from_me(packet) and arriving_loc is not None:
            logging.debug("Backwards learning from packet src and arriving loc")
            self.router.backwards_learn(packet.src.loc, arriving_loc)

        if is_control_packet(packet):
            logging.debug("Processing as control packet")
            self.router.handle_control_packet(packet, arriving_loc)
        else:
            logging.debug("Processing as data packet")
            self.router.route_packet(packet, arriving_loc)

    def send_from_host(self, payload: bytes, destination: ILNPAddress):
        self.__to_be_routed_queue.add(self.router.construct_host_packet(payload, destination))


class Router:
    MAX_NUM_RETRIES = 5
    TIME_BEFORE_RETRY = 10

    def __init__(self, address_handler: AddressHandler,
                 received_packets_queue: ReceivedQueue, conf: Config, monitor: Monitor):
        # Data Plane Config
        self.address_handler: AddressHandler = address_handler
        self.received_packets_queue: ReceivedQueue = received_packets_queue
        self.sender = SendingSocket(conf.port, conf.locators_to_ipv6, conf.loopback)
        self.hop_limit: int = conf.hop_limit

        self.monitor: Monitor = monitor

        # Control Plane Config
        self.request_id_generator: RequestIdGenerator = RequestIdGenerator()

        # Buffers
        self.destination_queues: DestinationQueues = DestinationQueues()
        self.requests_made: RequestRecords = RequestRecords()
        self.recently_seen_request_ids: RecentRequestBuffer = RecentRequestBuffer()

        # Network Knowledge
        self.forwarding_table: ForwardingTable = ForwardingTable()
        self.network_graph: NetworkGraph = self.init_network_graph()
        logging.debug("Initial network graph: %s", str(self.network_graph))

        # Maintenance
        logging.debug("Initializing and starting router maintenance thread")
        self.maintenance_thread: MaintenanceThread = MaintenanceThread(self, conf.router_refresh_delay_secs)
        self.maintenance_thread.daemon = True
        self.maintenance_thread.start()

        self.handler_functions = {
            RouteRequest.TYPE: self.__handle_route_request,
            RouteReply.TYPE: self.__handle_route_reply,
            RouteError.TYPE: self.__handle_route_error,
        }

    def construct_host_packet(self, payload: bytes, dest: ILNPAddress, src: Optional[ILNPAddress] = None) -> ILNPPacket:
        if src is None:
            src = ILNPAddress(self.address_handler.my_id, self.address_handler.get_random_src_locator())

        return ILNPPacket(src,
                          dest,
                          payload=payload,
                          payload_length=len(payload),
                          hop_limit=self.hop_limit)

    def route_packet(self, packet: ILNPPacket, arriving_interface: int = None):
        if self.address_handler.is_my_locator(packet.dest.loc):
            logging.debug("Packet destined for adjacent node")
            self.route_to_adjacent_node(packet, arriving_interface)
        else:
            logging.debug("Packet destined for remote node")
            self.route_to_remote_node(packet, arriving_interface)

    def route_to_remote_node(self, packet: ILNPPacket, arriving_interface: int):
        logging.debug("Routing packet to remove node")
        next_hop_locator: int = self.get_next_hop(packet.dest.loc, arriving_interface)

        if next_hop_locator is not None:
            logging.debug("Forwarding packet to %d.", next_hop_locator)
            self.forward_packet_to_addresses(packet, [next_hop_locator])
        if arriving_interface is None:
            logging.debug("No route found, sourcing route.")
            self.find_route_for_packet(packet)
        else:
            logging.debug("No route found: Packet discarded.")

    def route_to_adjacent_node(self, packet: ILNPPacket, arriving_interface: int):
        if self.address_handler.is_for_me(packet):
            logging.debug("Packet for me: payload extracted")
            self.received_packets_queue.add(packet.payload)
        elif packet.dest.loc != arriving_interface or arriving_interface is None:
            logging.debug("Forwarding packet to final dest %d", packet.dest.loc)
            self.forward_packet_to_addresses(packet, [packet.dest.loc])

    def flood_to_neighbours(self, packet: ILNPPacket, arriving_interface: int = None):
        logging.debug("Flooding all interfaces other than %d", arriving_interface)
        next_hops = [x for x in self.address_handler.my_locators]

        if arriving_interface in next_hops:
            next_hops.remove(arriving_interface)

        self.forward_packet_to_addresses(packet, next_hops)

    def forward_packet_to_addresses(self, packet: ILNPPacket, next_hop_locators: Iterable[int], decrement_hop=True):
        """
        Forwards packet to locator with given value if hop limit is still greater than 0.
        Decrements hop limit by one before forwarding.
        :param packet: packet to forward
        :param next_hop_locators: set of locators (interfaces) to forward packet to
        :param decrement_hop if true, the TTL in the packet will be decremented once before sending
        """
        if self.monitor and self.monitor.max_sends <= 0:
            logging.debug("Max sends reached. Cannot send.")
            return

        if packet.hop_limit <= 0:
            logging.debug("TTL expired: packet discarded")
            return

        if decrement_hop:
            logging.debug("TTL decremented")
            packet.decrement_hop_limit()

        forwarded = not self.address_handler.is_from_me(packet)
        packet_bytes = bytes(packet)
        for locator in next_hop_locators:
            logging.debug("Forwarding to %d", locator)
            self.sender.sendTo(packet_bytes, locator)

            if self.monitor:
                logging.debug("Recording sent packet")
                self.monitor.record_sent_packet(packet, forwarded)
                if self.monitor.max_sends <= 0:
                    logging.debug("Max sends reached")
                    return

    def init_network_graph(self) -> NetworkGraph:
        logging.debug("Initializing network graph")
        return NetworkGraph(self.address_handler.my_locators)

    def retry_old_requests(self):
        logging.debug("Retrying old requests")
        to_be_retried = []
        for request in self.requests_made.pop_records_older_than(self.TIME_BEFORE_RETRY):
            if request.num_attempts < self.MAX_NUM_RETRIES:
                logging.debug("Request for dest %d due to be retried", request.dest_loc)
                to_be_retried.append(request)
            else:
                # Discard and assume loss of connection to locator
                logging.debug("Assuming loss of connection to %d", request.dest_loc)
                self.destination_queues.pop_dest_queue(request.dest_loc)
                self.network_graph.remove_node(request.dest_loc)

        for request in to_be_retried:
            # Takes destination ID of first packet for routing, though any node in that locator can reply with path
            dest_loc = request.dest_loc
            dest_id = self.destination_queues[dest_loc][0].dest.id
            logging.debug("Sending RREQ to %d:%d", dest_loc, dest_id)
            self.__send_route_request(ILNPAddress(dest_loc, dest_id), request.num_attempts)

    def __create_rreq(self, dest_loc: int) -> RouteRequest:
        request_id = next(self.request_id_generator)
        logging.debug("Creating rreq with id %d for dest %d", request_id, dest_loc)
        return RouteRequest.build(request_id, dest_loc)

    def __send_route_request(self, dest_addr: ILNPAddress, num_attempts: int = 0, arriving_interface: int = None):
        rreq = self.__create_rreq(dest_addr.loc)
        dsr_message = create_dsr_message(rreq)

        next_hops = [x for x in self.address_handler.my_locators]
        if arriving_interface in next_hops:
            next_hops.remove(arriving_interface)

        packet = self.construct_host_packet(bytes(dsr_message), dest_addr)
        packet.next_header = DSR_NEXT_HEADER_VALUE
        for next_hop in next_hops:
            packet.src.loc = next_hop
            self.forward_packet_to_addresses(packet, [next_hop], False)

        self.requests_made.add(rreq.request_id, dest_addr.loc, num_attempts + 1)

    def __send_route_reply(self, original_packet: ILNPPacket, rreq: RouteRequest, arrived_from_locator: int):
        rrply = RouteReply.build(rreq, original_packet.src.loc, original_packet.dest.loc)
        logging.debug("rrply built with path: %s", rrply.route_list.locators)
        msg = create_dsr_message(rrply)

        packet = self.construct_host_packet(bytes(msg), original_packet.src, original_packet.dest)
        packet.next_header = DSR_NEXT_HEADER_VALUE

        self.forward_packet_to_addresses(packet, [arrived_from_locator])

    def find_route_for_packet(self, packet: ILNPPacket):
        dest_loc = packet.dest.loc

        if dest_loc not in self.destination_queues:
            logging.debug("Not already waiting for dest: beginning route request")
            self.__send_route_request(packet.dest)

        logging.debug("Adding packet to destination queue for %d", dest_loc)
        self.destination_queues.add_packet(packet)

    def handle_control_packet(self, packet: ILNPPacket, arrived_from_locator: int):
        if packet.next_header is not DSR_NEXT_HEADER_VALUE:
            logging.error("Unknown next header value")
            return

        dsr_bytes = memoryview(packet.payload)[:packet.payload_length]
        dsr_message = DSRMessage.from_bytes(dsr_bytes)
        for message in dsr_message.messages:
            logging.debug("Calling handler function")
            self.handler_functions[message.TYPE](packet, dsr_message, message, arrived_from_locator)

    def __handle_route_error(self, packet: ILNPPacket, dsr_message: DSRMessage, message: RouteError,
                             arrived_from_locator: int):
        logging.debug("Handling route error")
        pass  # TODO

    def __send_packets(self, packets: List[ILNPPacket], next_hop: int):
        logging.debug("Sending %d packets to %d", len(packets), next_hop)
        for packet in packets:
            self.forward_packet_to_addresses(packet, [next_hop])

    def __forward_route_request(self, packet: ILNPPacket, dsr_message: DSRMessage, message: RouteRequest,
                                black_list: List[int]):
        next_hops = [next_hop for next_hop in self.address_handler.my_locators if next_hop not in black_list]
        original_list = message.route_list.locators.copy()
        logging.debug("Forwarding rreq to %s", next_hops)

        for next_hop in next_hops:
            message.route_list.locators = original_list + [next_hop]

            message.data_len += LOCATOR_SIZE
            dsr_message.header.payload_length += LOCATOR_SIZE
            packet.payload_length += LOCATOR_SIZE
            packet.payload = bytes(dsr_message)

            logging.debug("Forwarding rreq with path %s", message.route_list.locators)
            self.forward_packet_to_addresses(packet, [next_hop], False)

    def __update_route_cache_and_attempt_send(self, new_path: List[int], arrived_from_locator: int):
        logging.debug("Updating route cache using path %s arriving from %d", new_path, arrived_from_locator)
        self.network_graph.add_path(new_path)
        for locator in new_path:
            if locator in self.destination_queues:
                logging.debug("Path found to %d: Sending waiting packets on interface %d", locator,
                              arrived_from_locator)
                self.__send_packets(self.destination_queues.pop_dest_queue(locator), arrived_from_locator)
                self.requests_made.pop_by_dest(locator)

    def __reply_with_cached_path(self, packet: ILNPPacket, dsr_message: DSRMessage, rreq: RouteRequest,
                                 cached_path: List[int], arrived_from_locator: int):
        # Set path omitting src since these are appended by the rrply builder
        orig_size = rreq.size_bytes()
        rreq.route_list.locators = cached_path[1:]
        # Update packet length fields
        rreq.refresh_data_len()
        size_diff = rreq.size_bytes() - orig_size
        dsr_message.header.payload_length += size_diff
        packet.payload_length += size_diff

        self.__send_route_reply(packet, rreq, arrived_from_locator)

    def __handle_route_request(self, packet: ILNPPacket, dsr_message: DSRMessage, rreq: RouteRequest,
                               arrived_from_locator: int):
        logging.debug("Handling route request")
        full_path = [packet.src.loc] + rreq.route_list.locators
        logging.debug("RREQ contains path %s", full_path)
        self.__update_route_cache_and_attempt_send(full_path, arrived_from_locator)

        # Reply if for me
        if self.address_handler.is_for_me(packet):
            logging.debug("For me: replying")
            self.__send_route_reply(packet, rreq, arrived_from_locator)
        # Discard if seen recently
        elif (packet.src.id, rreq.request_id) in self.recently_seen_request_ids:
            logging.debug("Seen request with id %d from src %d recently: discarding", packet.src.id, rreq.request_id)
            return

        # Attempt to reply with cached path
        cached_path = self.network_graph.get_shortest_path(packet.src.loc, packet.dest.loc)

        if cached_path:
            logging.debug("Replying with cached path: %s", cached_path)
            self.__reply_with_cached_path(packet, dsr_message, rreq, cached_path, arrived_from_locator)
        else:
            logging.debug("No cached path: forwarding to all unvisited locators")
            self.__forward_route_request(packet, dsr_message, rreq, full_path)

        logging.debug("Recording request id %d", rreq.request_id)
        self.recently_seen_request_ids.add(packet.src.id, rreq.request_id)

    def __handle_route_reply(self, packet: ILNPPacket, dsr_message: DSRMessage, rrply: RouteReply,
                             arrived_from_locator: int):
        logging.debug("Handling route reply")
        full_path = rrply.route_list.locators
        self.__update_route_cache_and_attempt_send(full_path, arrived_from_locator)

        # Attempt to suggest better path before forwarding if not for me
        if not self.address_handler.is_for_me(packet):
            logging.debug("Attempting to get better path")
            better_path = self.network_graph.get_shortest_path(full_path[0], full_path[len(full_path) - 1])
            logging.debug("Path found: %s", better_path)
            if len(better_path) < len(full_path):
                logging.debug("Replacing original path")
                rrply.change_route_list(better_path)
                dsr_message.header.payload_length = rrply.size_bytes()
                packet.payload_length = dsr_message.size_bytes()
                packet.payload = bytes(dsr_message)

            logging.debug("Forwarding rrply to dest")
            self.route_packet(packet, arrived_from_locator)

    def __simplify_path(self, existing_route: List[int]):
        if len(existing_route) == 1:
            logging.debug("No more possibility to simplify path")
            return existing_route

        my_locs = self.address_handler.my_locators

        # Remove first hop if directly interfaced with second hop
        if existing_route[1] in my_locs:
            logging.debug("Removing first hop %d since directly interfaced with second hop %d", existing_route[0],
                          existing_route[1])
            existing_route[:] = existing_route[1:]
            return self.__simplify_path(existing_route)
        else:
            logging.debug("Finished simplifying route")
            return existing_route

    def get_next_hop(self, dest_locator: int, arriving_interface: int) -> Optional[int]:
        """
        Provides a set of next hops to send the packet to get it to its destination. The arriving interface if provided
        will be removed to avoid the packet being pointlessly sent the way it came.

        :param dest_locator: locator address packet is destined for
        :param arriving_interface: locator interface that packet arrived on
        :return: list of viable next hops that should lead to the packets destination
        """
        # Check if next hop in forwarding table
        if dest_locator in self.forwarding_table:
            logging.debug("Destination in forwarding table")
            next_hops: Dict[int, ForwardingEntry] = self.forwarding_table.get_next_hop_list(dest_locator).entries
            next_hop: int = random.choice(list(next_hops.values())).next_hop_locator
            logging.debug("Random next hop chosen from %s: %d", next_hops.values(), next_hop)
            return next_hop
        else:
            # Check if route exists in current network topology knowledge
            logging.debug("Checking if route can be found from known topology")
            existing_route = self.network_graph.get_shortest_path(arriving_interface, dest_locator)
            if existing_route:
                logging.debug("Found route in cache!: %s", existing_route)
                existing_route = self.__simplify_path(existing_route)
                logging.debug("Route simplified to %s", existing_route)
                next_hop = existing_route[0]
                # Add missing entry to forwarding table
                self.forwarding_table.add_or_update_entry(dest_locator, next_hop, len(existing_route))
                logging.debug("Next hop: %d", next_hop)
                return next_hop
            else:
                logging.debug("Unable to determine next hop")
                return None

    def backwards_learn(self, src_loc: int, arriving_loc: int):
        self.forwarding_table.add_or_update_entry(src_loc, arriving_loc)


class MaintenanceThread(threading.Thread):

    def __init__(self, router: Router, maintenance_interval: int):
        super().__init__()
        self.stopped = threading.Event()
        self.router = router
        self.maintenance_interval = maintenance_interval

    def stop(self):
        logging.debug("Stopping event set in maintenance thread")
        self.stopped.set()

    def run(self):
        """
        Repeated maintenance tasks
        """
        while not self.stopped.is_set():
            logging.debug("Maintenance thread woke")
            # Log current status
            logging.debug("Current status:")
            logging.debug("Forwarding table:")
            logging.debug(str(self.router.forwarding_table))
            logging.debug("Network graph:")
            logging.debug(str(self.router.network_graph))
            logging.debug("Destination queues:")
            logging.debug(str(self.router.destination_queues))
            logging.debug("Requests made:")
            logging.debug(str(self.router.requests_made))
            logging.debug("End of current status")

            # Age and clear network graph once unreliable
            logging.debug("Aging forwarding table")
            nodes_have_expired = self.router.forwarding_table.decrement_and_clear()
            if nodes_have_expired:
                logging.debug("Destinations possibly lost, clearing network graph")
                self.router.network_graph = self.router.init_network_graph()

            logging.debug("Aging currently waiting requests")
            self.router.requests_made.age_records()
            logging.debug("Attemtping to retry requests")
            self.router.retry_old_requests()

            # Sleep
            logging.debug("Maintenance thread sleeping")
            time.sleep(self.maintenance_interval)


def create_dsr_message(message: Serializable) -> DSRMessage:
    header = DSRHeader.build(message.size_bytes())
    return DSRMessage(header, [message])
