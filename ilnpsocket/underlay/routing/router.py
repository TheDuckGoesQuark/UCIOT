import threading
from os import urandom
from queue import Queue
from struct import unpack

from ilnpsocket.underlay.listeningthread import ListeningThread
from ilnpsocket.underlay.headers.packet import Packet
from ilnpsocket.underlay.routing.routingtable import RoutingTable
from ilnpsocket.underlay.sockets.listeningsocket import ListeningSocket
from ilnpsocket.underlay.sockets.sendingsocket import SendingSocket


def create_receivers(locators_to_ipv6, port_number):
    """Creates a listening socket instance for each locator-ipv6 key value pair"""
    return [ListeningSocket(address, port_number, locator)
            for locator, address
            in locators_to_ipv6.items()]


def create_random_id():
    """
    Uses the OSs RNG to produce an id for this node.
    :return: a 64 bit id with low likelihood of collision
    """
    return unpack("!Q", urandom(8))[0]


class Router(threading.Thread):
    def __init__(self, conf, received_packets_queue):
        super(Router, self).__init__()

        # Assign addresses to this node
        if conf.my_id:
            self.my_id = conf.my_id
        else:
            self.my_id = create_random_id()

        self.hop_limit = conf.hop_limit
        self.interfaced_locators = {int(l) for l in conf.locators_to_ipv6}

        # packets awaiting routing
        self.__to_be_routed_queue = Queue()

        # packets for the current node
        self.__received_packets_queue = received_packets_queue

        # Create sending socket
        self.__sender = SendingSocket(conf.port, conf.locators_to_ipv6)

        # Configures listening thread
        receivers = create_receivers(conf.locators_to_ipv6, conf.port)
        self.__listening_thread = ListeningThread(receivers, self)

        # Ensures that child threads die with parent
        self.__listening_thread.daemon = True
        self.__listening_thread.start()

        # Configures routing table
        self.routing_table = RoutingTable(conf.hop_limit, conf.router_refresh_delay_secs)

    def add_to_route_queue(self, packet_to_route, arriving_locator=None):
        """
        Adds the given packet to the queue waiting to be routed, alongside the locator value the packet arrived from.
        Defaults to None when the packet was created locally.

        :param packet_to_route: packet instance to be routed
        :param arriving_locator: locator value that packet arrived from
        """
        self.__to_be_routed_queue.put((packet_to_route, arriving_locator))

    def get_addresses(self):
        """
        If no interfaces are configured, a ValueError is raised as no address exists.
        :return: a list of tuples of locator:identifier pairs that can be used as an address for this host.
        """
        if self.interfaced_locators is None or len(self.interfaced_locators) == 0:
            raise ValueError("An address cannot be obtained if this router has no interfaces.")
        else:
            return [(locator, self.my_id) for locator in self.interfaced_locators]

    def construct_host_packet(self, payload, destination):
        """
        Constructs a packet from this host to the given destination with the given payload
        :param payload: bytes to be sent
        :param destination: destination as (locator:identifier) tuple
        :return: Packet from this host to the given destination carrying the given payload
        """
        return Packet(payload, self.get_addresses()[0], destination, hop_limit=self.hop_limit)

    def run(self):
        """Polls for messages."""
        while True:
            packet, locator_interface = self.__to_be_routed_queue.get(block=True)

            if type(packet) is not Packet:
                continue

            if not self.is_from_me(packet):
                self.routing_table.update_routing_table(packet, locator_interface)

            self.route_packet(packet, locator_interface)

            self.__to_be_routed_queue.task_done()

    def is_my_address(self, locator, identifier):
        return (locator in self.interfaced_locators) and identifier == self.my_id

    def is_from_me(self, packet):
        return self.is_my_address(packet.src_locator, packet.src_identifier)

    def is_for_me(self, packet):
        return self.is_my_address(packet.dest_locator, packet.dest_identifier)

    def interface_exists_for_locator(self, locator):
        return locator in self.interfaced_locators

    def get_next_hops(self, dest_locator):
        next_hop = self.routing_table.find_next_hop(dest_locator)

        if next_hop is None:
            return self.interfaced_locators
        else:
            return next_hop

    def route_packet(self, packet, locator_interface=None):
        """
        Attempts to either receive packets for this node, or to forward packets to their destination
        :param packet: packet to be routed
        :param locator_interface: locator that packet arrived from. Default value of None
        implies that packet was created by this node to be routed
        """
        if self.interface_exists_for_locator(packet.dest_locator):
            if self.is_for_me(packet):
                self.__received_packets_queue.put(packet)
            elif packet.dest_locator is not locator_interface:
                # Packet needs bridged to destination
                self.forward_packet(packet, [packet.dest_locator])
            elif self.is_from_me(packet) and locator_interface is None:
                # Packet from host needing broadcast to locator
                self.forward_packet(packet, [packet.dest_locator])
        else:
            next_hop_locators = self.get_next_hops(packet.dest_locator)
            self.forward_packet(packet, next_hop_locators)

    def forward_packet(self, packet, next_hop_locators):
        """
        Forwards packet to locator with given value if hop limit is still greater than 0.
        Decrements hop limit by one before forwarding.
        :param packet: packet to forward
        :param next_hop_locators: set of locators (interfaces) to forward packet to
        """
        if packet.hop_limit > 0:
            packet.decrement_hop_limit()
            for locator in next_hop_locators:
                packet_bytes = packet.to_bytes()
                self.__sender.sendTo(packet_bytes, locator)

    def __enter__(self):
        return self

    def __exit__(self):
        """Closes sockets and joins thread upon exit"""
        self.__listening_thread.stop()
        self.__listening_thread.join()
        self.__sender.close()

