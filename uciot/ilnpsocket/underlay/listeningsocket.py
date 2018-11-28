import struct
import socket


class ListeningSocket:
    """Wrapper for socket instance that listens for traffic from a specific
    multicast group"""

    def __init__(self, multicast_address, port, locator):
        """
        Creates instance of listening socket
        :param multicast_address: multicast address this socket should accept traffic from
        :param port: port number this socket should accept traffic from
        :param locator: ILNP locator value this socket is the interface for
        """
        self.__multicast_address = multicast_address
        self.__port = port
        self.__sock = create_listening_socket(port, multicast_address)
        self.locator = locator

    def fileno(self):
        """Provides direct access to socket file handle for select module"""
        return self.__sock.fileno()

    def recvfrom(self, buffersize):
        return self.__sock.recvfrom(buffersize)


def create_listening_socket(port, multicast_address):
    """
    Creates a UDP datagram socket bound to listen for traffic from the given
    multicast address.
    :param port: port number to bind to
    :param multicast_address: multicast address to join
    :return: configured UDP socket
    """
    # Initialise socket for IPv6 datagrams
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Allows address to be reused
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Binds to all interfaces on the given port
    sock.bind(('', port))

    # Allow messages from this socket to loop back for development
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, True)

    # Construct message for joining multicast group
    multicast_request = struct.pack("16s15s".encode('utf-8'), socket.inet_pton(socket.AF_INET6, multicast_address),
                                    (chr(0) * 16).encode('utf-8'))
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, multicast_request)

    return sock
