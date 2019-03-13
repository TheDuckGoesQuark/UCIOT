from experiment.config import Config
from experiment.tools import Monitor
from ilnpsocket.underlay.routing.router import Router

import logging

from underlay.routing.ilnpaddress import ILNPAddress
from underlay.routing.queues import ReceivedQueue

logging.basicConfig(level=logging.DEBUG)


class ILNPSocket:
    def __init__(self, conf: Config, monitor: Monitor = None):
        """
        Creates an io instance able to send and receive ILNP packets. A thread will be created for listening
        for incoming packets which will then populate the message queue, which can be polled using the receive method.
        """
        self.__received_packets: ReceivedQueue = ReceivedQueue()
        self.ilnp_address: ILNPAddress = ILNPAddress(conf.locators_to_ipv6.keys()[0], conf.my_id)
        self.__router: Router = Router(conf, self.__received_packets, monitor)

        self.__router.daemon = True
        self.__router.start()

        logging.debug("ILNPSocket Initialised")

    def is_closed(self) -> bool:
        return self.__router.isAlive()

    def close(self):
        logging.debug("Closing socket")
        self.__router.stop()

    def send(self, payload: bytes, destination: ILNPAddress):
        """
        Sends the given packet to the specified destination.
        :param payload: data to be sent as bytes object
        :param destination: ILNP address of target
        """
        self.__router.send_from_host(payload, destination)

    def receive(self, timeout=None):
        """
        Polls for new messages as bytes
        :param timeout: optional timeout for when to stop listening for bytes
        :return: bytes of message
        """
        payload = self.__received_packets.get(block=True, timeout=timeout)
        self.__received_packets.task_done()
        return payload
