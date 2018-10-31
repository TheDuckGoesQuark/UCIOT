import socket
import threading

def create_sending_socket():
    """
    Configures a socket for sending IPv6 UDP datagrams.
    Disallows packets being sent back to this socket
    :return: configured socket object
    """
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, False)
    return sock


class RoutingThread(threading.Thread):
    """
    Routing thread manages all entries in the packet queue, determine the course of action 
     for each packet. It also floods packets on startup to initialize the routing table.
    """

    def __init__(self, port, sendTo):
        super(RoutingThread, self).__init__()
        self.sock = create_sending_socket()
        self.port = port
        self.sendTo = sendTo

    def run(self):
        print "Beginning Routing Thread"

        packet = "1"
        while True:
            self.send(packet)

    def send(self, packet):
        # TODO dest address should use locator value merged with last bits in IPv6 multicast address
        self.sock.sendto(packet, (self.sendTo, self.port))
