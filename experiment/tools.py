import csv
import errno
import fcntl
import logging
import os
import random
import struct
import time
from typing import List

from ilnpsocket.underlay.routing.ilnp import ILNPPacket, is_control_packet


class PacketEntry:
    def __init__(self, my_id, sent_at_time, packet_type, forwarded):
        """
        Record of sent or forwarded packet for analysis
        :param my_id id of node being recorded
        :type my_id int
        :param sent_at_time: epoch time packet was sent
        :type sent_at_time float
        :param packet_type: type of packet (control or data)
        :type packet_type str
        :param forwarded: was packet sent or forwarded by this node
        :type forwarded bool
        """
        self.node_id = my_id
        self.sent_at_time = sent_at_time
        self.packet_type = packet_type
        self.forwarded = forwarded


class Monitor:
    def __init__(self, max_sends, node_id, save_file_loc):
        self.max_sends = max_sends
        self.node_id = node_id
        self.entries = []
        self.save_file = save_file_loc

    def record_sent_packet(self, packet: ILNPPacket, forwarded=True):
        if is_control_packet(packet):
            self.entries.append(PacketEntry(self.node_id, time.time(), "control", forwarded))
        else:
            self.entries.append(PacketEntry(self.node_id, time.time(), "data", forwarded))

        self.max_sends = self.max_sends - 1

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
            if os.path.getsize(self.save_file) is 0:
                writer.writerow(["node_id", "sent_at_time", "packet_type", "forwarded"])

            for entry in self.entries:
                writer.writerow([entry.node_id, entry.sent_at_time, entry.packet_type, entry.forwarded])

            # Unlock
            logging.debug("Unlocking file")
            fcntl.flock(csv_file, fcntl.LOCK_UN)


class MockDataGenerator:

    def __init__(self, my_id: int):
        self.last_reading = SensorReading(my_id, 273.15, 50, 900, 2)

    def get_data(self):
        self.last_reading = SensorReading(
            self.last_reading.origin_id,
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
    struct_format = "!QfBHB"

    def __init__(self, origin_id, temperature_kelvin, humidity_percentage, pressure_hpa, uv_index):
        self.origin_id = origin_id
        self.temperature = temperature_kelvin
        self.humidity = humidity_percentage
        self.pressure = pressure_hpa
        self.uv_index = uv_index

    def __bytes__(self):
        return struct.pack(self.struct_format, self.origin_id, self.temperature, self.humidity, self.pressure, self.uv_index)

    @classmethod
    def from_bytes(cls, payload):
        (origin_id, temperature, humidity, pressure, uv_index) = struct.unpack(cls.struct_format, payload)
        return SensorReading(origin_id, temperature, humidity, pressure, uv_index)


class SinkLog:
    def __init__(self, sink_save_file):
        self.readings: List[SensorReading] = []
        self.sink_save_file = sink_save_file

    def record_reading(self, sensor_reading):
        self.readings.append(sensor_reading)

    def save(self):
        with open(self.sink_save_file, "a+") as csv_file:
            logging.debug("Attempting to gain sink log file lock")
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
            if os.path.getsize(self.sink_save_file) is 0:
                writer.writerow(["origin_id", "temperature", "humidity", "pressure", "uv_index"])

            writer = csv.writer(csv_file, delimiter=',')
            for sensor_reading in self.readings:
                writer.writerow([sensor_reading.origin_id, sensor_reading.temperature, sensor_reading.humidity,
                                 sensor_reading.pressure, sensor_reading.uv_index])

            # Unlock
            logging.debug("Unlocking file")
            fcntl.flock(csv_file, fcntl.LOCK_UN)
