import csv
import errno
import fcntl
import logging
import random
import struct
import time


class Monitor:
    def __init__(self, number_of_sends, node_id, save_file_loc):
        self.number_of_sends = number_of_sends
        self.data_sent = 0
        self.control_packets_sent = 0
        self.node_id = node_id
        self.save_file = save_file_loc

    def record_sent_packet(self, packet):
        if packet.is_control_message():
            self.control_packets_sent = self.control_packets_sent + 1
        else:
            self.data_sent = self.data_sent + 1

        self.number_of_sends = self.number_of_sends + 1

    def save(self):
        with open(self.save_file, "a+") as csv_file:
            logging.debug("Attempting to gain log file lock")
            while True:
                # Loop to gain lock
                try:
                    fcntl.flock(csv_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    logging.debug("Lock obtained")
                    break
                except IOError as e:
                    if e.errno != errno.EAGAIN:
                        raise
                    else:
                        time.sleep(0.1)

            writer = csv.writer(csv_file, delimiter=',')
            writer.writerow([self.node_id, self.number_of_sends, self.data_sent, self.control_packets_sent])

            # Unlock
            logging.debug("Unlocking file")
            fcntl.flock(csv_file, fcntl.LOCK_UN)


class MockDataGenerator:

    def __init__(self):
        self.last_reading = SensorReading(273.15, 50, 900, 2)

    def get_data(self):
        self.last_reading = SensorReading(
            self.generate_temperature(),
            self.generate_humidity(),
            self.generate_presssure(),
            self.generate_uv_index()
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

    def generate_uv_index(self):
        val = self.last_reading.uv_index + random.randint(-1, 1)
        if val < 0:
            return 0
        elif val > 12:
            return 12
        else:
            return val


class SensorReading:
    """
    Sensor data that is serialized and sent as the payload of a data packet
    """

    struct_format = "!fBHB"

    def __init__(self, temperature_kelvin, humidity_percentage, pressure_hpa, uv_index):
        self.temperature = temperature_kelvin
        self.humidity = humidity_percentage
        self.pressure = pressure_hpa
        self.uv_index = uv_index

    def __bytes__(self):
        return struct.pack(self.struct_format, self.temperature, self.humidity, self.pressure, self.uv_index)

    @classmethod
    def from_bytes(cls, payload):
        (temperature, humidity, pressure, uv_index) = struct.unpack(cls.struct_format, payload)
        return SensorReading(temperature, humidity, payload, uv_index)
