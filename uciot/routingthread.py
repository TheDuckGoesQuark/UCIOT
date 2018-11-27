import socket
import threading




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
        print("Beginning Routing Thread")

        packet = "00023412034013402134000213400Aasdasdf21400".encode()
        while True:
            self.send(packet)

    def send(self, packet):
        # TODO dest address should use locator value merged with last bits in IPv6 multicast address
        self.sock.sendto(packet, (self.sendTo, self.port))
