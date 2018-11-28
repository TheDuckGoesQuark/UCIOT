import datetime
import threading
import select

from uciot.ilnpsocket.underlay.packet import Packet


class ListeningThread(threading.Thread):

    def __init__(self, listening_sockets, message_queue, timeout=None):
        super(ListeningThread, self).__init__()
        self.__listening_sockets = listening_sockets
        self.__message_queue = message_queue
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
        data, addr = listening_socket.recvfrom(buffer_size)
        self.__packets_accepted += 1
        try:
            self.__message_queue.put(Packet(listening_socket.locator, data))
            print("INFO - Good packet received from {} at {}".format(addr, datetime.datetime.now()))
        except ValueError:
            self.__packets_dropped += 1
            print("WARN - Bad packet received.")
            print("WARN - Percentage dropped: {}".format((self.__packets_dropped / self.__packets_accepted) * 100))

    def stop(self):
        self.__stopped = True
