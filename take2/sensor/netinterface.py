import logging
import select
import socket
import struct
import threading
from multiprocessing import Queue
from typing import Dict, Tuple

from sensor.config import Configuration

logger = logging.getLogger(name=__name__)


def get_interface_index() -> int:
    known_names = ["enp4s0", "enp2s0"]
    for idx, name in enumerate(known_names):
        try:
            index = socket.if_nametoindex(name)
            logger.debug("socket %s chosen", name)
            return index
        except OSError as err:
            # If no more left to try, die
            if idx == (len(known_names) - 1):
                raise err


def create_socket(port: int, multicast_address: str, loopback: bool) -> socket.socket:
    """
    Creates a UDP datagram socket bound to listen for traffic from the given
    multicast address.
    :param port: port number to bind to
    :param multicast_address: multicast address to join
    :return: configured UDP socket
    """
    # Initialise socket for IPv6 datagrams
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Stops address from being reused
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, loopback)

    # Get interface to use
    interface_index = get_interface_index()

    # Bind to the one interface on the given port
    logger.debug("Binding listening socket to addr %s port %d, interface_idx %d", multicast_address, port,
                 interface_index)
    sock.bind((multicast_address, port, 0, interface_index))

    # Construct message for joining multicast group
    multicast_request = struct.pack("16s15s".encode('utf-8'), socket.inet_pton(socket.AF_INET6, multicast_address),
                                    (chr(0) * 16).encode('utf-8'))
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, multicast_request)

    return sock


def create_sock_dict(config: Configuration) -> Dict[Tuple[str, int], socket.socket]:
    return {(addr, config.port): create_socket(config.port, addr, config.loopback) for
            addr in
            config.mcast_groups}


class NetworkInterface(threading.Thread):
    def __init__(self, config: Configuration):
        super().__init__()
        self.sockets: Dict[Tuple[str, int], socket.socket] = create_sock_dict(config)
        self.buffer: Queue[bytes] = Queue()
        self.closed = False
        self.buffer_size = config.packet_buffer_size_bytes

    def run(self) -> None:
        """Continuously checks for incoming packets on each listening socket and
        adds new packets to the message queue"""
        logger.info("Running network interface listening thread")
        while not self.closed:
            ready_socks, _, _ = select.select(self.sockets.values(), [], [])
            for sock in ready_socks:
                self.read_sock(sock)

    def read_sock(self, sock: socket.socket):
        buffer = bytearray(self.buffer_size)
        n_bytes_read, addr_info = sock.recvfrom_into(buffer, len(buffer))

        logging.debug("Packet parsed from socket: {}".format(buffer.decode("utf-8")))
        self.buffer.put(buffer[:n_bytes_read])

    def send(self, bytes_to_send):
        """
        Sends the supplied bytes to all multicast groups this node belong to
        :param bytes_to_send: bytes to be sent
        """
        for addr, mcast_socket in self.sockets.items():
            logger.info("Sending to {}".format(addr))
            mcast_socket.sendto(bytes_to_send, addr)

    def receive(self, block=True, timeout=None):
        """Poll for bytes arriving on any interface"""
        return self.buffer.get(block, timeout)

    def close(self):
        """Close all sockets"""
        logger.info("Closing network interface")
        for addr, mcast_socket in self.sockets.items():
            mcast_socket.close()

        logger.info("Finish closing underlying sockets")
        self.closed = True
