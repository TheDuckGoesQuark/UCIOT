import argparse
import logging
import time
from queue import Empty
import os

from experiment.config import Config
from experiment.tools import Monitor, MockDataGenerator, SinkLog, SensorReading
from ilnpsocket.ilnpsocket import ILNPSocket


def run_as_sink(config):
    sock = ILNPSocket(config)
    sink_log = SinkLog(config.sink_save_file)
    timed_out = False
    while timed_out:
        try:
            reading = sock.receive(120)
            sink_log.record_reading(SensorReading.from_bytes(reading))
        except Empty:
            timed_out = True

    sink_log.save()


def killswitch():
    return not os.path.isdir("~/killswitch")


def run_as_node(config):
    monitor = Monitor(config.max_sends, config.my_id, config.save_file_loc)
    sock = ILNPSocket(config, monitor)
    mock_generator = MockDataGenerator()

    while monitor.max_sends > 0 and killswitch():
        print("{}: {} sends left".format(config.my_id, monitor.max_sends))
        time.sleep(config.send_delay_secs)
        sock.send(bytes(mock_generator.get_data()), (config.sink_loc, config.sink_id))

    monitor.save()


if __name__ == "__main__":
    # Obtain configuration
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=str, help="Path to config file.")
    parser.add_argument("section", type=str, help="Section in config file.")
    args = parser.parse_args()
    config_file = args.config
    section = args.section
    logging.info("Running config file {} section {}".format(config_file, section))
    configuration = Config(config_file, section)

    # Run node
    if not configuration.is_sink:
        run_as_node(configuration)
    else:
        run_as_sink(configuration)
