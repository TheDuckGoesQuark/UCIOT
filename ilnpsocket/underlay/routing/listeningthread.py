import logging
import threading
import select
from typing import List

from ilnpsocket.underlay.routing.ilnp import ILNPPacket
from ilnpsocket.underlay.routing.queues import PacketQueue
from ilnpsocket.underlay.sockets.listeningsocket import ListeningSocket


class ListeningThread(threading.Thread):

    def __init__(self, listening_sockets: List[ListeningSocket], inbound_queue: PacketQueue, buffer_size_bytes: int,
                 timeout: int = None):
        super(ListeningThread, self).__init__()
        self.__listening_sockets: List[ListeningSocket] = listening_sockets
        self.__stopped: bool = False
        self.__timeout: int = timeout
        self.__buffer_size: int = buffer_size_bytes
        self.__queue: PacketQueue = inbound_queue
        logging.debug("Listening thread initialized.")

    def run(self):
        """Continuously checks for incoming packets on each listening socket and
        adds new packets to the message queue"""
        while not self.__stopped:
            ready_socks, _, _ = select.select(self.__listening_sockets, [], [], self.__timeout)
            for sock in ready_socks:
                self.read_sock(sock)

    def read_sock(self, sock: ListeningSocket):
        buffer = bytearray(self.__buffer_size)
        n_bytes_to_read, addr_info = sock.recvfrom_into(buffer)
        packet = ILNPPacket.from_bytes(buffer)
        logging.debug("Packet parsed from socket")
        self.__queue.add(packet, sock.locator)

    def stop(self):
        self.__stopped = True
        for socket in self.__listening_sockets:
            socket.close()
