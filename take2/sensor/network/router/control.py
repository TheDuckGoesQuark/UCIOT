import logging
import threading
import time
from multiprocessing import Queue
from typing import Tuple, List, Dict

from sensor.battery import Battery
from sensor.network.router.ilnp import ILNPAddress, ILNPPacket
from sensor.network.router.forwardingtable import ForwardingTable
from sensor.network.router.netinterface import NetworkInterface
from sensor.network.router.reactive.dsrmessages import Hello, RouteError, parse_type
from sensor.network.router.transportwrapper import build_local_control_wrapper, LOCAL_CONTROL_TYPE

logger = logging.getLogger(__name__)

LOAD_PERCENTAGE = 50
KEEP_ALIVE_INTERVAL_SECS = 3
MAX_AGE_OF_LINK = KEEP_ALIVE_INTERVAL_SECS * 3

# Max lambda is given by the range of 4 bytes
MAX_LAMBDA = (2 ** (4 * 8)) - 1


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

    def __send_keepalive(self):
        logger.info("Sending keepalive")
        keepalive = Hello()
        t_wrap = build_local_control_wrapper(bytes(keepalive))
        packet = ILNPPacket(self.my_address, ILNPAddress(self.my_address.loc, 0), hop_limit=0,
                            payload_length=t_wrap.size_bytes(), payload=bytes(t_wrap))

        self.net_interface.broadcast(bytes(packet))

    def calc_my_lambda(self):
        return int(1 - (1 - self.battery.percentage()) ** 2) * MAX_LAMBDA

    def __keepalive_handler(self, packet: ILNPPacket):
        pass

    def handle_group_message(self, packet: ILNPPacket):
        type_val = parse_type(packet.payload.body)

    def handle_control_packet(self, packet: ILNPPacket):
        pass
