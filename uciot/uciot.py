from uciot.config import Config
from uciot.underlay.ilnpio import ILNPIO

config = Config()
ilnpio = ILNPIO(config.locators_to_ipv6, config.port)