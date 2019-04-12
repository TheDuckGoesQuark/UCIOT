import logging
from typing import Tuple, List

from sensor.battery import Battery
from sensor.config import Configuration
from sensor.network.router.router import Router
from sensor.packetmonitor import Monitor

logger = logging.getLogger(__name__)


class ILNPSocket:
    def __init__(self, config: Configuration, battery: Battery, monitor: Monitor):
        """
        Creates an ILNPSocket instance with a routing thread for managing packets
        :param config: configuration to be used for routing
        :param battery: the sensors battery
        """
        self.router_thread = Router(config, battery, monitor)
        self.router_thread.daemon = True
        self.router_thread.start()
        self.shutdown_buffer: List[Tuple[bytes, int]] = []

    def has_data(self):
        return self.router_thread.has_packets() or len(self.shutdown_buffer) > 0

    def close(self):
        """Close this thread and terminate the routing thread"""
        self.router_thread.join()
        self.router_thread.read_remaining_data_packets()
        logger.info("Reading any remaining data packets")
        while self.router_thread.has_packets():
            try:
                self.shutdown_buffer.append(self.receive_from())
                logger.info("Sock added to shutdown buffer")
            except Exception:
                logger.info("No more data packets remaining")
                break

    def send(self, data, dest_id):
        """
        Sends data to the node with the given ID
        :param data: data to send
        :param dest_id: identifier of node to send to
        """
        if self.is_closed():
            raise IOError("Socket is closed.")
        else:
            self.router_thread.send(data, dest_id)

    def receive_from(self, timeout=None) -> Tuple[bytes, int]:
        """
        Receive bytes from socket
        :param timeout: if not None, socket will block until the given value in seconds before returning.
        :return: bytes received and source identifier of data
        """
        if self.is_closed():
            if len(self.shutdown_buffer) == 0:
                raise IOError("Socket is closed.")
            else:
                return self.shutdown_buffer.pop()
        else:
            return self.router_thread.receive_from(blocking=True, timeout=timeout)

    def is_closed(self) -> bool:
        return not self.router_thread.is_alive()
