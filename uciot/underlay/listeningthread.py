import threading
from math import ceil

from uciot.messagequeue import message_queue
from uciot.underlay.packet import PacketHeader, Packet


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
            to_read = 1024
            buf, ipv6_address = self.sock.recv(to_read)
            print("received message from node with ipv6 address {} "
                  .format(ipv6_address))

            # parse packet and add to queue
            try:
                byte_array = bytearray(buf)
                header = PacketHeader(byte_array)
                packet = Packet(header, get_payload_from_buffer(len(header), header.payload_length, byte_array))
                message_queue.put(packet)

            except ValueError:
                print("invalid packet received, discarded")


def get_payload_from_buffer(offset, payload_length, byte_array):
    first_byte_index = ceil(offset / 8)
    last_byte_index = first_byte_index + ceil(payload_length / 8)
    return byte_array[first_byte_index:last_byte_index]

# M17.2 look into multiprocessing
