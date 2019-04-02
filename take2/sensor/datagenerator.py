import random
import struct

from sensor.network.router.serializable import Serializable


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

    def __bytes__(self):
        return struct.pack(self.FORMAT, self.origin_id, self.temperature, self.humidity, self.pressure,
                           self.luminosity)

    @classmethod
    def from_bytes(cls, payload):
        (origin_id, temperature, humidity, pressure, luminosity) = struct.unpack(cls.FORMAT, payload)
        return SensorReading(origin_id, temperature, humidity, pressure, luminosity)

    def size_bytes(self):
        return self.SIZE
