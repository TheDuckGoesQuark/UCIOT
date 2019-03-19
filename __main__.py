import argparse
import logging
import time
from queue import Empty
import os

from experiment.config import Config
from experiment.tools import Monitor, MockDataGenerator, SinkLog, SensorReading
from ilnpsocket.ilnpsocket import ILNPSocket
from ilnpsocket.underlay.routing.ilnp import ILNPAddress


def run_as_sink(config):
    sock = ILNPSocket(config)
    sink_log = SinkLog(config.sink_save_file)
    timed_out = False
    while not timed_out:
        try:
            reading = sock.receive(120)
            logging.debug("Received payload len %d", len(reading))
            sink_log.record_reading(SensorReading.from_bytes(reading))
        except Empty:
            timed_out = True

    sink_log.save()


killswitch_dir = os.path.expanduser("~/killswitch")


def killswitch():
    return os.path.isdir(killswitch_dir)


def run_as_node(config):
    monitor = Monitor(config.max_sends, config.my_id, config.save_file_loc)
    sock = ILNPSocket(config, monitor)
    mock_generator = MockDataGenerator()

    while monitor.max_sends > 0 and not killswitch() and not sock.is_closed():
        print("{} sends left".format(monitor.max_sends))
        time.sleep(config.send_delay_secs)
        sock.send(bytes(mock_generator.get_data()), ILNPAddress(config.sink_loc, config.sink_id))

    if sock.is_closed():
        logging.info("Router terminated. Checks logs for more details")

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
    logging.debug("Config: %s", configuration)

    # Run node
    if not configuration.is_sink:
        run_as_node(configuration)
    else:
        run_as_sink(configuration)
