import logging
from queue import Queue

from ilnpsocket.underlay.routing.ilnp import ILNPPacket


class PacketQueue:
    def __init__(self):
        self.queue = Queue()

    def add(self, packet_to_route: ILNPPacket, arriving_locator: int = None):
        logging.debug("Adding packet with src %s dest %s arriving on %s to queue.", packet_to_route.src,
                      packet_to_route.dest, arriving_locator)
        self.queue.put((packet_to_route, arriving_locator))

    def get(self, block: bool, timeout: int = None) -> (ILNPPacket, int):
        logging.debug("Waiting %d secs before timeout: %s", timeout, block)
        return self.queue.get(block, timeout)

    def task_done(self):
        self.queue.task_done()

    def unfinished_tasks(self):
        return self.queue.unfinished_tasks


class ReceivedQueue:
    def __init__(self):
        self.queue = Queue()

    def add(self, payload):
        self.queue.put(payload)

    def get(self, block: bool = True, timeout: int = None) -> bytearray:
        return self.queue.get(block, timeout)

    def task_done(self):
        self.queue.task_done()
