import logging
from typing import Tuple

from sensor.battery import Battery
from sensor.config import Configuration
from sensor.network.router.router import Router

logger = logging.getLogger(__name__)


class ILNPSocket:
    def __init__(self, config: Configuration, battery: Battery):
        """
        Creates an ILNPSocket instance with a routing thread for managing packets
        :param config: configuration to be used for routing
        :param battery: the sensors battery
        """
        self.battery = battery
        self.router_thread = Router(config, self.battery)
        self.router_thread.daemon = True
        self.router_thread.start()

    def close(self):
        """Close this thread and terminate the routing thread"""
        self.router_thread.join()

    def send(self, data, dest_id):
        """
        Sends data to the node with the given ID
        :param data: data to send
        :param dest_id: identifier of node to send to
        """
        if self.battery.remaining() <= 0:
            self.close()
            raise IOError("Battery low: socket closing")
        elif self.is_closed():
            raise IOError("Socket is closed.")
        else:
            self.router_thread.send(data, dest_id)

    def receive_from(self, timeout=None) -> Tuple[bytes, int]:
        """
        Receive bytes from socket
        :param timeout: if not None, socket will block until the given value in seconds before returning.
        :return: bytes received and source identifier of data
        """
        return self.router_thread.receive_from(timeout)

    def is_closed(self) -> bool:
        return not self.router_thread.running
