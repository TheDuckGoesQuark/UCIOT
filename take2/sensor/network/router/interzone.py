import collections
import logging
from functools import reduce
from typing import List, Dict, Deque, Tuple, Optional, Set

from sensor.network.router.controlmessages import LocatorRouteRequest, LocatorHopList, ControlHeader, ControlMessage, \
    LocatorRouteReply
from sensor.network.router.forwardingtable import ForwardingTable
from sensor.network.router.ilnp import ILNPPacket, ILNPAddress
from sensor.network.router.netinterface import NetworkInterface
from sensor.network.router.util import BoundedSequenceGenerator

logger = logging.getLogger(__name__)

NUM_REQUESTS_TO_REMEMBER = 15


class RecentlySeenRequests:
    """Stores a circular FIFO queue of recently seen request IDs"""

    def __init__(self):
        self.recently_seen: Deque[Tuple[int, int]] = collections.deque(NUM_REQUESTS_TO_REMEMBER * [()])

    def __str__(self) -> str:
        return str([str(x) for x in self.recently_seen])

    def add(self, src_id: int, request_id: int):
        logger.info("Adding {} {} to recently seen requests".format(src_id, request_id))
        self.recently_seen.appendleft((src_id, request_id))

    def __contains__(self, src_id_request_id: Tuple[int, int]) -> bool:
        return src_id_request_id in self.recently_seen


class RequestRecord:
    """Record of previous request for a route to the given ID, and how many times they've been retried"""

    def __init__(self, num_attempts: int, last_request_id: int):
        self.num_attempts: int = num_attempts
        self.last_request_id = last_request_id
        self.time_since_last_attempt: int = 0
        self.waiting_packets: List[ILNPPacket] = []

    def record_retry(self, new_request_id: int):
        """Increase the number of attempts that have been to find this ID"""
        self.num_attempts = self.num_attempts + 1
        self.last_request_id = new_request_id

    def increment_time_since_last_attempt(self):
        """Increase the time since a retry was last tried"""
        self.time_since_last_attempt = self.time_since_last_attempt + 1

    def add_packet(self, packet: ILNPPacket):
        self.waiting_packets.append(packet)


class CurrentRequestBuffer:
    """Tracks request made for a given destination"""

    def __init__(self):
        # { dest id : request record }
        self.records: Dict[int, RequestRecord] = {}

    def __str__(self):
        return str([(dest_id, str(record)) for dest_id, record in self.records.items()])

    def __contains__(self, destination_id: int) -> bool:
        """Returns true if a request for that destination is recorded"""
        return destination_id in self.records

    def add_new_request(self, destination_id: int, request_id: int):
        """Records the given request"""
        logger.info("Recording new request {} for destination {}".format(request_id, destination_id))
        self.records[destination_id] = RequestRecord(0, request_id)

    def add_packet_to_destination_buffer(self, packet: ILNPPacket):
        """Adds the given packet to the queue waiting for its destination ID"""
        logger.info("Buffering packet while waiting for request response")
        self.get_destination_request(packet.dest.id).add_packet(packet)

    def get_destination_request(self, destination_id: int) -> Optional[RequestRecord]:
        """Retrieves the request record for the given destination"""
        return self.records.get(destination_id, None)

    def record_retried_request(self, destination_id, new_request_id):
        request = self.get_destination_request(destination_id)
        request.record_retry(new_request_id)

    def age_records(self):
        """Increases the time since retry for all requests"""
        for request_record in self.records.values():
            request_record.increment_time_since_last_attempt()

    def get_destination_ids_with_requests_older_than(self, age: int) -> List[int]:
        """Returns the destination ids for all requests older than the given value"""
        destinations_due_retry = []
        for dest_id, record in self.records.items():
            if record.time_since_last_attempt > age:
                destinations_due_retry.append(dest_id)

        return destinations_due_retry


def get_difference_counts(path_one: List[int], path_two: List[int]) -> Tuple[int, int]:
    """Returns the number of elements shared and not shared between the two lists"""
    shared = 0
    not_shared = 0
    for hop in path_one:
        if hop not in path_two:
            not_shared += 1
        else:
            shared += 1

    return shared, not_shared


def choose_best_backup(main_path, path_a, path_b) -> List[int]:
    """Chooses the best backup path based on disjointness from main path"""
    shared_a, diff_a = get_difference_counts(main_path, path_a)
    shared_b, diff_b = get_difference_counts(main_path, path_b)

    if shared_a == shared_b:
        # Choose the shortest path if both share the same number of hops
        return path_a if len(path_a) < len(path_b) else path_b
    else:
        # Choose path that shares the fewest nodes with main path
        return path_a if shared_a < shared_b else path_b


class PathCache:
    """
    Stores two paths to each destination

    The first path is the shortest path
    The second path is the shortest path that shares the least paths with the first path
    """

    def __init__(self):
        # { locator : ( [Main Path], [BackupPath] ) }
        self.destination_to_paths: Dict[int, Tuple[List[int], List[int]]] = {}

    def __contains__(self, item: int):
        return item in self.destination_to_paths

    def record_path(self, destination: int, path: List[int]):
        """Records and possibly replaces existing path to destination"""
        if destination in self.destination_to_paths:
            self.__compare_and_update_path(destination, path)
        else:
            self.destination_to_paths[destination] = (path, path)

    def __compare_and_update_path(self, destination: int, path: List[int]):
        main_path, backup_path = self.destination_to_paths[destination]
        if len(path) < len(main_path):
            old_main_path = main_path
            main_path = path
            backup_path = choose_best_backup(main_path, old_main_path, backup_path)
        else:
            backup_path = choose_best_backup(main_path, backup_path, path)

        self.destination_to_paths[destination] = (main_path, backup_path)

    def get_path_to_dest(self, locator: int) -> List[int]:
        return self.destination_to_paths[locator][0]


def extend_route_request(packet: ILNPPacket):
    """Appends empty locator to hop list and updates size of control and ILNP header payload lengths"""
    header: ControlHeader = packet.payload.header
    body: LocatorRouteRequest = packet.payload.body
    # Add empty locator to be overwritten
    body.locator_hop_list.append(0)
    # Refresh control header payload length
    header.payload_length = body.size_bytes()
    # Refresh ILNPPacket payload length
    packet.payload_length = packet.payload.size_bytes()


class ExternalRequestHandler:
    def __init__(self, net_interface: NetworkInterface, my_address: ILNPAddress, forwarding_table: ForwardingTable):
        self.my_address: ILNPAddress = my_address

        # Bookkeeping
        self.recently_seen_requests: RecentlySeenRequests = RecentlySeenRequests()
        self.current_requests: CurrentRequestBuffer = CurrentRequestBuffer()
        self.request_id_generator: BoundedSequenceGenerator = BoundedSequenceGenerator(511)
        self.path_cache: PathCache = PathCache()

        # Forwarding
        self.forwarding_table: ForwardingTable = forwarding_table
        self.net_interface: NetworkInterface = net_interface

    def find_route(self, packet: ILNPPacket):
        """
        initializes route request for the packet destination,
        or adds it to the queue of packets already waiting for that destination
        """
        dest_id = packet.dest.id

        if dest_id in self.current_requests:
            self.current_requests.add_packet_to_destination_buffer(packet)
        else:
            request_id = self.__initiate_destination_request(packet)
            if request_id is not None:
                self.current_requests.add_packet_to_destination_buffer(packet)
            else:
                logger.info("No neighbours to send destination request to. Discarding packet.")

    def __build_rreq(self, request_id: int, dest_id: int, first_hop_locator: int) -> ILNPPacket:
        logger.info("Building route request for {} via locator {}".format(dest_id, first_hop_locator))
        initial_list = LocatorHopList([first_hop_locator])
        rreq = LocatorRouteRequest(request_id, True, initial_list)
        header = ControlHeader(rreq.TYPE, rreq.size_bytes())
        control = ControlMessage(header, rreq)
        return ILNPPacket(self.my_address, ILNPAddress(0, dest_id), payload=control,
                          payload_length=control.size_bytes())

    def __initiate_destination_request(self, packet: ILNPPacket) -> Optional[int]:
        """Sends a destination request via each of the neighbouring locators"""
        logger.info("Initiating destination request")

        if len(self.forwarding_table.next_hop_to_locator) == 0:
            logger.info("No neighbour locators to send destination request to.")
            logger.info("Discarding.")
            return None

        request_id = next(self.request_id_generator)
        for locator, next_hop in self.forwarding_table.next_hop_to_locator.items():
            request: ILNPPacket = self.__build_rreq(request_id, packet.dest.id, locator)
            self.net_interface.send(bytes(request), next_hop)

        self.current_requests.add_new_request(packet.dest.id, request_id)

    def handle_locator_route_request(self, packet: ILNPPacket):
        logger.info("Handling route request")
        request: LocatorRouteRequest = packet.payload.body

        if packet.dest.id == self.my_address.id:
            logger.info("Request for me. Replying")
            packet.dest.loc = self.my_address.loc
            self.__reply_to_locator_route_request(packet)
        elif (packet.src.id, request.request_id) in self.recently_seen_requests:
            logger.info(
                "Seen request id {} from src {} too recently. Discarding.".format(packet.src.id, request.request_id))
        elif self.__in_my_locator(packet.dest.id):
            logger.info("Received request for ID in my locator. Replying")
            packet.dest.loc = self.my_address.loc
            self.__reply_to_locator_route_request(packet)
            self.recently_seen_requests.add(packet.src.id, request.request_id)
        elif request.allow_cached_replies:
            logger.info("Checking cache for reply")
            node_locator = self.forwarding_table.get_locator_for_id(packet.dest.id)
            if node_locator is not None and node_locator in self.path_cache:
                logger.info("Have cached path")
                cached_path = self.path_cache.get_path_to_dest(node_locator)
                current_path = request.locator_hop_list.locator_hops
                if self.my_address.loc in current_path:
                    reply = current_path[:current_path.index(self.my_address.loc) + 1] + cached_path
                else:
                    # Request originated from my locator
                    reply = cached_path

                logger.info("Replying with path: {}".format(reply))
                self.___reply_with_cached_path(reply, packet.src)
            else:
                logger.info("No cached path, forwarding")
                self.__forward_locator_route_request(packet)

            self.recently_seen_requests.add(packet.src.id, request.request_id)
        else:
            logger.info("Forwarding route request")
            self.__forward_locator_route_request(packet)
            self.recently_seen_requests.add(packet.src.id, request.request_id)

    def __in_my_locator(self, node_id: int):
        """Checks that the node with the given ID exiss within this locator"""
        return self.forwarding_table.find_next_hop_for_local_node(node_id) is not None

    def __reply_to_locator_route_request(self, packet: ILNPPacket):
        """Replies to request with reverse of their path"""
        request: LocatorRouteRequest = packet.payload.body
        path: List[int] = request.locator_hop_list.locator_hops
        reply = LocatorRouteReply(LocatorHopList(path))
        header = ControlHeader(reply.TYPE, reply.size_bytes())
        message = ControlMessage(header, reply)
        reply_packet = ILNPPacket(self.my_address, packet.src, payload_length=message.size_bytes(),
                                  payload=bytes(message))
        # Next hop is either neighbour, or hop before my locator
        next_hop_locator = path[len(path) - 2] if len(path) > 1 else packet.src.loc
        self.net_interface.send(bytes(reply_packet), self.forwarding_table.find_next_hop_for_locator(next_hop_locator))

    def ___reply_with_cached_path(self, path: List[int], dest_address: ILNPAddress):
        """Replies to request with cached path"""
        reply = LocatorRouteReply(LocatorHopList(path))
        header = ControlHeader(reply.TYPE, reply.size_bytes())
        message = ControlMessage(header, reply)
        reply_packet = ILNPPacket(self.my_address, dest_address, payload_length=message.size_bytes(),
                                  payload=bytes(message))
        # Next hop is either in my locator, neighbour locator , or hop before my locator
        if dest_address.loc == self.my_address.loc:
            self.net_interface.send(bytes(reply_packet),
                                    self.forwarding_table.find_next_hop_for_local_node(dest_address.id))
        else:
            next_hop_locator = path[len(path) - 2] if len(path) > 1 else dest_address.loc
            self.net_interface.send(bytes(reply_packet),
                                    self.forwarding_table.find_next_hop_for_locator(next_hop_locator))

    def __forward_locator_route_request(self, packet: ILNPPacket):
        """Forwards the route request to all neighbours it hasn't already visited"""

        packet.decrement_hop_limit()
        if len(self.forwarding_table.next_hop_to_locator) == 0:
            logger.info("No neighbour locators to send destination request to.")
            logger.info("Discarding.")
            return
        elif packet.hop_limit == 0:
            logger.info("No more hops. Discarding.")
            return

        request_list: LocatorHopList = packet.payload.body.locator_hop_list
        path: List[int] = request_list.locator_hops
        if path[len(path) - 1] is not self.my_address.loc:
            self.net_interface.send(bytes(packet), self.forwarding_table.find_next_hop_for_locator(path[len(path) - 1]))
        else:
            # Get all neighbour locators not already in path
            unvisited_neighbours = [locator for locator in self.forwarding_table.next_hop_to_locator.keys()
                                    if locator not in path]

            # Forward packet to each neighbour locator
            if len(unvisited_neighbours) > 0:
                extend_route_request(packet)
                for locator in unvisited_neighbours:
                    logger.info("Forwarding to {}".format(locator))
                    # Change last hop locator on each iteration
                    request_list.locator_hops[len(request_list.locator_hops) - 1] = locator
                    self.net_interface.send(bytes(packet), self.forwarding_table.find_next_hop_for_locator(locator))

    def handle_locator_route_reply(self, packet):
        pass

    def handle_locator_link_error(self, packet):
        pass
