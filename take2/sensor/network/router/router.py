import logging
import select
import threading
from _queue import Empty
from multiprocessing import Queue
from typing import Tuple, List

from sensor.battery import Battery
from sensor.config import Configuration
from sensor.network.router.forwardingtable import ForwardingTable
from sensor.network.router.ilnp import ILNPPacket, ILNPAddress
from sensor.network.router.netinterface import NetworkInterface
from sensor.network.router.control import RouterControlPlane
from sensor.network.router.reactive.dsrmessages import parse_type, Hello
from sensor.network.router.transportwrapper import build_data_wrapper, TransportWrapper

logger = logging.getLogger(__name__)

SECONDS_BETWEEN_SHUTDOWN_CHECKS = 3


def parse_packet(data) -> ILNPPacket:
    packet = ILNPPacket.from_bytes(data)
    packet.payload = TransportWrapper.from_bytes(packet.payload)
    return packet


class IncomingMessageParserThread(threading.Thread):
    """
    Polls network interface for incoming messages, parses them into ILNPPackets, and adds them to the queue for later
    processing.

    Thread checks if it should continue after every three seconds data is not received,
    and after each packet is received.

    Also provides ID <-> IPv6 address mapping as HelloGroup messages will only arrive from one hop neighbours
    """

    def __init__(self, net_interface: NetworkInterface, packet_queue: Queue):
        super().__init__()
        self.net_interface: NetworkInterface = net_interface
        self.packet_queue: Queue = packet_queue
        self.stopped: bool = False

    def join(self, timeout=None) -> None:
        logger.info("Terminating network interface polling thread")
        self.stopped = True
        super().join(timeout)
        logger.info("Finished terminating network interface polling thread")

    def add_link_knowledge(self, packet: ILNPPacket, ipv6_addr: str):
        """If packet is HELLO, it can provide a mapping for sending directly to neighbour links"""
        message_type = parse_type(memoryview(packet.payload.body))

        if message_type is Hello.TYPE:
            logger.info("Registering node {} ({}) as link local neighbour.".format(packet.src.id, ipv6_addr))
            self.net_interface.add_id_ipv6_mapping(packet.src.id, ipv6_addr)

    def run(self):
        while not self.stopped:
            logger.info("Checking for packets from interface")
            received = self.net_interface.receive(SECONDS_BETWEEN_SHUTDOWN_CHECKS)

            if received is None:
                continue

            data = received[0]
            ipv6_addr = received[1]

            packet = parse_packet(data)

            if packet.payload.is_control_packet():
                self.add_link_knowledge(packet, ipv6_addr)

            self.packet_queue.put(packet)


class Router(threading.Thread):
    """
    Router handles data and control packet processing and forwarding
    """

    def __init__(self, config: Configuration, battery: Battery):
        super().__init__()
        self.my_address = ILNPAddress(config.my_locator, config.my_id)

        # Data for this ID, with the ID that sent it
        self.arrived_data_queue: Queue[Tuple[bytes, int]] = Queue()
        # Interface for sending data
        self.net_interface: NetworkInterface = NetworkInterface(config, battery)
        # Data received from net interface needing processed
        self.packet_queue: Queue[ILNPPacket] = Queue()
        # Control packet handler
        self.forwarding_table = ForwardingTable()
        self.control_plane = RouterControlPlane(self.net_interface, self.packet_queue, self.my_address, battery,
                                                self.forwarding_table, config.max_radius)
        # Thread for continuous polling of network interface for packets
        self.incoming_message_thread = IncomingMessageParserThread(
            self.net_interface, self.packet_queue)

        self.incoming_message_thread.daemon = True
        self.incoming_message_thread.start()

        self.control_plane.daemon = True
        self.control_plane.start()

        self.running = True

    def join(self, **kwargs):
        """Terminates this thread, and cleans up any resources or threads it has open"""
        logger.info("Terminating routing thread")
        self.running = False
        logger.info("Waiting on network interface to close")
        self.net_interface.close()
        logger.info("Waiting on incoming message thread to terminate")
        self.incoming_message_thread.join()
        logger.info("Waiting on control plane thread terminating")
        self.control_plane.join()
        logger.info("Joining router thread")
        super().join()
        logger.info("Finished terminating routing thread")

    def send(self, data, dest_id):
        """
         Wraps the given data in an ILNPPacket for the given destination ID,
        and adds it to the queue to be processed
        :param data: data to be sent
        :param dest_id: id of node to be sent to
        """
        logger.info("Wrapping data to be sent")
        t_wrap = build_data_wrapper(data)

        # Locator can't be assigned immediately, since it could change before packet gets processed
        src_addr = ILNPAddress(None, self.my_address.id)
        dest_addr = ILNPAddress(None, dest_id)
        packet = ILNPPacket(src_addr, dest_addr, payload=t_wrap, payload_length=t_wrap.size_bytes())

        self.packet_queue.put(packet)

    def receive_from(self, blocking=True, timeout=None) -> Tuple[bytes, int]:
        return self.arrived_data_queue.get(blocking, timeout)

    def run(self) -> None:
        """Initializes locator then begins regular processing"""
        logger.info("Router thread starting")
        self.control_plane.initialize_locator()

        # Begin processing
        logger.info("Beginning regular processing")
        while self.running:
            packet = self.packet_queue.get(timeout=SECONDS_BETWEEN_SHUTDOWN_CHECKS)

            if packet is not None:
                logger.info("Data has arrived on one of the queues")
                self.handle_packet(packet)
            else:
                logger.info("No packets have arrived in the past {} seconds".format(SECONDS_BETWEEN_SHUTDOWN_CHECKS))

    def handle_data_packet(self, packet: ILNPPacket):
        """Attempt basic routing of packet using available resources"""
        logger.info("Handling data packet")
        if packet.dest.id == self.my_address.id:
            logger.info("Packet for me, adding to received queue <3")
            self.arrived_data_queue.put((packet.payload.body, packet.src.id))
            return

        next_hop = self.forwarding_table.get_next_hop(packet.dest.id)

        if next_hop is not None:
            logger.info("Found next hop, forwarding to {}".format(next_hop))
            self.net_interface.send(bytes(packet), next_hop)
        elif packet.src.id == self.my_address.id:
            logger.info("No next hop found for packet originating from this node.")
            logger.info("Requesting route reactive routing.")
            self.control_plane.find_route(packet)
        else:
            logger.info("No next hop found for packet. Dropping packet.")

    def handle_packet(self, packet: ILNPPacket):
        """Passes the first packet from each of the queues to the relevant handler"""
        if packet.payload.is_control_packet():
            self.control_plane.handle_control_packet(packet)
        else:
            self.handle_data_packet(packet)
