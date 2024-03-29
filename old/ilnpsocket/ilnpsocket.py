from experiment.config import Config
from experiment.tools import Monitor
from ilnpsocket.underlay.routing.ilnpnode import ILNPNode

import logging

from ilnpsocket.underlay.routing.queues import ReceivedQueue
from ilnpsocket.underlay.routing.ilnp import ILNPAddress

logging.basicConfig(level=logging.DEBUG, format='%(process)d - %(name)s - %(levelname)s - %(message)s')


class ILNPSocket:
    def __init__(self, conf: Config, monitor: Monitor = None):
        """
        Creates an io instance able to send and receive ILNP packets. A thread will be created for listening
        for incoming packets which will then populate the message queue, which can be polled using the receive method.
        """
        logging.debug("Beginning setup")
        self.__received_packets: ReceivedQueue = ReceivedQueue()
        self.__node: ILNPNode = ILNPNode(conf, self.__received_packets, monitor)

        logging.debug("Starting node thread")
        self.__node.daemon = True
        self.__node.start()

        logging.debug("ILNPSocket Initialised")

    def is_closed(self) -> bool:
        return not self.__node.isAlive()

    def close(self):
        logging.debug("Closing socket")
        self.__node.stop()

    def send(self, payload: bytes, destination: ILNPAddress):
        """
        Sends the given packet to the specified destination.
        :param payload: data to be sent as bytes object
        :param destination: ILNP address of target
        """
        logging.debug("Sending '%s' to %s", payload, destination)
        self.__node.send_from_host(payload, destination)

    def receive(self, timeout=None):
        """
        Polls for new messages as bytes
        :param timeout: optional timeout for when to stop listening for bytes
        :return: bytes of message
        """
        payload = self.__received_packets.get(block=True, timeout=timeout)
        logging.debug("Received '%s'", payload)
        self.__received_packets.task_done()
        return payload
