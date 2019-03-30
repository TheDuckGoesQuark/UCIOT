import logging

from ilnpsocket.config import Configuration
from ilnpsocket.netinterface import NetworkInterface

logger = logging.getLogger(name=__name__)


class Sensor:
    def __init__(self, config: Configuration):
        self.config: Configuration = config
        self.net_interface: NetworkInterface = NetworkInterface(config)
        self.net_interface.start()

    def start(self):
        logger.info("Starting")

    def stop(self):
        self.net_interface.close()
        self.net_interface.join()
