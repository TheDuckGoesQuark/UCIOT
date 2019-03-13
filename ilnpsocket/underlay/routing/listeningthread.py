import logging
import threading
import select
from typing import List

from ilnpsocket.underlay.routing.ippacket import IPPacket
from underlay.routing.router import Router
from underlay.sockets.listeningsocket import ListeningSocket


class ListeningThread(threading.Thread):

    def __init__(self, listening_sockets: List[ListeningSocket], router: Router, buffer_size_bytes: int,
                 timeout: int = None):
        super(ListeningThread, self).__init__()
        self.__listening_sockets: List[ListeningSocket] = listening_sockets
        self.__router: Router = router
        self.__stopped: bool = False
        self.__timeout: int = timeout
        self.__buffer_size: int = buffer_size_bytes

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
        packet = IPPacket.from_bytes(buffer)
        logging.debug("Packet from {}-{} to {} {} arrived on interface {}"
                      .format(packet.src_locator, packet.src_identifier,
                              packet.dest_locator, packet.dest_identifier, sock.locator))

        self.__router.add_to_route_queue(packet, sock.locator)

    def stop(self):
        self.__stopped = True
