import collections
import logging
from typing import List, Dict, Deque, Tuple, Optional, Set

from sensor.network.router.controlmessages import LocatorRouteRequest, LocatorHopList, ControlHeader, ControlMessage
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


class ExternalRequestHandler:
    def __init__(self, net_interface: NetworkInterface, my_address: ILNPAddress, forwarding_table: ForwardingTable):
        self.my_address: ILNPAddress = my_address
        self.forwarding_table: ForwardingTable = forwarding_table
        self.recently_seen_requests: RecentlySeenRequests = RecentlySeenRequests()
        self.current_requests: CurrentRequestBuffer = CurrentRequestBuffer()
        self.net_interface: NetworkInterface = net_interface
        self.request_id_generator: BoundedSequenceGenerator = BoundedSequenceGenerator(511)

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
