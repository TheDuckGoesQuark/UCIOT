from queue import Queue

from ilnpsocket.config import Config
from ilnpsocket.underlay.packet import Packet
from ilnpsocket.underlay.routing.router import Router


# TODO
# support mobility by allowing changes to locators to occur and sending updates when these changes do occur.
# see https://tools.ietf.org/html/rfc6740#section-2.1 page 30
# TODO
# routing table implementation
# TODO
# neighbour discovery

class ILNPSocket:
    """Abstracts UDP layer to leave only ILNP overlay"""

    def __init__(self, config_file):
        """
        Creates an io instance able to send and receive ILNP packets. A thread will be created for listening
        for incoming packets which will then populate the message queue, which can be polled using the receive method.
        """
        conf = Config(config_file)

        # packets for this node
        self.__received_packets = Queue()
        # router thread for forwarding and sending packets
        self.__router = Router(conf, self.__received_packets)
        self.__router.daemon = True
        self.__router.start()

        print("ILNP IO Initialised")

    def send(self, payload, destination):
        """
        Sends the given packet to the specified destination.
        :param payload: data to be sent
        :param destination: ILNP address as L:ID tuple of target
        """
        self.__router.add_to_route_queue(Packet(payload, self.__router.my_addresses[0], destination))

    def receive(self, timeout=None):
        """Polls for messages. A timeout can be supplied"""
        received_packet = self.__received_packets.get(block=True, timeout=timeout)

        if received_packet is None:
            return

        self.__received_packets.task_done()

        return received_packet.get_payload()
