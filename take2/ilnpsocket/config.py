import os
from configparser import ConfigParser
from typing import List

LINK_LOCAL_MULTICAST = "FF02"


def get_default_id() -> str:
    """Provides a unique identifier for the network by producing the hex value of the given users uid"""
    uid = os.getuid()
    return format(uid, 'x')


def build_ipv6_multicast_address(uid: str, group_id: str) -> str:
    """Takes the unique identifer and multicast group id and produces the ipv6 multicast address for this
    sub network """
    return LINK_LOCAL_MULTICAST + "::" + uid + ":" + group_id


class Configuration:
    def __init__(self, file_path, section):
        cp = ConfigParser()
        cp.read(file_path)
        fields = cp[section]

        uid: str = fields.get('unique_identifier', None)
        if not uid:
            uid = get_default_id()

        # Raw Socket Conf
        self.port: int = fields.getint('port', 8080)
        self.packet_buffer_size_bytes: int = fields.getint('packet_buffer_size_bytes', 512)
        self.loopback: bool = fields.getboolean("loopback", True)
        self.mcast_groups: List[str] = \
            [build_ipv6_multicast_address(uid, group_id) for group_id in fields.get('mcast_groups').split(',')]

        # ILNP Conf
        self.my_id: int = fields.getint('my_id')
        self.my_locator: int = fields.getint('my_locator')

    def __str__(self) -> str:
        return str(vars(self))



