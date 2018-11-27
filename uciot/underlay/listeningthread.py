import threading
import select
from math import ceil

from uciot.underlay.packet import Packet


class ListeningThread(threading.Thread):

    def __init__(self, listening_sockets, message_queue):
        super(ListeningThread, self).__init__()
        self.__listening_sockets = listening_sockets
        self.__message_queue = message_queue
        self.__stopped = False

    def run(self, timeout=None):
        """Continuously checks for incoming packets on each listening socket and
        adds new packets to the message queue"""
        while not self.__stopped:
            ready_socks, _, _ = select.select(self.__listening_sockets, [], [], timeout)
            for sock in ready_socks:
                self.read_sock(sock)

    def read_sock(self, listening_socket, buffer_size=1280):
        data, addr = listening_socket.recvfrom(buffer_size)
        self.__message_queue.put(Packet(listening_socket.locator, data))

    def stop(self):
        self.__stopped = True


def get_payload_from_buffer(offset, payload_length, byte_array):
    first_byte_index = ceil(offset / 8)
    last_byte_index = first_byte_index + ceil(payload_length / 8)
    return byte_array[first_byte_index:last_byte_index]
