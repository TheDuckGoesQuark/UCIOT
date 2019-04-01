import logging
from time import sleep

from sensor.battery import Battery
from sensor.config import Configuration
from sensor.datagenerator import MockDataGenerator
from sensor.network.ilnpsocket import ILNPSocket

logger = logging.getLogger(name=__name__)


class Sensor:
    def __init__(self, config: Configuration):
        self.socket = ILNPSocket(config, Battery(config.max_sends))
        self.interval = config.interval
        self.sink_id = config.sink_id
        self.mock_gen = MockDataGenerator(config.my_id)
        self.running = True

    def take_reading(self):
        logger.info("Taking reading")
        return self.mock_gen.get_data()

    def start(self):
        logger.info("Starting")

        while self.running and not self.socket.is_closed():
            sleep(self.interval)
            try:
                reading = self.take_reading()
                self.socket.send(bytes(reading), self.sink_id)
            except IOError as e:
                logger.warn("Terminating: " + e)

        self.stop()

    def stop(self):
        logger.info("Stopping underlying services.")
        self.running = False
        self.socket.close()
