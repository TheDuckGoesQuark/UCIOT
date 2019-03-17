import collections
import threading
import time
from typing import List, Dict, Deque, Tuple, Optional

from underlay.routing.dsrmessages import RouteRequest, RouteReply, DSRMessage, DSRHeader, RouteError, LOCATOR_SIZE, \
    RouteList
from underlay.routing.forwardingtable import ForwardingTable
from underlay.routing.ilnpaddress import ILNPAddress
from underlay.routing.ilnppacket import ILNPPacket, DSR_NEXT_HEADER_VALUE
from underlay.routing.router import Router
from underlay.routing.serializable import Serializable

NUM_REQUEST_IDS = 256


class RecentRequestBuffer:
    def __init__(self):
        self.recently_seen: Deque[Tuple[int, int]] = collections.deque(10 * [()])

    def add(self, src_id, request_id):
        self.recently_seen.appendleft((src_id, request_id))

    def __contains__(self, src_id_request_id: Tuple[int, int]) -> bool:
        return src_id_request_id in self.recently_seen


class RequestRecord:
    def __init__(self, dest_loc: int, num_attempts: int):
        self.dest_loc: int = dest_loc
        self.num_attempts: int = num_attempts
        self.time_since_last_attempt: int = 0

    def increment_num_attempts(self):
        self.num_attempts = self.num_attempts + 1

    def increment_time_since_last_attempt(self):
        self.time_since_last_attempt = self.time_since_last_attempt + 1


class RequestRecords:
    def __init__(self):
        self.records: List[Optional[RequestRecord]] = [None] * NUM_REQUEST_IDS

    def __contains__(self, request_id: int) -> bool:
        return self.records[request_id] is not None

    def add(self, request_id: int, dest_loc: int, num_attempts: int = 0):
        self.records[request_id] = RequestRecord(dest_loc, num_attempts)

    def pop(self, request_id: int):
        record = self.records[request_id]
        self.records[request_id] = None
        return record

    def pop_by_dest(self, dest_loc: int):
        requests_for_dest = [request_id for request_id, request in enumerate(self.records)
                             if request is not None and request.dest_loc == dest_loc]

        for request in requests_for_dest:
            self.pop(request)

    def age_records(self):
        for record in self.records:
            if record is not None:
                record.increment_time_since_last_attempt()

    def pop_records_older_than(self, age: int) -> List[RequestRecord]:
        old_records = []

        for request_id in range(len(self.records)):
            if request_id not in self:
                continue
            elif self.records[request_id].time_since_last_attempt > age:
                old_records.append(self.pop(request_id))

        return old_records


class DestinationQueues:
    """
    Maintains list of packets waiting for route to destination, and the request id of the RREQ that is fetching the
    route.
    """

    def __init__(self):
        self.dest_queues: Dict[int, List[ILNPPacket]] = {}

    def __contains__(self, dest_loc: int) -> bool:
        return dest_loc in self.dest_queues

    def __getitem__(self, dest_loc: int) -> List[ILNPPacket]:
        return self.dest_queues[dest_loc]

    def add_packet(self, packet: ILNPPacket):
        """
        Adds packet to existing queue for destination, or creates one and adds it if doesn't already exist
        :param packet: packet to add to queue
        """
        dest_loc = packet.dest.loc

        if dest_loc not in self:
            self.dest_queues[dest_loc] = [packet]
        else:
            self.dest_queues[dest_loc].append(packet)

    def remove_dest_queue(self, dest_loc: int):
        del self.dest_queues[dest_loc]

    def pop_dest_queue(self, dest_loc: int) -> List[ILNPPacket]:
        return self.dest_queues.pop(dest_loc)


class RequestIdGenerator:
    def __init__(self):
        self.current = 0

    def __next__(self):
        val = self.current
        self.current = (self.current + 1) % NUM_REQUEST_IDS
        return val

    def __iter__(self):
        self.current = 0
        return self


class DSRService(threading.Thread):
    MAX_NUM_RETRIES = 5
    TIME_BEFORE_RETRY = 10

    def __init__(self, router: Router, maintenance_interval_secs: int):
        """
        Initializes DSRService with forwarding table which it will maintain with information it gains from routing
        messages.

        :param maintenance_interval_secs: time between each forwarding table refresh
        :param router: router that can be used to forward any control messages
        """
        super().__init__()
        self.router: Router = router
        self.request_id_generator = RequestIdGenerator()

        # Buffers
        self.destination_queues: DestinationQueues = DestinationQueues()
        self.requests_made: RequestRecords = RequestRecords()
        self.recently_seen_request_ids: RecentRequestBuffer = RecentRequestBuffer()

        # Network Knowledge
        self.forwarding_table: ForwardingTable = ForwardingTable()
        self.network_graph: NetworkGraph = NetworkGraph(self.router.my_locators)

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

    def stop(self):
        self.stopped.set()

    def run(self):
        """
        Repeated maintenance tasks
        """
        while not self.stopped.is_set():
            # Age
            self.forwarding_table.decrement_and_clear()
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
                self.destination_queues.pop_dest_queue(request.dest_loc)

        for request in to_be_retried:
            # Takes destination ID of first packet for routing, though any node in that locator can reply with path
            dest_loc = request.dest_loc
            dest_id = self.destination_queues[dest_loc][0].dest.id
            self.__send_route_request(ILNPAddress(dest_loc, dest_id), request.num_attempts)

    def __create_rreq(self, dest_loc: int) -> RouteRequest:
        request_id = next(self.request_id_generator)
        return RouteRequest.build(request_id, dest_loc)

    def __create_dsr_message(self, message: Serializable) -> DSRMessage:
        header = DSRHeader.build(message.size_bytes())
        return DSRMessage(header, [message])

    def __send_route_request(self, dest_addr: ILNPAddress, num_attempts: int = 0, arriving_interface: int = None):
        rreq = self.__create_rreq(dest_addr.loc)
        dsr_message = self.__create_dsr_message(rreq)

        next_hops = [x for x in self.router.my_locators]
        if arriving_interface in next_hops:
            next_hops.remove(arriving_interface)

        packet = self.router.construct_host_packet(bytes(dsr_message), dest_addr)
        for next_hop in next_hops:
            packet.src.loc = next_hop
            self.router.forward_packet_to_addresses(packet, [next_hop], False)

        self.requests_made.add(rreq.request_id, dest_addr.loc, num_attempts + 1)

    def __send_route_reply(self, original_packet: ILNPPacket, rreq: RouteRequest, arrived_from_locator: int):
        rrply = RouteReply.build(rreq, original_packet.src.loc, original_packet.dest.loc)
        msg = self.__create_dsr_message(rrply)

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
        next_hops = [next_hop for next_hop in self.router.my_locators if next_hop not in black_list]
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
        if self.router.is_for_me(packet):
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
        if not self.router.is_for_me(packet):
            better_path = self.network_graph.get_path_between(full_path[0], full_path[len(full_path) - 1])
            if len(better_path) < len(full_path):
                rrply.change_route_list(better_path)
                dsr_message.header.payload_length = rrply.size_bytes()
                packet.payload_length = dsr_message.size_bytes()
                packet.payload = bytes(dsr_message)

            self.router.route_packet(packet, arrived_from_locator)

    def get_next_hop(self, dest_locator: int, arriving_interface: int) -> Optional[int]:
        """
        Provides a set of next hops to send the packet to get it to its destination. The arriving interface if provided
        will be removed to avoid the packet being pointlessly sent the way it came.

        :param dest_locator: locator address packet is destined for
        :param arriving_interface: locator interface that packet arrived on
        :return: list of viable next hops that should lead to the packets destination
        """
        # TODO
        pass

    def backwards_learn(self, src_loc: int, arriving_loc: int):
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

    def add_path(self, locators):
        pass
