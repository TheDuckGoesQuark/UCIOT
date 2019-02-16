import argparse
import time

from experiment.config import Config
from experiment.tools import Monitor, MockDataGenerator
from ilnpsocket.ilnpsocket import ILNPSocket

# init
parser = argparse.ArgumentParser()
parser.add_argument("config", type=str, help="Path to config file.")
parser.add_argument("section", type=str, help="Section in config file.")
args = parser.parse_args()
config_file = args.config
section = args.section

config = Config(config_file, section)
monitor = Monitor(config.max_sends, config.my_id, config.save_file_loc)

if __name__ == "__main__":
    sock = ILNPSocket(config, monitor)
    mock_generator = MockDataGenerator()

    if not config.is_sink:
        while monitor.max_sends > 0:
            time.sleep(config.send_delay_secs)
            sock.send(bytes(mock_generator.get_data()))
    else:
        while True:
            pass
else:
    sock = ILNPSocket(config_file, monitor)
