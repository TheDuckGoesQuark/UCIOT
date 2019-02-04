import threading
import select

from ilnpsocket.underlay.packet import Packet


class ListeningThread(threading.Thread):

    def __init__(self, listening_sockets, router, buffer_size_bytes, timeout=None):
        super(ListeningThread, self).__init__()
        self.__listening_sockets = listening_sockets
        self.__router = router
        self.__stopped = False
        self.__timeout = timeout

        if buffer_size_bytes < Packet.HEADER_SIZE:
            raise ValueError("Buffer size must be at least the size of an ILNPv6 packet header. "
                             "Given value: {}".format(buffer_size_bytes))

        self.__buffer = bytearray(buffer_size_bytes)
        self.buffer_view = memoryview(self.__buffer)

    def run(self):
        """Continuously checks for incoming packets on each listening socket and
        adds new packets to the message queue"""
        while not self.__stopped:
            ready_socks, _, _ = select.select(self.__listening_sockets, [], [], self.__timeout)
            for sock in ready_socks:
                self.read_sock(sock)

    def read_sock(self, listening_socket):
        """
        Reads bytes from the given socket and attempts to parse a packet from it. On success, this packet will be added
        to the message queue alongside this listening threads' locator value so the arriving interface can be identified

        :param listening_socket: socket that has bytes ready to read
        """
        packet_bytes = listening_socket.recvall(Packet.HEADER_SIZE)
        packet = Packet.parse_header(packet_bytes)

        if packet.payload_length is not 0:
            packet.payload = listening_socket.recvall(packet.payload_length)

        self.__router.add_to_route_queue(packet, listening_socket.locator)

    def stop(self):
        self.__stopped = True
