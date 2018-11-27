import socket


class SendingSocket:
    def __init__(self, port_number):
        self.__port = port_number
        self.__sock = create_sending_socket()

    def sendTo(self, packet_bytes, dest):
        """
        Sends the bytes to the IPv6 destination address
        :param packet_bytes: byte array to send
        :param dest: destination to send packet bytes
        :return: number of bytes sent
        """
        return self.__sock.sendto(packet_bytes, (dest, self.__port))

    def close(self):
        self.__sock.close()


def create_sending_socket():
    """
    Configures a socket for sending IPv6 UDP datagrams.
    Allows packets to sent back to this interface
    :return: configured socket object
    """
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, True)
    return sock
