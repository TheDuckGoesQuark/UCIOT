from queue import Queue

from uciot import Config
from ilnpsocket.underlay.packet import Packet
from ilnpsocket.underlay.routing import Router


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
        self.__router.run()

        print("ILNP IO Initialised")

    def send(self, payload, destination):
        """
        Sends the given packet to the specified destination.
        :param payload: data to be sent
        :param destination: ILNP address as ID:L tuple of target
        """
        self.__router.add_to_route_queue(Packet.build_packet(destination, payload))

    def receive(self, timeout=None):
        """Polls for messages. A timeout can be supplied"""
        received_packet = self.__received_packets.get(block=True, timeout=timeout)

        if received_packet is None:
            return

        self.__received_packets.task_done()

        return received_packet.get_payload()
