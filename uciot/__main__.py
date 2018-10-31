import struct
import threading
import socket
import json
from Queue import Queue
from Config import Config

"""
Stores packets waiting to be parsed, validated, and routed.
"""
packetQueue = Queue()

"""
Stores mapping of locator to interface 
"""


class Packet:
    """
    The payload of the UDP datagram used to imitate ILNP packets. 
    The src and dest addresses should have the format Locator:Identifer, 
    such that the locator identifies the sub-network the node belongs to,
    and the identifier is unique to that node.
    """

    def __init__(self, src_address, dest_address, payload, hop_limit):
        self.src_address = src_address
        self.dest_address = dest_address
        self.payload = payload
        self.hop_limit = hop_limit

    def decrement_hop_limit(self):
        self.hop_limit -= 1

    def print_packet(self):
        print("ILNP Source: {}".format(self.src_address))
        print("ILNP Dest  : {}".format(self.dest_address))
        print("Payload    : {}".format(self.payload))
        print("Hop limit  : {}".format(self.payload))

    @classmethod
    def parse_packet(cls, packet):
        """Parses object from packet json"""
        packet = json.load(packet)
        return Packet(packet.src_address, packet.dest_address, packet.payload, packet.hop_limit)


class ListeningThread(threading.Thread):
    """
    Listening thread awaits packets arriving through the socket, and adds them to the queue
    to be handled.
    """

    def __init__(self, config):
        super(ListeningThread, self).__init__()

        # Initialise socket for IPv6 datagrams
        self.sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

        # Allows address to be reused
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Binds to any interface on the given port
        self.sock.bind(('', config.port))

        # Allow messages from this socket to loop back for development
        self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, True)

        # Construct message for joining multicast group
        # TODO add support for multiple multicast groups (i.e networks) by joining multiple groups in config
        mreq = struct.pack("16s15s", socket.inet_pton(socket.AF_INET6, config.ipv6_multicast_addresses[0]), chr(0) * 16)
        self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)

    def run(self):
        print("Beginning listening")
        while True:
            # Create a buffer of size 1024 to receive messages
            packet, ipv6_address = self.sock.recvfrom(1024)
            print("received message '{}' from node with ipv6 address {} ".format(packet.decode('utf-8'), ipv6_address))
            packetQueue.put(packet)


class RoutingThread(threading.Thread):
    """
    Routing thread manages all entries to the packet queue, determine the course of action 
     for each packet.
    """

    def __init__(self, config):
        super(RoutingThread, self).__init__()

        # Configure socket for sending IPv6 Datagrams
        self.sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, True)
        self.config = config

    def run(self):
        print "Beginning Routing Thread"

        while True:
            packet = Packet.parse_packet(packetQueue.get())
            # TODO check locator/identifier here
            self.send(packet)

    def send(self, packet):
        # TODO dest address should use locator value merged with last bits in IPv6 multicast address
        self.sock.sendto(json.dumps(packet.__dict__), (self.config.ipv6_multicast_addresses[0], self.config.port))


if __name__ == '__main__':
    config = Config()
    listening = ListeningThread(config)
    routing = RoutingThread(config)
    listening.start()
    routing.start()
