import logging
import threading
import time
from typing import Dict, List

from sensor.battery import Battery
from sensor.network.router.interzone import ExternalRequestHandler
from sensor.network.router.ilnp import ILNPAddress, ILNPPacket, ALL_LINK_LOCAL_NODES_ADDRESS
from sensor.network.router.forwardingtable import ForwardingTable, ZonedNetworkGraph, update_forwarding_table
from sensor.network.router.controlmessages import Hello, ControlMessage, ControlHeader, LSDBMessage, ExpiredLinkList, \
    LocatorRouteRequest, LocatorRouteReply, LocatorLinkError
from sensor.network.router.netinterface import NetworkInterface
from sensor.network.router.util import BoundedSequenceGenerator
from sensor.packetmonitor import Monitor

logger = logging.getLogger(__name__)

NO_NEXT_HEADER_VALUE = 59

# Internal Configuration
KEEP_ALIVE_INTERVAL_SECS = 20
MAX_AGE_OF_LINK = KEEP_ALIVE_INTERVAL_SECS * 2

# Max lambda is given by the range of 4 bytes
MAX_LAMBDA = (2 ** (4 * 8)) - 1


def parse_type(raw_bytes: memoryview) -> int:
    """Parses type from control message"""
    return int(raw_bytes[0])


class NeighbourLinks:
    """Tracks all link local neighbours and the time since their last keepalive"""

    def __init__(self):
        self.neighbour_link_ages: Dict[int, int] = {}

    def __contains__(self, item):
        return item in self.neighbour_link_ages

    def get_neighbour_age(self, node_id: int) -> int:
        return self.neighbour_link_ages[node_id]

    def add_neighbour(self, neighbour_id: int):
        self.neighbour_link_ages[neighbour_id] = 0

    def refresh_neighbour(self, neighbour_id: int):
        self.add_neighbour(neighbour_id)

    def pop_expired_neighbours(self) -> List[int]:
        expired_ids = [node_id for node_id, age in self.neighbour_link_ages.items() if age >= MAX_AGE_OF_LINK]
        for expired_id in expired_ids:
            del self.neighbour_link_ages[expired_id]

        return expired_ids

    def age_neighbours(self):
        for neighbour in self.neighbour_link_ages:
            self.neighbour_link_ages[neighbour] += KEEP_ALIVE_INTERVAL_SECS


class RouterControlPlane(threading.Thread):
    def __init__(self, net_interface: NetworkInterface, my_address: ILNPAddress,
                 battery: Battery, forwarding_table: ForwardingTable, monitor: Monitor):
        super().__init__(name="Control")
        self.battery = battery
        self.my_address = my_address
        self.monitor: Monitor = monitor

        # Forwarding table provides quick look-up for forwarding packets to internal and external nodes
        self.forwarding_table = forwarding_table
        self.network_graph = ZonedNetworkGraph(self.my_address.id, self.__calc_my_lambda())

        # Tracks neighbours and time since last keepalive
        self.neighbours: NeighbourLinks = NeighbourLinks()
        self.net_interface = net_interface

        # Status flags
        self.update_available = False

        # Tracks last LSB sequence value
        self.lsb_sequence_generator = BoundedSequenceGenerator(511)

        # Handler for locator requests
        self.external_request_handler = ExternalRequestHandler(self.net_interface, self.my_address,
                                                               self.forwarding_table, self.monitor)

    def join(self, timeout=None) -> None:
        self.monitor.running = False
        super().join(timeout)

    def run(self) -> None:
        """Send keepalives and remove links that haven't sent one"""
        self.initialize()

        while self.monitor.running:
            time.sleep(KEEP_ALIVE_INTERVAL_SECS)
            try:
                self.__send_keepalive()
            except Exception as e:
                logger.info(str(e))
                self.monitor.running = False

            self.neighbours.age_neighbours()
            logger.info("Current neighbours: {}".format(vars(self.neighbours)))
            logger.info("Current network graph: {}".format(str(self.network_graph)))
            logger.info("Current forwarding table: {}".format(str(self.forwarding_table)))

            logger.info("Removing expired links")
            expired = self.neighbours.pop_expired_neighbours()
            logger.info("links expired: {}".format(expired))
            if len(expired) > 0:
                self.__handle_expired_links(expired)
                self.update_available = True

            self.external_request_handler.maintenance()

            if self.update_available:
                self.__recalculate_forwarding_table()

        logger.info("Control thread finished executing")

    def initialize(self):
        """Broadcast hello messages with my lambda to inform neighbours of presence"""
        self.__send_keepalive()

    def __calc_my_lambda(self):
        return int(1 - (1 - self.battery.percentage()) ** 2) * MAX_LAMBDA

    def __send_keepalive(self):
        """Broadcasts hello message containing this nodes current lambda"""
        keepalive = Hello(self.__calc_my_lambda())
        header = ControlHeader(keepalive.TYPE, keepalive.size_bytes())
        control_message = ControlMessage(header, keepalive)

        packet = ILNPPacket(self.my_address, ALL_LINK_LOCAL_NODES_ADDRESS, hop_limit=0,
                            payload_length=control_message.size_bytes(), payload=bytes(control_message))

        self.net_interface.broadcast(bytes(packet))
        self.monitor.record_sent_packet(True, False)

    def find_route(self, packet: ILNPPacket):
        """Finds route to an external ID"""
        self.external_request_handler.find_route(packet)

    def handle_control_packet(self, packet: ILNPPacket):
        control_type = packet.payload.header.payload_type

        if packet.src.id == self.my_address.id:
            return

        if control_type is Hello.TYPE:
            logger.info("Received hello message!: {}".format(str(packet.payload)))
            self.__handle_hello(packet)
        elif control_type is LSDBMessage.TYPE:
            logger.info("Received LSDBMessage!: {}".format(str(packet.payload)))
            self.__handle_lsdb_message(packet)
        elif control_type is ExpiredLinkList.TYPE:
            logger.info("Received ExpiredLinkList! {}".format(str(packet.payload)))
            self.__handle_expired_link_list_message(packet)
        elif control_type is LocatorRouteRequest.TYPE:
            logger.info("Received locator route request: {}".format(str(packet.payload)))
            self.external_request_handler.handle_locator_route_request(packet)
        elif control_type is LocatorRouteReply.TYPE:
            logger.info("Received locator route reply: {}".format(str(packet.payload)))
            self.external_request_handler.handle_locator_route_reply(packet)
        elif control_type is LocatorLinkError.TYPE:
            logger.info("Received locator link error: {}".format(str(packet.payload)))
            self.external_request_handler.handle_locator_link_error(packet)
        else:
            logger.info("Unknown message received")

    def __handle_hello(self, packet: ILNPPacket):
        """Refreshes neighbours link to stop expiry process, or adds neighbour"""
        src_id = packet.src.id
        if src_id in self.neighbours:
            logger.info("Refreshing neighbour link {}".format(src_id))
            self.neighbours.refresh_neighbour(src_id)
        else:
            logger.info("New neighbour! {}".format(src_id))
            self.__handle_new_neighbour(packet)

    def __handle_new_neighbour(self, packet: ILNPPacket):
        """Adds neighbour as either external or internal link depending on locator, and broadcasts updated LSDB"""
        neighbour_address = packet.src
        hello: Hello = packet.payload.body

        logger.info("Adding neighbour")
        self.neighbours.add_neighbour(neighbour_address.id)

        # is local node
        if neighbour_address.loc == self.my_address.loc:
            logger.info("Adding as internal link")
            self.network_graph.add_internal_link(
                self.my_address.id, self.__calc_my_lambda(), neighbour_address.id, hello.lambda_val
            )
            self.__broadcast_lsdb()
        # is remote node
        else:
            logger.info("Adding as external link")
            self.network_graph.add_external_link(
                self.my_address.id, neighbour_address.loc, neighbour_address.id, hello.lambda_val
            )
            self.__broadcast_lsdb()

        self.update_available = True

    def __broadcast_lsdb(self):
        """Broadcasts my LSDB to neighbouring nodes"""
        logger.info("Broadcasting my LSDB")
        lsdb = self.network_graph.to_lsdb_message(next(self.lsb_sequence_generator))
        header = ControlHeader(LSDBMessage.TYPE, lsdb.size_bytes())
        control_message = ControlMessage(header, lsdb)
        packet = ILNPPacket(self.my_address, ALL_LINK_LOCAL_NODES_ADDRESS,
                            payload_length=control_message.size_bytes(), payload=control_message)

        self.net_interface.broadcast(bytes(packet))
        self.monitor.record_sent_packet(True, False)

    def __handle_lsdb_message(self, packet):
        """Handles LSDB messages"""
        lsdbmessage: LSDBMessage = packet.payload.body

        # From local network and contains new information
        if packet.src.loc == self.my_address.loc and self.network_graph.add_all(lsdbmessage):
            logger.info("Change detected from local network LSDB")
            self.lsb_sequence_generator.set_to_last_seen(lsdbmessage.seq_number)
            self.__broadcast_lsdb()
            self.update_available = True
        else:
            logger.info("No new information or describes other locator. Discarding")

    def __handle_expired_link_list_message(self, packet: ILNPPacket):
        if packet.src.loc != self.my_address.loc:
            logger.info("Link failure in other network. None of my concern")
            return

        central_node_id: int = packet.src.id
        expired_message: ExpiredLinkList = packet.payload.body
        learned_something = False
        for expired_node_id in expired_message.lost_link_ids:
            learned_something |= self.network_graph.remove_link(central_node_id, expired_node_id)

        if learned_something:
            packet.decrement_hop_limit()
            if packet.hop_limit > 0:
                self.net_interface.broadcast(bytes(packet))
                self.monitor.record_sent_packet(True, True)
                self.update_available = True

    def __handle_expired_links(self, expired: List[int]):
        """Broadcasts information about lost links and removes them from our network graph"""
        for expired_node_id in expired:
            self.network_graph.remove_link(self.my_address.id, expired_node_id)

        expired_message = ExpiredLinkList(expired)
        header = ControlHeader(expired_message.TYPE, expired_message.size_bytes())
        control_message = ControlMessage(header, expired_message)
        packet = ILNPPacket(self.my_address, ALL_LINK_LOCAL_NODES_ADDRESS,
                            payload_length=control_message.size_bytes(), payload=control_message)

        self.net_interface.broadcast(bytes(packet))
        self.monitor.record_sent_packet(True, False)

    def __recalculate_forwarding_table(self):
        """Recalculates next hops for the forwarding table based on the internal network graph"""
        logger.info("Recalculating forwarding table")
        update_forwarding_table(self.network_graph, self.my_address.id, self.forwarding_table)
        self.external_request_handler.add_external_paths_to_forwarding_table(self.forwarding_table)
