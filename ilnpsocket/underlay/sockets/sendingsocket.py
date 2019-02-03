import socket
import logging


class SendingSocket:
    def __init__(self, port_number, locator_to_ipv6, loopback):
        self.__port = port_number
        self.__sock = create_sending_socket(loopback)
        self.__locator_to_ipv6 = locator_to_ipv6

    def translate_locator_to_ipv6(self, locator):
        return self.__locator_to_ipv6[str(locator)]

    def sendTo(self, packet_bytes, dest):
        """
        Sends the bytes to the IPv6 destination address
        :param packet_bytes: byte array to send
        :param dest: locator to send packet bytes
        :return: number of bytes sent
        """
        ipv6_addr = self.translate_locator_to_ipv6(dest)
        logging.debug("Sending packet to locator:ipv6 address {}-{}".format(dest, ipv6_addr))
        return self.__sock.sendto(packet_bytes, (ipv6_addr, self.__port))

    def close(self):
        self.__sock.close()


def create_sending_socket(loopback):
    """
    Configures a socket for sending IPv6 UDP datagrams.
    Allows packets to sent back to this interface
    :return: configured socket object
    """
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, loopback)
    return sock
