import logging
import select
import threading
from multiprocessing import Queue
from typing import Tuple, List

from sensor.battery import Battery
from sensor.config import Configuration
from sensor.network.router.groupmessages import GroupMessage, HELLO_GROUP_TYPE, HELLO_GROUP_ACK_TYPE
from sensor.network.router.ilnp import ILNPPacket, ILNPAddress
from sensor.network.router.netinterface import NetworkInterface
from sensor.network.router.control import RouterControlPlane
from sensor.network.router.data import RouterDataPlane
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

    def __init__(self, net_interface: NetworkInterface, control_packet_queue: Queue, data_packet_queue: Queue):
        super().__init__()
        self.net_interface: NetworkInterface = net_interface
        self.control_packet_queue: Queue = control_packet_queue
        self.data_packet_queue: Queue = data_packet_queue
        self.stopped: bool = False

    def join(self, timeout=None) -> None:
        logger.info("Terminating network interface polling thread")
        self.stopped = True
        super().join(timeout)
        logger.info("Finished terminating network interface polling thread")

    def add_link_knowledge(self, packet: ILNPPacket, ipv6_addr: str):
        """If packet is one-hop type, it can provide a mapping for sending directly to neighbour links"""
        message_type = GroupMessage.parse_type(packet.payload.body)

        if message_type is HELLO_GROUP_TYPE or message_type is HELLO_GROUP_ACK_TYPE:
            logger.info("Registering node {} ({}) as link local neighbour.".format(packet.src.id, ipv6_addr))
            self.net_interface.add_id_ipv6_mapping(packet.src.id, ipv6_addr)

    def run(self):
        while not self.stopped:
            logger.info("Checking for packets from interface")
            received = self.net_interface.receive(SECONDS_BETWEEN_SHUTDOWN_CHECKS)

            if received is None:
                logger.info("No packets arrived in the last {} seconds".format(SECONDS_BETWEEN_SHUTDOWN_CHECKS))
                continue

            data = received[0]
            ipv6_addr = received[1]

            packet = parse_packet(data)

            if packet.payload.is_control_packet():
                logger.info("Received control packet from {} ({})".format(packet.src.id, ipv6_addr))
                self.add_link_knowledge(packet, ipv6_addr)
                self.control_packet_queue.put(packet)
            else:
                logger.info("Received data packet from {} ({})".format(packet.src.id, ipv6_addr))
                self.data_packet_queue.put(packet)


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
        self.control_packet_queue: Queue[ILNPPacket] = Queue()
        self.data_packet_queue: Queue[ILNPPacket] = Queue()
        # Control packet handler
        self.control_plane = RouterControlPlane(self.net_interface, self.control_packet_queue, self.my_address, battery)
        # Data packet handler
        self.data_plane = RouterDataPlane(self.net_interface, self.data_packet_queue, self.arrived_data_queue)
        # Thread for continuous polling of network interface for packets
        self.incoming_message_thread = IncomingMessageParserThread(
            self.net_interface, self.control_packet_queue, self.data_packet_queue)

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

        logger.info("Adding data packet to queue for processing")
        self.data_packet_queue.put(packet)

    def receive_from(self, blocking=True, timeout=None) -> Tuple[bytes, int]:
        logger.info("Polling arrived data queue...")
        return self.arrived_data_queue.get(blocking, timeout)

    def run(self) -> None:
        """Initializes locator then begins regular processing"""
        logger.info("Router thread starting")
        self.control_plane.initialize_locator()

        # Begin processing
        logger.info("Beginning regular processing")
        while self.running:
            logger.info("Polling incoming packet queues")
            # NOTE select on queues doesn't work in windows due to the file handles used
            queues_available, _, _ = select.select([self.data_packet_queue._reader, self.control_packet_queue._reader],
                                                   [], [],
                                                   SECONDS_BETWEEN_SHUTDOWN_CHECKS)
            if len(queues_available) > 0:
                logger.info("Data has arrived on one of the queues")
                self.handle_available_packets(queues_available)
            else:
                logger.info("No packets have arrived in the past {} seconds".format(SECONDS_BETWEEN_SHUTDOWN_CHECKS))

    def handle_available_packets(self, queues_available: List[Queue]):
        """Passes the first packet from each of the queues to the relevant handler"""
        for queue in queues_available:
            if queue is self.control_packet_queue._reader:
                self.control_plane.handle_packet(self.control_packet_queue.get())
            else:
                self.data_plane.handle_packet(self.data_packet_queue.get())
