import logging
import threading
from os import urandom
from struct import unpack
from typing import Dict, List, Set

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
        self.interfaced_locators: Set[int] = {int(l) for l in conf.locators_to_ipv6}
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
        if not self.is_from_me(packet.src):
            self.dsr_service.backwards_learn(packet.src.loc, arriving_loc)

        if is_control_packet(packet):
            self.dsr_service.handle_message(packet, arriving_loc)
        else:
            self.route_packet(packet, arriving_loc)

    def is_my_address(self, locator: int, identifier: int) -> bool:
        return (locator in self.interfaced_locators) and identifier == self.my_address

    def is_from_me(self, src_address: ILNPAddress):
        return self.is_my_address(src_address.loc, src_address.id)

    def is_for_me(self, packet):
        return self.is_my_address(packet.dest_locator, packet.dest_identifier)

    def interface_exists_for_locator(self, locator):
        return locator in self.interfaced_locators

    def route_packet(self, packet: ILNPPacket, arriving_interface: int = None):
        """
        Attempts to either receive packets for this node, or to forward packets to their destination.

        If a path isn't found, its handed over to the DSR service to find a path.
        :param arriving_interface: interface packet arrived on. If not given or None, packet will be assumed
        to have been created by the host.

        :param packet: packet to be routed
        """
        if self.interface_exists_for_locator(packet.dest_locator):
            if self.is_for_me(packet):
                logging.debug("Packet added to received queue")
                self.__received_packets_queue.put(packet)
            elif packet.dest_locator is not arriving_interface:
                logging.debug("Packet being forwarded to final destination")
                # Packet needs forwarded to destination
                self.forward_packet_to_addresses(packet, [packet.dest_locator])
            elif self.is_from_me(packet) and arriving_interface is None:
                logging.debug("Packet being broadcast to my locator group {}".format(packet.dest_locator))
                # Packet from host needing broadcast to locator
                self.forward_packet_to_addresses(packet, [packet.dest_locator])
        else:
            next_hop_locator = self.dsr_service.get_next_hop(packet.dest_locator, arriving_interface)

            if next_hop_locator is None and arriving_interface is None:
                logging.debug("No route found to {} {}, requesting one."
                              .format(packet.dest_locator, packet.dest_identifier))
                self.dsr_service.find_route_for_packet(packet)
            elif next_hop_locator is not None:
                self.forward_packet_to_addresses(packet, [next_hop_locator])

    def flood(self, packet, arriving_interface=None):
        logging.debug("Flooding packet")
        next_hops = [x for x in self.interfaced_locators]

        if arriving_interface in next_hops:
            next_hops.remove(arriving_interface)

        self.forward_packet_to_addresses(packet, next_hops)

    def forward_packet_to_addresses(self, packet, next_hop_locators):
        """
        Forwards packet to locator with given value if hop limit is still greater than 0.
        Decrements hop limit by one before forwarding.
        :param packet: packet to forward
        :param next_hop_locators: set of locators (interfaces) to forward packet to
        """
        if packet.hop_limit > 0:
            logging.debug("Forwarding packet to the following locator(s): {}".format(next_hop_locators))
            packet.decrement_hop_limit()
            from_me = self.is_from_me(packet)
            packet_bytes = bytes(packet)
            for locator in next_hop_locators:
                self.__sender.sendTo(packet_bytes, locator)

                if self.monitor:
                    self.monitor.record_sent_packet(packet, from_me)
        else:
            logging.debug("Packet dropped. Hop limit reached")

    def __exit__(self):
        """Closes sockets and joins thread upon exit"""
        self.__listening_thread.stop()
        self.__listening_thread.join()
        self.__sender.close()

    def stop(self):
        self.__stop_event.set()

    def send_from_host(self, payload: bytes, destination: ILNPAddress):
        packet = ILNPPacket(self.my_address,
                            destination,
                            payload=memoryview(payload),
                            payload_length=len(payload),
                            hop_limit=self.hop_limit)

        self.__to_be_routed_queue.add(packet)
