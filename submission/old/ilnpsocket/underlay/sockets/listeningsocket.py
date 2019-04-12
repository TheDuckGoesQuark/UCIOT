import logging
import struct
import socket


class ListeningSocket:
    """Wrapper for socket instance that listens for traffic from a specific
    multicast group and provides mapping from locator to ipv6 address"""

    def __init__(self, multicast_address: str, port: int, locator: int):
        """
        Creates instance of listening socket
        :param multicast_address: multicast address this socket should accept traffic from
        :param port: port number this socket should accept traffic from
        :param locator: ILNP locator value this socket is the interface for
        """
        self.multicast_address: str = multicast_address
        self.__port: int = port
        self.__sock: socket.socket = create_listening_socket(port, multicast_address)
        self.locator: int = locator

    def fileno(self):
        """Provides direct access to socket file handle for select module"""
        return self.__sock.fileno()

    def recvfrom_into(self, buffer: bytearray, buffer_size: int = None):
        """
        Reads socket contents into given buffer
        :param buffer: buffer to read socket contents into
        :param buffer_size: size of buffer
        """
        if buffer_size is None:
            buffer_size = len(buffer)

        return self.__sock.recvfrom_into(buffer, buffer_size)

    def close(self):
        self.__sock.close()


def get_interface_index():
    known_names = ["enp4s0", "enp2s0"]
    for idx, name in enumerate(known_names):
        try:
            index = socket.if_nametoindex(name)
            logging.debug("socket %s chosen", name)
            return index
        except OSError as err:
            # If no more left to try, die
            if idx == (len(known_names) - 1):
                raise err


def create_listening_socket(port: int, multicast_address: str) -> socket.socket:
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

    # Get interface to use
    interface_index = get_interface_index()

    # Bind to the one interface on the given port
    logging.debug("Binding listening socket to addr %s port %d, interface_idx %d", multicast_address, port,
                  interface_index)
    sock.bind((multicast_address, port, 0, interface_index))

    # Construct message for joining multicast group
    multicast_request = struct.pack("16s15s".encode('utf-8'), socket.inet_pton(socket.AF_INET6, multicast_address),
                                    (chr(0) * 16).encode('utf-8'))
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, multicast_request)

    return sock
