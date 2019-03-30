import logging
import time

from ilnpsocket.config import Configuration
from ilnpsocket.netinterface import NetworkInterface

logger = logging.getLogger(name=__name__)


class Sensor:
    def __init__(self, config: Configuration):
        self.config: Configuration = config
        self.net_interface: NetworkInterface = NetworkInterface(config)
        self.net_interface.start()

    def joinOrStartGroup(self):
        pass

    def start(self):
        logger.info("Starting")
        self.joinOrStartGroup()
        while (True):
            self.net_interface.send(bytes("abc", "utf-8"))
            time.sleep(1)

    def stop(self):
        self.net_interface.close()
        self.net_interface.join()
