import logging
import threading
import select

from ilnpsocket.underlay.routing.packet import Packet


class ListeningThread(threading.Thread):

    def __init__(self, listening_sockets, router, buffer_size_bytes, timeout=None):
        super(ListeningThread, self).__init__()
        self.__listening_sockets = listening_sockets
        self.__router = router
        self.__stopped = False
        self.__timeout = timeout
        self.__buffer = bytearray(buffer_size_bytes)
        self.buffer_view = memoryview(self.__buffer)

    def run(self):
        """Continuously checks for incoming packets on each listening socket and
        adds new packets to the message queue"""
        while not self.__stopped:
            ready_socks, _, _ = select.select(self.__listening_sockets, [], [], self.__timeout)
            for sock in ready_socks:
                self.read_sock(sock)

    def read_sock(self, sock):
        n_bytes_to_read, addr_info = sock.recvfrom_into(self.buffer_view)
        packet = Packet.parse_header(self.buffer_view)
        logging.debug("Packet from {}-{} to {} {} arrived on interface {}"
                      .format(packet.src_locator, packet.src_identifier,
                              packet.dest_locator, packet.dest_identifier, sock.locator))

        # Copy payload into bytearray from buffer
        if packet.payload_length is not 0:
            offset = Packet.HEADER_SIZE
            end = offset + packet.payload_length
            packet.payload = bytearray(self.buffer_view[offset:end])

        logging.debug(str(packet))

        self.__router.add_to_route_queue(packet, sock.locator)

    def stop(self):
        self.__stopped = True

