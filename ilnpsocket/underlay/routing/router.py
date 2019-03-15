import logging
import threading
from os import urandom
from struct import unpack
from typing import Dict, List, Set, Iterable

from experiment.config import Config
from experiment.tools import Monitor
from underlay.routing.dsrservice import DSRService
from underlay.routing.ilnpaddress import ILNPAddress
from underlay.routing.ilnppacket import ILNPPacket, DSR_NEXT_HEADER_VALUE
from underlay.routing.listeningthread import ListeningThread
from underlay.routing.queues import ReceivedQueue, PacketQueue
from underlay.sockets.listeningsocket import ListeningSocket
from underlay.sockets.sendingsocket import SendingSocket


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


class Router(threading.Thread):
    def __init__(self, conf: Config, received_packets_queue: ReceivedQueue, monitor: Monitor):

        super(Router, self).__init__()

        self.__stop_event: threading.Event() = threading.Event()
        self.hop_limit: int = conf.hop_limit

        # Assign addresses to this node
        self.my_locators: Set[int] = {int(l) for l in conf.locators_to_ipv6}
        self.my_id: int = conf.my_id if conf.my_id is not None else create_random_id()
        self.__to_be_routed_queue: PacketQueue = PacketQueue()
        self.__received_packets_queue = received_packets_queue
        self.__sender = SendingSocket(conf.port, conf.locators_to_ipv6, conf.loopback)

        # Configures listening thread
        receivers = create_receivers(conf.locators_to_ipv6, conf.port)
        self.__listening_thread = ListeningThread(receivers, self.__to_be_routed_queue, conf.packet_buffer_size_bytes)

        # Ensures that child threads die with parent
        self.__listening_thread.daemon = True
        self.__listening_thread.start()

        # Configures routing service and forwarding table
        self.dsr_service = DSRService(self, conf.router_refresh_delay_secs)

        self.monitor = monitor

    def run(self):
        """Polls for messages."""
        while not self.__stop_event.is_set():
            logging.debug("Polling for packet...")

            packet: ILNPPacket
            arriving_loc: int
            packet, arriving_loc = self.__to_be_routed_queue.get(block=True)

            self.handle_packet(packet, arriving_loc)
            self.__to_be_routed_queue.task_done()

    def handle_packet(self, packet: ILNPPacket, arriving_loc: int):
        if not self.is_from_me(packet):
            self.dsr_service.backwards_learn(packet.src.loc, arriving_loc)

        if is_control_packet(packet):
            self.dsr_service.handle_message(packet, arriving_loc)
        else:
            self.route_packet(packet, arriving_loc)

    def is_my_address(self, address: ILNPAddress) -> bool:
        return (address.loc in self.my_locators) and address.id == self.my_id

    def is_from_me(self, packet: ILNPPacket) -> bool:
        return self.is_my_address(packet.src)

    def is_for_me(self, packet: ILNPPacket) -> bool:
        return self.is_my_address(packet.dest)

    def interface_exists_for_locator(self, locator: int) -> bool:
        return locator in self.my_locators

    def route_packet(self, packet: ILNPPacket, arriving_interface: int = None):
        if self.interface_exists_for_locator(packet.dest.loc):
            self.route_to_adjacent_node(packet, arriving_interface)
        else:
            self.route_to_remote_node(packet, arriving_interface)

    def route_to_remote_node(self, packet: ILNPPacket, arriving_interface: int):
        next_hop_locator = self.dsr_service.get_next_hop(packet.dest.loc, arriving_interface)

        if next_hop_locator is None and arriving_interface is None:
            self.dsr_service.find_route_for_packet(packet)
        elif next_hop_locator is not None:
            self.forward_packet_to_addresses(packet, [next_hop_locator])

    def route_to_adjacent_node(self, packet: ILNPPacket, arriving_interface: int):
        if self.is_for_me(packet):
            self.__received_packets_queue.add(packet.payload)
        elif packet.dest.loc != arriving_interface or arriving_interface is None:
            self.forward_packet_to_addresses(packet, [packet.dest.loc])

    def flood_to_neighbours(self, packet: ILNPPacket, arriving_interface: int = None):
        next_hops = [x for x in self.my_locators]

        if arriving_interface in next_hops:
            next_hops.remove(arriving_interface)

        self.forward_packet_to_addresses(packet, next_hops)

    def forward_packet_to_addresses(self, packet: ILNPPacket, next_hop_locators: Iterable[int]):
        """
        Forwards packet to locator with given value if hop limit is still greater than 0.
        Decrements hop limit by one before forwarding.
        :param packet: packet to forward
        :param next_hop_locators: set of locators (interfaces) to forward packet to
        """
        if packet.hop_limit < 0:
            return

        packet.decrement_hop_limit()
        from_me = self.is_from_me(packet)
        packet_bytes = bytes(packet)
        for locator in next_hop_locators:
            self.__sender.sendTo(packet_bytes, locator)

            if self.monitor:
                self.monitor.record_sent_packet(packet, from_me)

    def stop(self):
        self.__stop_event.set()
        self.__listening_thread.stop()
        self.__listening_thread.join()
        self.__sender.close()
        self.dsr_service.stop()

    def construct_host_packet(self, payload: bytes, dest: ILNPAddress) -> ILNPPacket:
        return ILNPPacket(ILNPAddress(next(x for x in self.my_locators), self.my_id),
                          dest,
                          payload=memoryview(payload),
                          payload_length=len(payload),
                          hop_limit=self.hop_limit)

    def send_from_host(self, payload: bytes, destination: ILNPAddress):
        self.__to_be_routed_queue.add(self.construct_host_packet(payload, destination))
