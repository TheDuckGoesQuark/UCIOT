import threading
from os import urandom
from queue import Queue
from struct import unpack

from uciot.ilnpsocket.underlay.listeningsocket import ListeningSocket
from uciot.ilnpsocket.underlay.listeningthread import ListeningThread
from uciot.ilnpsocket.underlay.sendingsocket import SendingSocket


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
        # Parse config file
        port_number = conf.port
        locators_to_ipv6 = conf.locators_to_ipv6

        # Assign addresses to this node
        my_id = create_random_id()
        self.my_locators = {locator for locator in locators_to_ipv6}
        self.my_addresses = {(locator, my_id) for locator in self.my_locators}
        self.routing_table = RoutingTable()

        # packets awaiting routing
        self.__to_be_routed_queue = Queue()

        # packets for the current node
        self.__received_packets_queue = received_packets_queue

        # Create sending socket
        self.__locators_to_ipv6 = locators_to_ipv6
        self.__sender = SendingSocket(port_number)

        # Configures listening thread
        receivers = create_receivers(locators_to_ipv6, port_number)
        self.__listening_thread = ListeningThread(receivers, self)

        # Ensures that child threads die with parent
        self.__listening_thread.daemon = True
        self.__listening_thread.start()

    def add_to_route_queue(self, packet_to_route, arriving_locator=None):
        """
        Adds the given packet to the queue waiting to be routed, alongside the locator value the packet arrived from.
        Defaults to None when the packet was created locally.

        :param packet_to_route: packet instance to be routed
        :param arriving_locator: locator value that packet arrived from
        """
        self.__to_be_routed_queue.put((packet_to_route, arriving_locator))

    def run(self):
        """Polls for messages."""
        while True:
            packet, arrived_from = self.__to_be_routed_queue.get(block=True)

            if not self.is_from_me(packet):
                self.routing_table.update(packet.src_locator, arrived_from)

            self.route_packet(packet, arrived_from)

            self.__to_be_routed_queue.task_done()

    def is_my_address(self, locator, identifier):
        return (locator, identifier) in self.my_addresses

    def is_from_me(self, packet):
        return self.is_my_address(packet.src_locator, packet.src_identfier)

    def is_for_me(self, packet):
        return self.is_my_address(packet.dest_locator, packet.dest_identifier)

    def route_packet(self, packet, arrived_from_locator):
        if packet.dest_locator in self.my_locators:
            if self.is_for_me(packet):
                self.__received_packets_queue.put(packet)
            elif packet.dest_locator is not arrived_from_locator:
                self.forward_packet(packet, packet.dest_locator)
        else:
            next_hop_locator = self.routing_table.find_next_hop(packet.dest_locator)
            if next_hop_locator is not None:
                self.forward_packet(packet, next_hop_locator)

    def forward_packet(self, packet, next_hop_locator):
        return self.__sender.sendTo(packet.to_bytes(), self.__locators_to_ipv6[next_hop_locator])

    def __enter__(self):
        return self

    def __exit__(self):
        """Closes sockets and joins thread upon exit"""
        self.__listening_thread.stop()
        self.__listening_thread.join()
        self.__sender.close()


class RoutingTable():
    def __init__(self):
        pass

    def update(self, packet_origin_locator, packet):
        pass

    def find_next_hop(self, packet_dest_locator):
        return None
