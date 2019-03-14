import socket
import logging
from typing import Dict


class SendingSocket:
    def __init__(self, port_number: int, locator_to_ipv6: Dict[int, str], loopback: bool):
        self.__port: int = port_number
        self.__sock: socket.socket = create_sending_socket(loopback)
        self.__locator_to_ipv6: Dict[int, str] = locator_to_ipv6

    def translate_locator_to_ipv6(self, locator: int) -> str:
        return self.__locator_to_ipv6[locator]

    def sendTo(self, packet_bytes: bytes, next_hop_locator: int):
        """
        Sends the bytes to the IPv6 destination address
        :param packet_bytes: byte array to send
        :param next_hop_locator: locator to send packet bytes
        :return: number of bytes sent
        """
        try:
            ipv6_addr = self.translate_locator_to_ipv6(next_hop_locator)
            return self.__sock.sendto(packet_bytes, (ipv6_addr, self.__port))
        except KeyError:
            logging.error("Unable to send to locator {}".format(next_hop_locator))

    def getsockname(self):
        return self.__sock.getsockname()

    def close(self):
        self.__sock.close()


def create_sending_socket(loopback: bool) -> socket.socket:
    """
    Configures a socket for sending IPv6 UDP datagrams.
    Allows packets to sent back to this interface
    :return: configured socket object
    """
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, loopback)
    return sock
