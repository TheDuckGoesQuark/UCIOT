import datetime
import threading
import select

from ilnpsocket.underlay.packet import Packet


class ListeningThread(threading.Thread):

    def __init__(self, listening_sockets, router, timeout=None):
        super(ListeningThread, self).__init__()
        self.__listening_sockets = listening_sockets
        self.__router = router
        self.__stopped = False
        self.__timeout = timeout

        # Stats for debugging
        self.__packets_dropped = 0
        self.__packets_accepted = 0

    def run(self):
        """Continuously checks for incoming packets on each listening socket and
        adds new packets to the message queue"""
        while not self.__stopped:
            ready_socks, _, _ = select.select(self.__listening_sockets, [], [], self.__timeout)
            for sock in ready_socks:
                self.read_sock(sock)

    def read_sock(self, listening_socket, buffer_size=1280):
        """
        Reads bytes from the given socket and attempts to parse a packet from it. On success, this packet will be added
        to the message queue alongside this listening threads' locator value so the arriving interface can be identified

        :param listening_socket: socket that has bytes ready to read
        :param buffer_size: maximum number of bytes to read from the buffer at once
        """
        data, addr = listening_socket.recvfrom(buffer_size)
        self.__packets_accepted += 1

        try:
            self.__router.add_to_route_queue((Packet.parse_packet(data), listening_socket.locator))
            print("INFO - Good packet received from {} at {}".format(addr, datetime.datetime.now()))
        except ValueError:
            self.__packets_dropped += 1
            print("WARN - Bad packet received.")
            print("WARN - Percentage dropped: {}".format((self.__packets_dropped / self.__packets_accepted) * 100))

    def stop(self):
        self.__stopped = True
