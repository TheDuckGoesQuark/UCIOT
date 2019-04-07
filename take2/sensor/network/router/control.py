import logging
import threading
import time
from multiprocessing import Queue
from typing import Dict

from sensor.battery import Battery
from sensor.network.router.ilnp import ILNPAddress, ILNPPacket
from sensor.network.router.forwardingtable import ForwardingTable
from sensor.network.router.internal.lsmessages import Hello
from sensor.network.router.netinterface import NetworkInterface
from sensor.network.router.transportwrapper import build_control_wrapper

logger = logging.getLogger(__name__)

LOAD_PERCENTAGE = 50
KEEP_ALIVE_INTERVAL_SECS = 3
MAX_AGE_OF_LINK = KEEP_ALIVE_INTERVAL_SECS * 3

# Max lambda is given by the range of 4 bytes
MAX_LAMBDA = (2 ** (4 * 8)) - 1

# All nodes multicast address as in IPv6
ALL_LINK_LOCAL_NODES_ADDRESS = ILNPAddress(int("ff01000000000000", 16), int("1", 16))


class RouterControlPlane(threading.Thread):
    def __init__(self, net_interface: NetworkInterface, packet_queue: Queue, my_address: ILNPAddress,
                 battery: Battery, forwarding_table: ForwardingTable):
        super().__init__()
        self.battery = battery
        self.my_address = my_address

        # Tracks neighbours and time since last keepalive
        self.neighbours: Dict[int, int] = {}
        self.net_interface = net_interface
        self.packet_queue = packet_queue
        self.running = False
        self.initialized = False

        # Forwarding table provides quick look-up for forwarding packets to internal and external nodes
        self.forwarding_table = forwarding_table

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
        t_wrap = build_control_wrapper(bytes(keepalive))
        packet = ILNPPacket(self.my_address, ALL_LINK_LOCAL_NODES_ADDRESS, hop_limit=0,
                            payload_length=t_wrap.size_bytes(), payload=bytes(t_wrap))

        self.net_interface.broadcast(bytes(packet))

    def __remove_expired_links(self, expired):
        # TODO
        pass

    def find_route(self, packet: ILNPPacket):
        """Uses AODV to find a route to the packets destination"""
        # TODO
        pass

    def handle_control_packet(self, packet: ILNPPacket):

        pass

