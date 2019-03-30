import logging

from sensor.config import Configuration
from sensor.datagenerator import MockDataGenerator
from sensor.ilnp import ILNPSocket

logger = logging.getLogger(name=__name__)


class Sensor:
    def __init__(self, config: Configuration):
        self.socket = ILNPSocket(config)
        self.sink_addr = config.sink_addr
        self.mock_gen = MockDataGenerator(config.my_id)
        self.running = True

    def take_reading(self):
        logger.info("Taking reading")
        return self.mock_gen.get_data()

    def start(self):
        logger.info("Starting")

        while self.running and not self.socket.isClosed():
            try:
                reading = self.take_reading()
                self.socket.send(bytes(reading))
            except IOError as e:
                logger.warn("Terminating: " + e)

        self.stop()

    def stop(self):
        logger.info("Stopping underlying services.")
        self.running = False
        self.socket.close()
