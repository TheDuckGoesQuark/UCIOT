from queue import Queue

from ilnpsocket.config import Config
from ilnpsocket.underlay.routing.router import Router

import logging
logging.basicConfig(level=logging.DEBUG)


class ILNPSocket:
    """Abstracts UDP layer to leave only ILNP overlay"""

    def __init__(self, config_file, config_section="DEFAULT"):
        """
        Creates an io instance able to send and receive ILNP packets. A thread will be created for listening
        for incoming packets which will then populate the message queue, which can be polled using the receive method.
        """
        conf = Config(config_file, config_section)
        # packets for this node
        self.__received_packets = Queue()
        # router thread for forwarding and sending packets
        self.__router = Router(conf, self.__received_packets)
        self.__router.daemon = True
        self.__router.start()

        logging.debug("ILNPSocket Initialised")

    def send(self, payload, destination):
        """
        Sends the given packet to the specified destination.
        :param payload: data to be sent as bytes object
        :param destination: ILNP address as L:ID tuple of target
        """

        if payload is None or type(payload) is not bytes:
            raise TypeError("Payload must be bytes object.")

        if destination is None or type(destination) is not tuple or len(destination) != 2:
            raise TypeError("Destination must be two element tuple of destination locator and identifier.")

        self.__router.add_to_route_queue(self.__router.construct_host_packet(payload, destination))

    def receive(self, timeout=None):
        """
        Polls for new messages as bytes
        :param timeout: optional timeout for when to stop listening for bytes
        :return: bytes of message
        """
        received_packet = self.__received_packets.get(block=True, timeout=timeout)

        if received_packet is None:
            return

        self.__received_packets.task_done()

        return received_packet.payload
