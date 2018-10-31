import socket
import struct
import threading

from messagequeue import message_queue
from packet import Packet


def create_listening_socket(port, multicast_group):
    # Initialise socket for IPv6 datagrams
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Allows address to be reused
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Binds to all interfaces on the given port
    sock.bind(('', port))

    # Allow messages from this socket to loop back for development
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, True)

    # Construct message for joining multicast group
    mreq = struct.pack("16s15s", socket.inet_pton(socket.AF_INET6, multicast_group), chr(0) * 16)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)

    return sock


class ListeningThread(threading.Thread):
    """
    Listening thread awaits packets arriving through the socket, and adds them to the queue
    to be handled.
    """

    def __init__(self, port, multicast_group):
        """
        Initialises listening thread to join a multicast group and listen on a given socket.
        :param port: port number to use for multicast group socket 
        :param multicast_group: ipv6 address of multicast group
        """
        super(ListeningThread, self).__init__()
        self.sock = create_listening_socket(port, multicast_group)

    def run(self):
        print("Beginning listening")
        while True:
            # Create a buffer of size 1024 to receive messages
            message_bytes, ipv6_address = self.sock.recvfrom(1024)
            print("received message '{}' from node with ipv6 address {} "
                  .format(message_bytes.decode('utf-8'), ipv6_address))

            # Parse packet and add to queue
            try:
                packet = Packet(message_bytes)
                message_queue.put(packet)
            except ValueError:
                print("Invalid packet received, discarded")
