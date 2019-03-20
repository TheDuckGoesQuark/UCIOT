import logging
import os
from configparser import ConfigParser
from typing import Set, Dict

LINK_LOCAL_MULTICAST = "FF02"


def parse_group_ids(opt_list_uids: str) -> Set[int]:
    if opt_list_uids:
        return {int(uid) for uid in opt_list_uids.split(',')}
    else:
        return {0}


def build_ipv6_multicast_address(uid: str, group_id: int) -> str:
    """Takes the unique identifer and multicast group id (locator) and produces the ipv6 multicast address for this
    sub network """
    return LINK_LOCAL_MULTICAST + "::" + uid + ":" + format(group_id, "x")


def get_default_id() -> str:
    """Provides a unique identifier for the network by producing the hex value of the given users uid"""
    uid = os.getuid()
    return format(uid, 'x')


class Config:
    def __init__(self, config_file: str, section: str):
        if config_file is not None:
            cp = ConfigParser()
            cp.read(config_file)
            fields = cp[section]

            # Raw Socket Conf
            self.port: int = fields.getint('port', 8080)
            self.packet_buffer_size_bytes: int = fields.getint('packet_buffer_size_bytes', 512)
            self.loopback: bool = fields.getboolean("loopback", True)
            uid: str = fields.get('unique_identifier', None)
            if not uid:
                uid = get_default_id()

            # ILNP Conf
            self.my_id: int = fields.getint('my_id', 1)
            locators: Set[int] = parse_group_ids(fields.get('group_ids'))
            self.hop_limit: int = fields.getint('hop_limit', 32)
            self.locators_to_ipv6: Dict[int, str] = {locator: build_ipv6_multicast_address(uid, locator)
                                                     for locator in locators}

            # Router Conf
            self.router_refresh_delay_secs: int = fields.getint('router_refresh_delay_secs', 60)

            # Experiment config
            self.max_sends: int = fields.getint("max_sends", 100)
            self.save_file_loc: str = fields.get("save_file_loc", "test_log.csv")
            self.send_delay_secs: int = fields.getint("send_delay_secs", 10)
            self.sink_loc: int = fields.getint("sink_loc", 1)
            self.sink_id: int = fields.getint("sink_id", 1)
            self.sink_save_file: str = fields.get("sink_save_file", "sink_log.csv")

            self.is_sink = self.my_id is self.sink_id
        else:
            raise FileNotFoundError("No config file could be found at {}".format(config_file))

    def __str__(self):
        return str({
            'port': self.port,
            'packet_buffer_size_bytes': self.packet_buffer_size_bytes,
            'loopback?': self.loopback,
            'my_id': self.my_id,
            'hop_limit': self.hop_limit,
            'loc_ipv6': self.locators_to_ipv6,
            'router refresh delay sec': self.router_refresh_delay_secs,
            'max sends': self.max_sends,
            'save file loc': self.save_file_loc,
            'is sink?': self.is_sink,
            'send delay secs': self.send_delay_secs,
            'sink loc': self.sink_loc,
            'sink id': self.sink_id,
            'sink save file': self.sink_save_file
        })
