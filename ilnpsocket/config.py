import os
from configparser import ConfigParser

LINK_LOCAL_MULTICAST = "FF02"


def parse_uid(opt_string_uid):
    if opt_string_uid:
        return int(opt_string_uid)
    else:
        return get_default_id()


def parse_group_ids(opt_list_uids):
    if opt_list_uids:
        return (uid for uid in opt_list_uids.split(','))
    else:
        return {hex(0)}


def build_ipv6_multicast_address(uid, group_id):
    """Takes the unique identifer and multicast group id (locator) and produces the ipv6 multicast address for this
    sub network """
    return LINK_LOCAL_MULTICAST + "::" + uid + ":" + group_id


def get_default_id():
    """Provides a unique identifier for the network by producing the hex value of the given users uid"""
    uid = os.getuid()
    return format(uid, 'x')


class Config:
    def __init__(self, config_file, section="DEFAULT"):
        if config_file is not None:
            cp = ConfigParser()
            cp.read(config_file)
            fields = cp[section]

            self.router_refresh_delay_secs = fields.getint('router_refresh_delay_secs', 60)
            self.uid = parse_uid(fields['unique_identifier'])
            self.group_ids = parse_group_ids(fields['group_ids'])
            self.port = fields.getint('port', 8080)
            self.hop_limit = fields.getint('hop_limit', 32)
            self.message = fields.get('message', "hello world")
            self.sleep = fields.getint('sleep', 3)
            self.locators_to_ipv6 = {group_id: build_ipv6_multicast_address(self.uid, group_id) for group_id in
                                     self.group_ids}
            self.my_id = fields.getint('my_id', 1)
            self.print_config()
        else:
            raise FileNotFoundError("No config file could be found at {}".format(config_file))

    def print_config(self):
        print("INFO - CONFIGURATION DESCRIPTION START")
        print("INFO - The following configuration was detected:")
        print("INFO - uid: {}".format(self.uid))
        print("INFO - port: {}".format(self.port))
        print("INFO - hop count: {}".format(self.hop_limit))
        print("INFO - message: {}".format(self.message))
        print("INFO - sleep: {}".format(self.sleep))
        print("INFO - locators:ipv6: {}".format(self.locators_to_ipv6))
        print("INFO - CONFIGURATION DESCRIPTION END")

