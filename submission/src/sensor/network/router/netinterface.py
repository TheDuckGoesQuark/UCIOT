import logging
import select
import socket
import struct
from typing import Dict, Tuple, List, Optional

from sensor.battery import Battery
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
    def __init__(self, config: Configuration, battery: Battery):
        super().__init__()
        self.id_to_ipv6: Dict[int:str] = {}
        self.battery = battery
        self.ipv6_groups = config.mcast_groups
        self.my_ipv6_group = config.my_ipv6_group
        self.port = config.port
        self.sock = create_mcast_socket(config.port, self.ipv6_groups, config.loopback)
        self.buffer_size: int = config.packet_buffer_size_bytes
        self.closed = False

    def handle_battery_failure(self):
        self.close()
        raise IOError("Not enough battery to send or receive packets")

    def send(self, bytes_to_send: bytes, next_hop_id: int):
        """
        Sends the supplied bytes to only the specified node id
        :param bytes_to_send: bytes to be sent
        :param next_hop_id: id of node to be sent to
        :raises KeyError if next hop id is not known on this link
        """
        if self.battery.remaining() <= 0:
            self.handle_battery_failure()

        try:
            ip_next_hop = self.id_to_ipv6[next_hop_id]

            logger.info("Sending to {} ({})".format(next_hop_id, ip_next_hop))
            self.sock.sendto(bytes_to_send, (ip_next_hop, self.port))
            self.battery.decrement()
        except Exception as e:
            logger.info("Something went wrong when trying to send to {}".format(next_hop_id))
            logger.info(str(e))


    def broadcast(self, bytes_to_send: bytes):
        """
        Sends the supplied bytes to the multicast group this node belong to
        :param bytes_to_send: bytes to be sent
        """
        if self.battery.remaining() <= 0:
            self.handle_battery_failure()

        logger.info("Broadcasting message")
        logger.info("Sending to {}".format(self.my_ipv6_group))
        self.sock.sendto(bytes_to_send, (self.my_ipv6_group, self.port))
        self.battery.decrement()
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
        # Select provides timeout to socket polling
        try:
            ready, _, _ = select.select([self.sock], [], [], timeout)

            if len(ready) == 0:
                return None

            buffer = bytearray(self.buffer_size)
            n_bytes_read, addr_info = self.sock.recvfrom_into(buffer, len(buffer))
            src_ipv6_addr = addr_info[0]

            return buffer[:n_bytes_read], src_ipv6_addr
        except ValueError:
            logger.info("Nothing left to read from socket")
            self.close()

    def close(self):
        """Closes underlying socket"""
        logger.info("Closing network interface")
        self.sock.close()

        logger.info("Finish closing underlying sockets")
        self.closed = True

    def is_closed(self) -> bool:
        """Checks if the underlying sockets are closed"""
        return self.closed
