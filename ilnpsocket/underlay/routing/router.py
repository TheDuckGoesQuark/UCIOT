import logging
import threading
from os import urandom
from queue import Queue
from struct import unpack

from ilnpsocket.underlay.routing.listeningthread import ListeningThread
from ilnpsocket.underlay.routing.packet import Packet
from ilnpsocket.underlay.sockets.listeningsocket import ListeningSocket
from ilnpsocket.underlay.sockets.sendingsocket import SendingSocket
from ilnpsocket.underlay.routing.dsrservice import DSRService


def create_receivers(locators_to_ipv6, port_number):
    """Creates a listening socket instance for each locator-ipv6 key value pair"""
    return [ListeningSocket(address, port_number, int(locator))
            for locator, address
            in locators_to_ipv6.items()]


def create_random_id():
    """
    Uses the OSs RNG to produce an id for this node.
    :return: a 64 bit id with low likelihood of collision
    """
    return unpack("!Q", urandom(8))[0]


class Router(threading.Thread):
    def __init__(self, conf, received_packets_queue, monitor):
        super(Router, self).__init__()

        self.hop_limit = conf.hop_limit

        # Assign addresses to this node
        if conf.my_id:
            self.my_id = conf.my_id
        else:
            self.my_id = create_random_id()

        self.hop_limit = conf.hop_limit
        self.interfaced_locators = {int(l) for l in conf.locators_to_ipv6}

        # packets awaiting routing or route reply
        self.__to_be_routed_queue = Queue()

        # packets for the current node
        self.__received_packets_queue = received_packets_queue

        # Create sending socket
        self.__sender = SendingSocket(conf.port, conf.locators_to_ipv6, conf.loopback)

        # Configures listening thread
        receivers = create_receivers(conf.locators_to_ipv6, conf.port)
        self.__listening_thread = ListeningThread(receivers, self, conf.packet_buffer_size_bytes)

        # Ensures that child threads die with parent
        self.__listening_thread.daemon = True
        self.__listening_thread.start()

        # Configures routing service and forwarding table
        self.dsr_service = DSRService(self, conf.router_refresh_delay_secs)

        self.monitor = monitor

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
            raise ValueError("An address cannot be obtained as this router has no interfaces.")
        else:
            return [(locator, self.my_id) for locator in self.interfaced_locators]

    def construct_host_packet(self, payload, destination):
        """
        Constructs a packet from this host to the given destination with the given payload
        :param payload: bytes to be sent
        :param destination: destination as (locator:identifier) tuple
        :return: Packet from this host to the given destination carrying the given payload
        """
        if len(payload) > Packet.MAX_PAYLOAD_SIZE:
            raise ValueError("Payload cannot exceed {} bytes. "
                             "Provided payload size: {} bytes. ".format(Packet.MAX_PAYLOAD_SIZE, len(payload)))

        packet = Packet(self.get_addresses()[0], destination,
                        payload=payload, payload_length=len(payload), hop_limit=self.hop_limit)

        return packet

    def run(self):
        """Polls for messages."""
        while True:
            logging.debug("Polling for packet...")
            packet, locator_interface = self.__to_be_routed_queue.get(block=True)

            if type(packet) is not Packet:
                continue

            if not self.is_from_me(packet):
                self.dsr_service.forwarding_table.record_entry(packet.src_locator, locator_interface,
                                                               self.hop_limit - packet.hop_limit)

            if packet.is_control_message():
                self.dsr_service.handle_message(packet, locator_interface)
            else:
                logging.debug("Received normal packet from {}-{} for {} {} on interface {}"
                              .format(packet.src_locator, packet.src_identifier,
                                      packet.dest_locator, packet.dest_identifier, locator_interface))
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

    def route_packet(self, packet, arriving_interface=None):
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
            else:
                self.forward_packet_to_addresses(packet, [next_hop_locator])

    def flood(self, packet, arriving_interface=None):
        logging.debug("Flooding packet")
        next_hops = self.interfaced_locators

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
