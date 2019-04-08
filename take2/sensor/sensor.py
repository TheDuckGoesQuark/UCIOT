import logging
from time import sleep

from sensor.battery import Battery
from sensor.config import Configuration
from sensor.datagenerator import MockDataGenerator, SensorReading
from sensor.network.ilnpsocket import ILNPSocket

logger = logging.getLogger(name=__name__)


class Sensor:
    def __init__(self, config: Configuration):
        self.socket = ILNPSocket(config, Battery(config.max_sends))
        self.interval = config.interval
        self.sink_id = config.sink_id
        self.is_sink = config.sink_id == config.my_id
        self.mock_gen = MockDataGenerator(config.my_id)
        self.running = True

    def take_reading(self):
        logger.info("Taking reading")
        return self.mock_gen.get_data()

    def start(self):
        logger.info("Starting")
        if self.is_sink:
            self.run_as_sink()
        else:
            self.run_as_sensor()

        self.stop()

    def run_as_sensor(self):
        while self.running and not self.socket.is_closed():
            logger.info("Sensor waiting for reading")
            sleep(self.interval)
            try:
                reading = self.take_reading()
                self.socket.send(bytes(reading), self.sink_id)
            except IOError as e:
                logger.warning("Terminating: " + str(e))

    def run_as_sink(self):
        while self.running and not self.socket.is_closed():
            logger.info("Sleeping between readings")
            sleep(self.interval)
            try:
                data_bytes, source_id = self.socket.receive_from(self.interval)
                sensor_reading = SensorReading.from_bytes(data_bytes)
                print("Received reading {} from {}".format(sensor_reading, source_id))
            except IOError as e:
                logger.warning("Terminating: " + e)
                self.running = False

    def stop(self):
        logger.info("Stopping underlying services.")
        self.running = False
        self.socket.close()
