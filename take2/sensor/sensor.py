import logging
import os
from time import sleep

from sensor import packetmonitor
from sensor.battery import Battery
from sensor.config import Configuration
from sensor.datagenerator import MockDataGenerator, SensorReading, SinkLog
from sensor.network.ilnpsocket import ILNPSocket
from sensor.packetmonitor import Monitor

logger = logging.getLogger(name=__name__)

killswitch_dir = os.path.expanduser("~/killswitch")


def killswitch_engaged():
    return os.path.isdir(killswitch_dir)


class Sensor:
    def __init__(self, config: Configuration):
        self.monitor = Monitor(config.my_id, config.results_file)
        self.socket = ILNPSocket(config, Battery(config.max_sends), self.monitor)
        self.interval = config.interval
        self.sink_id = config.sink_id
        self.sink_file = config.sink_log_file
        self.is_sink = config.sink_id == config.my_id
        self.mock_gen = MockDataGenerator(config.my_id)

    def take_reading(self):
        return self.mock_gen.get_data()

    def start(self):
        logger.info("Starting")
        if self.is_sink:
            self.run_as_sink()
        else:
            self.run_as_sensor()

        self.stop()

    def run_as_sensor(self):
        logger.info("Giving network a chance to initialize")
        sleep(5)
        while self.monitor.running and not self.socket.is_closed() and not killswitch_engaged():
            sleep(self.interval)
            try:
                reading = self.take_reading()
                self.socket.send(bytes(reading), self.sink_id)
            except Exception as e:
                logger.warning("Terminating: " + str(e))
                self.monitor.running = False

        self.monitor.save()

    def run_as_sink(self):
        sink_log = SinkLog(self.sink_file)
        while self.monitor.running and not self.socket.is_closed() and not killswitch_engaged():
            sleep(self.interval)
            try:
                data_bytes, source_id = self.socket.receive_from(self.interval)
                if data_bytes is not None:
                    sensor_reading = SensorReading.from_bytes(data_bytes)
                    sink_log.record_reading(sensor_reading)
                    logger.info("Received reading {} from {}".format(sensor_reading, source_id))
            except Exception as e:
                logger.warning("Terminating: " + str(e))
                self.monitor.running = False

        sink_log.save()

    def stop(self):
        logger.info("Stopping underlying services.")
        self.monitor.running = False
        self.socket.close()
