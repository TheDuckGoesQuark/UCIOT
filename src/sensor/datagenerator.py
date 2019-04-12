import csv
import errno
import fcntl
import logging
import os
import random
import struct
import time
from typing import List

from sensor.network.router.serializable import Serializable

logger = logging.getLogger(__name__)


class MockDataGenerator:
    """
    Generates mock data using slight variance from initial values over time.
    """

    def __init__(self, my_id: int):
        self.last_reading = SensorReading(my_id, 273.15, 50, 900, 2)

    def get_data(self):
        self.last_reading = SensorReading(
            self.last_reading.origin_id,
            self.generate_temperature(),
            self.generate_humidity(),
            self.generate_presssure(),
            self.generate_luminosity()
        )
        return self.last_reading

    def generate_temperature(self):
        val = self.last_reading.temperature + (random.random() * 2 - 1)
        if val < 0:
            return 0
        else:
            return val

    def generate_humidity(self):
        val = self.last_reading.humidity + random.randint(-5, 5)
        if val < 0:
            return 0
        elif val > 100:
            return 100
        else:
            return val

    def generate_presssure(self):
        val = self.last_reading.pressure + random.randint(-5, 5)
        if val < 0:
            return 0
        else:
            return val

    def generate_luminosity(self):
        val = self.last_reading.luminosity + random.randint(-1, 1)
        if val < 0:
            return 0
        elif val > 12:
            return 12
        else:
            return val


class SensorReading(Serializable):
    FORMAT = "!QfBHB"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, origin_id, temperature_kelvin, humidity_percentage, pressure_hpa, luminosity):
        self.origin_id = origin_id
        self.temperature = temperature_kelvin
        self.humidity = humidity_percentage
        self.pressure = pressure_hpa
        self.luminosity = luminosity

    def __str__(self):
        return str(vars(self))

    def __bytes__(self):
        return struct.pack(self.FORMAT, self.origin_id, self.temperature, self.humidity, self.pressure,
                           self.luminosity)

    @classmethod
    def from_bytes(cls, payload):
        (origin_id, temperature, humidity, pressure, luminosity) = struct.unpack(cls.FORMAT, payload)
        return SensorReading(origin_id, temperature, humidity, pressure, luminosity)

    def size_bytes(self):
        return self.SIZE


class SinkLog:
    """Stores the data received by the sink node"""

    def __init__(self, sink_save_file: str):
        self.readings: List[SensorReading] = []
        self.sink_save_file = sink_save_file

    def record_reading(self, sensor_reading: SensorReading):
        self.readings.append(sensor_reading)

    def save(self):
        with open(self.sink_save_file, "a+") as csv_file:
            logger.debug("Attempting to gain sink log file lock")
            while True:
                # Loop to gain lock
                try:
                    fcntl.flock(csv_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    logger.debug("Lock obtained")
                    break
                except IOError as e:
                    if e.errno != errno.EAGAIN:
                        raise
                    else:
                        time.sleep(0.1)

            writer = csv.writer(csv_file, delimiter=',')
            if os.path.getsize(self.sink_save_file) is 0:
                writer.writerow(["origin_id", "temperature", "humidity", "pressure", "luminosity"])

            writer = csv.writer(csv_file, delimiter=',')
            for sensor_reading in self.readings:
                writer.writerow([sensor_reading.origin_id, sensor_reading.temperature, sensor_reading.humidity,
                                 sensor_reading.pressure, sensor_reading.luminosity])

            writer.writerow([time.time()])

            # Unlock
            logger.debug("Unlocking file")
            fcntl.flock(csv_file, fcntl.LOCK_UN)
