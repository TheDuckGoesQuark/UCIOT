import logging
import select
import socket
import struct
from typing import Dict, Tuple, List, Optional

from sensor.config import Configuration

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
        self.sock = create_mcast_socket(config.port, self.ipv6_groups, config.loopback)
        self.buffer_size: int = config.packet_buffer_size_bytes
        self.closed = False

    def send(self, bytes_to_send: bytes, next_hop_id: int):
        """
        Sends the supplied bytes to only the specified node id
        :param bytes_to_send: bytes to be sent
        :param next_hop_id: id of node to be sent to
        """
        ip_next_hop = self.id_to_ipv6[next_hop_id]

        logger.info("Sending to {} ({})".format(next_hop_id, ip_next_hop))

        self.sock.sendto(bytes_to_send, (ip_next_hop, self.port))

    def broadcast(self, bytes_to_send: bytes):
        """
        Sends the supplied bytes to all multicast groups this node belong to
        :param bytes_to_send: bytes to be sent
        """
        logger.info("Broadcasting message")
        for addr in self.ipv6_groups:
            logger.info("Sending to {}".format(addr))
            self.sock.sendto(bytes_to_send, (addr, self.port))

        logger.info("Finished broadcasting message")

    def add_id_ipv6_mapping(self, identifier: int, ipv6: str):
        """
        Registers this given identifer to the given ipv6 address.
        Emulates neighbour discovery and layer 2 addresses
        :param identifier: identifier of node
        :param ipv6: ipv6 address of node
        """
        self.id_to_ipv6[identifier] = ipv6

    def receive(self, timeout=None) -> Optional[Tuple[bytearray, str]]:
        """
        Receive bytes from the interface. Blocks until available unless timeout is set.

        If timeout is set and no data is available within the timeout, then None is returned
        :param timeout: n seconds to block.
        :return: received bytes and origin ipv6 address as two element tuple
        :raises TimeoutError
        """
        buffer = bytearray(self.buffer_size)

        logger.info("Waiting for data to arrive")
        ready, _, _ = select.select([self.sock.recvfrom_into(buffer, len(buffer))], [], [], timeout)

        if len(ready) == 0:
            return None

        n_bytes_read, addr_info = self.sock.recvfrom_into(buffer, len(buffer))
        src_ipv6_addr = addr_info[0]
        logger.info("Data arrived from {}".format(src_ipv6_addr))

        return buffer[:n_bytes_read], src_ipv6_addr

    def close(self):
        """Closes underlying socket"""
        logger.info("Closing network interface")
        self.sock.close()

        logger.info("Finish closing underlying sockets")
        self.closed = True

    def is_closed(self) -> bool:
        """Checks if the underlyin sockets are closed"""
        return self.closed

