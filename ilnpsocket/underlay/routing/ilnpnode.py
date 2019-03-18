import logging
import random
import threading
import time
from os import urandom
from struct import unpack
from typing import Dict, List, Iterable, Optional

from experiment.config import Config
from experiment.tools import Monitor
from ilnpsocket.underlay.routing.ilnp import ILNPPacket, DSR_NEXT_HEADER_VALUE, AddressHandler, ILNPAddress
from ilnpsocket.underlay.routing.listeningthread import ListeningThread
from ilnpsocket.underlay.routing.queues import ReceivedQueue, PacketQueue
from ilnpsocket.underlay.sockets.listeningsocket import ListeningSocket
from ilnpsocket.underlay.sockets.sendingsocket import SendingSocket
from ilnpsocket.underlay.routing.dsrmessages import DSRHeader, DSRMessage, LOCATOR_SIZE, RouteRequest, RouteReply, \
    RouteError
from ilnpsocket.underlay.routing.serializable import Serializable
from ilnpsocket.underlay.routing.dsrutil import NetworkGraph, RequestRecords, RecentRequestBuffer, DestinationQueues, \
    RequestIdGenerator
from ilnpsocket.underlay.routing.forwardingtable import ForwardingTable


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


def is_control_packet(packet: ILNPPacket) -> bool:
    return packet.next_header == DSR_NEXT_HEADER_VALUE


class ILNPNode(threading.Thread):
    def __init__(self, conf: Config, received_packets_queue: ReceivedQueue, monitor: Monitor):
        super(ILNPNode, self).__init__()

        self.__stop_event: threading.Event() = threading.Event()

        self.address_handler: AddressHandler = AddressHandler(
            conf.my_id if conf.my_id is not None else create_random_id(), {int(l) for l in conf.locators_to_ipv6})

        self.__to_be_routed_queue: PacketQueue = PacketQueue()
        self.__received_packets_queue = received_packets_queue

        # Configures listening thread
        receivers = create_receivers(conf.locators_to_ipv6, conf.port)
        self.__listening_thread = ListeningThread(receivers, self.__to_be_routed_queue, conf.packet_buffer_size_bytes)

        # Ensures that child threads die with parent
        self.__listening_thread.daemon = True
        self.__listening_thread.start()

        # Configures routing and control plane service
        self.router = Router(self.address_handler, self.dsr_service, self.__received_packets_queue, conf, self.monitor)
        self.dsr_service = DSRService(self.address_handler, conf.router_refresh_delay_secs, self.router)

        self.monitor = monitor

    def run(self):
        """Polls for messages."""
        while not self.__stop_event.is_set() and (self.monitor is None or self.monitor.max_sends > 0):
            logging.debug("Polling for packet...")

            packet: ILNPPacket
            arriving_loc: int
            packet, arriving_loc = self.__to_be_routed_queue.get(block=True)

            self.handle_packet(packet, arriving_loc)
            self.__to_be_routed_queue.task_done()

    def stop(self):
        self.__stop_event.set()
        self.__listening_thread.stop()
        self.__listening_thread.join()
        self.router.sender.close()
        self.dsr_service.stop()

    def handle_packet(self, packet: ILNPPacket, arriving_loc: int):
        if not self.address_handler.is_from_me(packet):
            self.dsr_service.backwards_learn(packet.src.loc, arriving_loc)

        if is_control_packet(packet):
            self.dsr_service.handle_control_packet(packet, arriving_loc)
        else:
            self.router.route_packet(packet, arriving_loc)

    def send_from_host(self, payload: bytes, destination: ILNPAddress):
        self.__to_be_routed_queue.add(self.router.construct_host_packet(payload, destination))


class Router:

    def __init__(self, address_handler: AddressHandler, route_provider,
                 received_packets_queue: ReceivedQueue, conf: Config, monitor: Monitor):
        self.address_handler: AddressHandler = address_handler
        self.route_provider = route_provider
        self.__received_packets_queue: ReceivedQueue = received_packets_queue
        self.sender = SendingSocket(conf.port, conf.locators_to_ipv6, conf.loopback)
        self.monitor: Monitor = monitor
        self.hop_limit: int = conf.hop_limit

    def construct_host_packet(self, payload: bytes, dest: ILNPAddress, src: Optional[ILNPAddress] = None) -> ILNPPacket:
        if src is None:
            src = ILNPAddress(self.address_handler.my_id, self.address_handler.get_random_src_locator())

        return ILNPPacket(src,
                          dest,
                          payload=memoryview(payload),
                          payload_length=len(payload),
                          hop_limit=self.hop_limit)

    def route_packet(self, packet: ILNPPacket, arriving_interface: int = None):
        if self.address_handler.is_my_locator(packet.dest.loc):
            self.route_to_adjacent_node(packet, arriving_interface)
        else:
            self.route_to_remote_node(packet, arriving_interface)

    def route_to_remote_node(self, packet: ILNPPacket, arriving_interface: int):
        next_hop_locator = self.route_provider.get_next_hop(packet.dest.loc, arriving_interface)

        if next_hop_locator is None and arriving_interface is None:
            self.route_provider.find_route_for_packet(packet)
        elif next_hop_locator is not None:
            self.forward_packet_to_addresses(packet, [next_hop_locator])

    def route_to_adjacent_node(self, packet: ILNPPacket, arriving_interface: int):
        if self.address_handler.is_for_me(packet):
            self.__received_packets_queue.add(packet.payload)
        elif packet.dest.loc != arriving_interface or arriving_interface is None:
            self.forward_packet_to_addresses(packet, [packet.dest.loc])

    def flood_to_neighbours(self, packet: ILNPPacket, arriving_interface: int = None):
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
        if packet.hop_limit < 0:
            return

        if decrement_hop:
            packet.decrement_hop_limit()

        from_me = self.address_handler.is_from_me(packet)
        packet_bytes = bytes(packet)
        for locator in next_hop_locators:
            self.sender.sendTo(packet_bytes, locator)

            if self.monitor:
                self.monitor.record_sent_packet(packet, from_me)
                if self.monitor.max_sends <= 0:
                    return


def create_dsr_message(message: Serializable) -> DSRMessage:
    header = DSRHeader.build(message.size_bytes())
    return DSRMessage(header, [message])


class DSRService(threading.Thread):
    MAX_NUM_RETRIES = 5
    TIME_BEFORE_RETRY = 10

    def __init__(self, address_handler: AddressHandler, maintenance_interval_secs: int, router: Router):
        """
        Initializes DSRService with forwarding table which it will maintain with information it gains from routing
        messages.

        :param maintenance_interval_secs: time between each forwarding table refresh
        """
        super().__init__()
        self.router: router = router
        self.address_handler: AddressHandler = address_handler
        self.request_id_generator: RequestIdGenerator = RequestIdGenerator()

        # Buffers
        self.destination_queues: DestinationQueues = DestinationQueues()
        self.requests_made: RequestRecords = RequestRecords()
        self.recently_seen_request_ids: RecentRequestBuffer = RecentRequestBuffer()

        # Network Knowledge
        self.forwarding_table: ForwardingTable = ForwardingTable()
        self.network_graph: NetworkGraph = self.init_network_graph()

        # Maintenance
        self.maintenance_interval = maintenance_interval_secs
        self.stopped: threading.Event = threading.Event()
        self.daemon = True
        self.start()

        self.handler_functions = {
            RouteRequest.TYPE: self.__handle_route_request,
            RouteReply.TYPE: self.__handle_route_reply,
            RouteError.TYPE: self.__handle_route_error,
        }

    def init_network_graph(self) -> NetworkGraph:
        return NetworkGraph(self.address_handler.my_locators)

    def stop(self):
        self.stopped.set()

    def run(self):
        """
        Repeated maintenance tasks
        """
        while not self.stopped.is_set():
            # Age and clear network graph once unreliable
            nodes_have_expired = self.forwarding_table.decrement_and_clear()
            if nodes_have_expired:
                self.network_graph = self.init_network_graph()

            # Retry and clear buffered packets
            self.requests_made.age_records()
            self.__retry_old_requests()
            # Sleep
            time.sleep(self.maintenance_interval)

    def __retry_old_requests(self):
        to_be_retried = []
        for request in self.requests_made.pop_records_older_than(self.TIME_BEFORE_RETRY):
            if request.num_attempts < self.MAX_NUM_RETRIES:
                to_be_retried.append(request)
            else:
                # Discard and assume loss of connection to locator
                self.destination_queues.pop_dest_queue(request.dest_loc)
                self.network_graph.remove_node(request.dest_loc)

        for request in to_be_retried:
            # Takes destination ID of first packet for routing, though any node in that locator can reply with path
            dest_loc = request.dest_loc
            dest_id = self.destination_queues[dest_loc][0].dest.id
            self.__send_route_request(ILNPAddress(dest_loc, dest_id), request.num_attempts)

    def __create_rreq(self, dest_loc: int) -> RouteRequest:
        request_id = next(self.request_id_generator)
        return RouteRequest.build(request_id, dest_loc)

    def __send_route_request(self, dest_addr: ILNPAddress, num_attempts: int = 0, arriving_interface: int = None):
        rreq = self.__create_rreq(dest_addr.loc)
        dsr_message = create_dsr_message(rreq)

        next_hops = [x for x in self.address_handler.my_locators]
        if arriving_interface in next_hops:
            next_hops.remove(arriving_interface)

        packet = self.router.construct_host_packet(bytes(dsr_message), dest_addr)
        for next_hop in next_hops:
            packet.src.loc = next_hop
            self.router.forward_packet_to_addresses(packet, [next_hop], False)

        self.requests_made.add(rreq.request_id, dest_addr.loc, num_attempts + 1)

    def __send_route_reply(self, original_packet: ILNPPacket, rreq: RouteRequest, arrived_from_locator: int):
        rrply = RouteReply.build(rreq, original_packet.src.loc, original_packet.dest.loc)
        msg = create_dsr_message(rrply)

        packet = self.router.construct_host_packet(bytes(msg), original_packet.src, original_packet.dest)

        self.router.forward_packet_to_addresses(packet, [arrived_from_locator])

    def find_route_for_packet(self, packet: ILNPPacket):
        dest_loc = packet.dest.loc

        if dest_loc not in self.destination_queues:
            self.__send_route_request(packet.dest)

        self.destination_queues.add_packet(packet)

    def handle_control_packet(self, packet: ILNPPacket, arrived_from_locator: int):
        if packet.next_header is not DSR_NEXT_HEADER_VALUE:
            return

        dsr_bytes = memoryview(packet.payload)[:packet.payload_length]
        dsr_message = DSRMessage.from_bytes(dsr_bytes)
        for message in dsr_message.messages:
            self.handler_functions[message.TYPE](packet, dsr_message, message, arrived_from_locator)

    def __handle_route_error(self, packet: ILNPPacket, dsr_message: DSRMessage, message: RouteError,
                             arrived_from_locator: int):
        pass  # TODO

    def __send_packets(self, packets: List[ILNPPacket], next_hop: int):
        for packet in packets:
            self.router.forward_packet_to_addresses(packet, [next_hop])

    def __forward_route_request(self, packet: ILNPPacket, dsr_message: DSRMessage, message: RouteRequest,
                                black_list: List[int]):
        next_hops = [next_hop for next_hop in self.address_handler.my_locators if next_hop not in black_list]
        original_list = message.route_list.locators.copy()

        for next_hop in next_hops:
            message.route_list.locators = original_list + [next_hop]

            message.data_len += LOCATOR_SIZE
            dsr_message.header.payload_length += LOCATOR_SIZE
            packet.payload_length += LOCATOR_SIZE
            packet.payload = bytes(dsr_message)

            self.router.forward_packet_to_addresses(packet, [next_hop], False)

    def __update_route_cache_and_attempt_send(self, new_path: List[int], arrived_from_locator: int):
        self.network_graph.add_path(new_path)
        for locator in new_path:
            if locator in self.destination_queues:
                self.__send_packets(self.destination_queues.pop_dest_queue(locator), arrived_from_locator)
                self.requests_made.pop_by_dest(locator)

    def __handle_route_request(self, packet: ILNPPacket, dsr_message: DSRMessage, rreq: RouteRequest,
                               arrived_from_locator: int):
        full_path = [packet.src.loc] + rreq.route_list.locators
        self.__update_route_cache_and_attempt_send(full_path, arrived_from_locator)

        # Reply if for me
        if self.address_handler.is_for_me(packet):
            self.__send_route_reply(packet, rreq, arrived_from_locator)
        # Discard if seen recently
        elif (packet.src.id, rreq.request_id) in self.recently_seen_request_ids:
            return
        else:
            # Forward to all adjacent locators its not already been to
            self.__forward_route_request(packet, dsr_message, rreq, full_path)

        self.recently_seen_request_ids.add(packet.src.id, rreq.request_id)

    def __handle_route_reply(self, packet: ILNPPacket, dsr_message: DSRMessage, rrply: RouteReply,
                             arrived_from_locator: int):
        full_path = rrply.route_list.locators
        self.__update_route_cache_and_attempt_send(full_path, arrived_from_locator)

        # Attempt to suggest better path before forwarding if not for me
        if not self.address_handler.is_for_me(packet):
            better_path = self.network_graph.get_shortest_path(full_path[0], full_path[len(full_path) - 1])
            if len(better_path) < len(full_path):
                rrply.change_route_list(better_path)
                dsr_message.header.payload_length = rrply.size_bytes()
                packet.payload_length = dsr_message.size_bytes()
                packet.payload = bytes(dsr_message)

            self.router.route_packet(packet, arrived_from_locator)

    def __remove_adjacent_locator_hops(self, existing_route: List[int]):
        my_locs = self.address_handler.my_locators
        if len(existing_route) == 1:
            return existing_route

        # Remove first hop if directly interfaced with second hop
        if existing_route[1] in my_locs:
            existing_route[:] = existing_route[1:]
            return self.__remove_adjacent_locator_hops(existing_route)
        else:
            return existing_route

    def get_next_hop(self, dest_locator: int, arriving_interface: int) -> Optional[int]:
        """
        Provides a set of next hops to send the packet to get it to its destination. The arriving interface if provided
        will be removed to avoid the packet being pointlessly sent the way it came.

        :param dest_locator: locator address packet is destined for
        :param arriving_interface: locator interface that packet arrived on
        :return: list of viable next hops that should lead to the packets destination
        """
        if dest_locator in self.forwarding_table:
            # Check if next hop in forwarding table
            next_hops = self.forwarding_table.get_next_hop_list(dest_locator)
            return random.choice(next_hops.entries)
        else:
            # Check if route exists in current route knowledge and add it once known
            existing_route = self.network_graph.get_shortest_path(arriving_interface, dest_locator)
            if existing_route:
                existing_route = self.__remove_adjacent_locator_hops(existing_route)
                next_hop = existing_route[0]
                self.forwarding_table.add_or_update_entry(dest_locator, next_hop, len(existing_route))
                return next_hop
            else:
                return None

    def backwards_learn(self, src_loc: int, arriving_loc: int):
        self.forwarding_table.add_or_update_entry(src_loc, arriving_loc)
