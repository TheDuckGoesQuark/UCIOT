import logging
from argparse import ArgumentParser
from typing import Dict

from ilnpsocket.config import Configuration
from ilnpsocket.sensor import Sensor

CONFIG_FILE_PATH_OPT = "config_file_path"
CONFIG_HEADER_OPT = "configuration_header"

logging.basicConfig(level=logging.DEBUG, format='%(process)d - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_args() -> Dict:
    ap = ArgumentParser()

    ap.add_argument("-f", "--" + CONFIG_FILE_PATH_OPT, required=True,
                    help="Path to configuration file to be used by node.")
    ap.add_argument("-c", "--" + CONFIG_HEADER_OPT, required=True,
                    help="Which section of config file to use.")

    return vars(ap.parse_args())


if __name__ == "__main__":
    logger.info("Starting up.")
    args = get_args()
    config = Configuration(args[CONFIG_FILE_PATH_OPT], args[CONFIG_HEADER_OPT])

    logger.info("Configuration parsed: " + str(config))

    logger.info("Starting sensor.")
    try:
        sensor = Sensor(config)
        sensor.start()
    except KeyboardInterrupt as e:
        logger.info("Keyboard interrupt. Stopping sensor")
        sensor.stop()


