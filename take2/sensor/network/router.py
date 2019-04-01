import threading
from multiprocessing import Queue
from typing import Tuple, Optional

from sensor.config import Configuration
from sensor.network.groupmessages import GroupMessage, HELLO_GROUP_TYPE, HELLO_GROUP_ACK_TYPE
from sensor.network.ilnp import ILNPPacket, ILNPAddress
from sensor.network.netinterface import NetworkInterface
from sensor.network.transportwrapper import build_data_wrapper, TransportWrapper


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

    SECONDS_BETWEEN_SHUTDOWN_CHECKS = 3

    def __init__(self, net_interface: NetworkInterface, packet_queue: Queue[ILNPPacket]):
        super().__init__()
        self.net_interface: NetworkInterface = net_interface
        self.packet_queue: Queue[ILNPPacket] = packet_queue
        self.stopped: bool = False

    def join(self, timeout: Optional[float] = ...) -> None:
        self.stopped = True
        super().join(timeout)

    def add_link_knowledge(self, packet: ILNPPacket, ipv6_addr: str):
        """If packet is one-hop type, it can provide a mapping for sending directly to neighbour links"""
        message_type = GroupMessage.parse_type(packet.payload.body)

        if message_type is HELLO_GROUP_TYPE or message_type is HELLO_GROUP_ACK_TYPE:
            self.net_interface.add_id_ipv6_mapping(packet.src.id, ipv6_addr)

    def run(self):
        while not self.stopped:
            received = self.net_interface.receive(self.SECONDS_BETWEEN_SHUTDOWN_CHECKS)

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

    def __init__(self, config: Configuration):
        super().__init__()
        self.my_id = config.my_id
        self.my_locator = config.my_locator

        # Data for this ID, with the ID that sent it
        self.arrived_data_queue: Queue[Tuple[bytes, int]] = Queue()

        # Interface for sending data
        self.net_interface: NetworkInterface = NetworkInterface(config)
        # Data received from net interface needing processed
        self.awaiting_processing_queue: Queue[ILNPPacket] = Queue()
        # Thread for continuous polling of network interface for packets
        self.incoming_message_thread = IncomingMessageParserThread(self.net_interface, self.awaiting_processing_queue)
        self.incoming_message_thread.daemon = True
        self.incoming_message_thread.start()

    def join(self, **kwargs):
        """Terminates this thread, and cleans up any resources or threads it has open"""
        self.net_interface.close()
        self.incoming_message_thread.join()
        super().join()

    def get_next_hop(self, dest_id) -> int:
        """Get the ID of the next hop in order to reach the node with the given destination ID"""
        # TODO
        return dest_id

    def send(self, data, dest_id):
        """
         Wraps the given data in an ILNPPacket for the given destination ID,
        and adds it to the queue to be processed
        :param data: data to be sent
        :param dest_id: id of node to be sent to
        """
        t_wrap = build_data_wrapper(data)

        src_addr = ILNPAddress(self.my_locator, self.my_id)
        dest_addr = ILNPAddress(None, dest_id)
        packet = ILNPPacket(src_addr, dest_addr, payload=t_wrap, payload_length=len(t_wrap.size_bytes()))

        self.awaiting_processing_queue.put(packet)

    def receive_from(self, blocking=True, timeout=None) -> Tuple[bytes, int]:
        return self.arrived_data_queue.get(blocking, timeout)
