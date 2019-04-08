import logging
import threading
import time
from multiprocessing import Queue
from typing import Dict, List

from sensor.battery import Battery
from sensor.network.router.ilnp import ILNPAddress, ILNPPacket
from sensor.network.router.forwardingtable import ForwardingTable, ZonedNetworkGraph
from sensor.network.router.controlmessages import Hello, ControlMessage, ControlHeader, LSBMessage, Link
from sensor.network.router.netinterface import NetworkInterface
from sensor.network.router.util import BoundedSequenceGenerator

logger = logging.getLogger(__name__)

NO_NEXT_HEADER_VALUE = 59

# Internal Configuration
KEEP_ALIVE_INTERVAL_SECS = 3
MAX_AGE_OF_LINK = KEEP_ALIVE_INTERVAL_SECS * 3

# Max lambda is given by the range of 4 bytes
MAX_LAMBDA = (2 ** (4 * 8)) - 1

# All nodes multicast address as in IPv6
ALL_LINK_LOCAL_NODES_ADDRESS = ILNPAddress(int("ff01000000000000", 16), int("1", 16))


def parse_type(raw_bytes: memoryview) -> int:
    """Parses type from control message"""
    return int(raw_bytes[0])


class NeighbourLinks:
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


class RouterControlPlane(threading.Thread):
    def __init__(self, net_interface: NetworkInterface, my_address: ILNPAddress,
                 battery: Battery, forwarding_table: ForwardingTable):
        super().__init__()
        self.battery = battery
        self.my_address = my_address

        # Forwarding table provides quick look-up for forwarding packets to internal and external nodes
        self.forwarding_table = forwarding_table
        self.network_graph = ZonedNetworkGraph()

        # Tracks neighbours and time since last keepalive
        self.neighbours: NeighbourLinks = NeighbourLinks()
        self.net_interface = net_interface

        # Status flags
        self.running = False
        self.initialized = False

        # Tracks last LSB sequence value
        self.lsb_sequence_generator = BoundedSequenceGenerator(511)

    def join(self, timeout=None) -> None:
        self.running = False
        super().join(timeout)

    def run(self) -> None:
        """Send keepalives and remove links that haven't sent one"""
        self.initialize()

        self.running = True
        while self.running:
            if not self.initialized:
                continue

            time.sleep(KEEP_ALIVE_INTERVAL_SECS)
            self.__send_keepalive()
            logger.info("Removing expired links")
            expired = [neighbour for neighbour, age in self.neighbours.items() if age > MAX_AGE_OF_LINK]
            self.neighbours = {neighbour: age + KEEP_ALIVE_INTERVAL_SECS
                               for neighbour, age in self.neighbours.items()
                               if age <= MAX_AGE_OF_LINK}

            logger.info("links expired: {}".format(expired))
            self.__remove_expired_links(expired)

    def initialize(self):
        """Broadcast hello messages with my lambda to inform neighbours of presence"""
        self.__send_keepalive()

    def __calc_my_lambda(self):
        return int(1 - (1 - self.battery.percentage()) ** 2) * MAX_LAMBDA

    def __send_keepalive(self):
        """Broadcasts hello message containing this nodes current lambda"""
        logger.info("Sending keepalive")
        keepalive = Hello(self.__calc_my_lambda())
        header = ControlHeader(keepalive.TYPE, keepalive.size_bytes())
        control_message = ControlMessage(header, keepalive)

        packet = ILNPPacket(self.my_address, ALL_LINK_LOCAL_NODES_ADDRESS, hop_limit=0,
                            payload_length=control_message.size_bytes(), payload=bytes(control_message))

        self.net_interface.broadcast(bytes(packet))

    def __remove_expired_links(self, expired):
        # TODO
        pass

    def find_route(self, packet: ILNPPacket):
        """Uses AODV to find a route to the packets destination"""
        # TODO
        pass

    def handle_control_packet(self, packet: ILNPPacket):
        control_type = packet.payload.header.payload_type

        if control_type is Hello.TYPE:
            logger.info("Received hello message!")
            self.__handle_hello(packet)

    def perform_locator_discovery(self, packet: ILNPPacket):
        pass

    def __handle_hello(self, packet: ILNPPacket):
        """Refreshes neighbours link to stop expiry process, or adds neighbour"""
        src_id = packet.src.id
        if src_id in self.neighbours:
            self.neighbours.refresh_neighbour(src_id)
        else:
            self.handle_new_neighbour(packet)

    def handle_new_neighbour(self, packet: ILNPPacket):
        neighbour_address = packet.src
        hello :Hello = packet.payload.body

        self.neighbours.add_neighbour(neighbour_address.id)

        if neighbour_address.loc == self.my_address.loc:
            self.network_graph.add_external_link(
                self.my_address.id, neighbour_address.loc, neighbour_address.id, hello.lambda_val)

        lsbmsg = LSBMessage(next(self.lsb_sequence_generator), [], [])
        header = ControlHeader(LSBMessage.TYPE, lsbmsg.size_bytes())
        control_message = ControlMessage(header, lsbmsg)
        packet = ILNPPacket(self.my_address, neighbour_address,
                            payload_length=control_message.size_bytes(), payload=bytes(control_message))

