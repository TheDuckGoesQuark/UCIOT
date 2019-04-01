import logging
import select
import socket
import struct
from typing import Dict, Tuple, List

from sensor.config import Configuration
from sensor.router import Router

logger = logging.getLogger(name=__name__)


def add_group_to_socket(sock: socket.socket, group: str):
    # Look up multicast group address in name server and find out IP version
    addrinfo = socket.getaddrinfo(group, None)[0]
    group_bin = socket.inet_pton(addrinfo[0], addrinfo[4][0])
    mreq = group_bin + struct.pack('@I', 0)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)


def create_mcast_socket(port: int, multicast_addresses: List[str], loopback: bool) -> socket.socket:
    """
    Creates a UDP datagram socket bound to listen for traffic from the given
    multicast address.
    :param port: port number to bind to
    :param multicast_addresses:
    :param loopback: if messages sent to the multicast group should be returned to this socket
    :return: configured UDP socket
    """
    # Get multicast group address in name server
    addrinfo = socket.getaddrinfo(multicast_addresses[0], None)[0]

    # Initialise socket for IPv6 datagrams
    sock = socket.socket(addrinfo[0], socket.SOCK_DGRAM)

    # Allow multiple instances of socket on machine
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Sets loopback
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, loopback)

    # Bind to all interfaces on this port
    sock.bind(('', port))

    # Join groups
    for group in multicast_addresses:
        add_group_to_socket(sock, group)

    return sock


class NetworkInterface:
    def __init__(self, config: Configuration):
        super().__init__()
        self.id_to_ipv6: Dict[int:str] = {}
        self.ipv6_groups = config.mcast_groups
        self.port = config.port
        self.socket = create_mcast_socket(config.port, self.ipv6_groups, config.loopback)
        self.buffer_size: int = config.packet_buffer_size_bytes
        self.router: Router = Router()

    def send(self, bytes_to_send: bytes, dest_id: int):
        """
        Sends the supplied bytes to only the specified node id
        :param bytes_to_send: bytes to be sent
        :param dest_id: id of node to be sent to
        """
        next_hop = self.router.get_next_hop(dest_id)
        ip_next_hop = self.id_to_ipv6[next_hop]

        logger.info("Sending to {} ({})".format(next_hop, ip_next_hop))

        self.socket.sendto(bytes_to_send, ip_next_hop)

    def broadcast(self, bytes_to_send: bytes):
        """
        Sends the supplied bytes to all multicast groups this node belong to
        :param bytes_to_send: bytes to be sent
        """
        logger.info("Broadcasting message")
        for addr in self.ipv6_groups:
            logger.info("Sending to {}".format(addr))
            self.socket.sendto(bytes_to_send, (addr, self.port))

        logger.info("Finished broadcasting message")

    def receive(self, timeout=None) -> Tuple[bytearray, str]:
        buffer = bytearray(self.buffer_size)

        n_bytes_read, addr_info = sock.recvfrom_into(buffer, len(buffer))
        src_ipv6_addr = addr_info[0]

        return buffer[:n_bytes_read], src_ipv6_addr

    def close(self):
        """Close all sockets"""
        for addr, mcast_socket in self.sockets.items():
            logger.info("Closing network interface")
            mcast_socket.close()

        logger.info("Finish closing underlying sockets")
        self.closed = True

# recv_from returns ip address of origin node, treat that like MAC address

# Receiving packet maps src IP address to identifier, allowing directed sending (like MAC address in 802.11).
