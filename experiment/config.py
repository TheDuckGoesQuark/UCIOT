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
        return {"0"}


def build_ipv6_multicast_address(uid, group_id):
    """Takes the unique identifer and multicast group id (locator) and produces the ipv6 multicast address for this
    sub network """
    return LINK_LOCAL_MULTICAST + "::" + uid + ":" + group_id


def get_default_id():
    """Provides a unique identifier for the network by producing the hex value of the given users uid"""
    uid = os.getuid()
    return format(uid, 'x')


class Config:
    def __init__(self, config_file, section):
        if config_file is not None:
            cp = ConfigParser()
            cp.read(config_file)
            fields = cp[section]

            self.router_refresh_delay_secs = fields.getint('router_refresh_delay_secs', 60)
            self.uid = parse_uid(fields.get('unique_identifier', None))
            self.group_ids = parse_group_ids(fields.get('group_ids'))
            self.port = fields.getint('port', 8080)
            self.hop_limit = fields.getint('hop_limit', 32)
            self.sleep = fields.getint('sleep', 3)
            self.locators_to_ipv6 = {group_id: build_ipv6_multicast_address(self.uid, group_id) for group_id in
                                     self.group_ids}
            self.my_id = fields.getint('my_id', 1)
            self.packet_buffer_size_bytes = fields.getint('packet_buffer_size_bytes', 512)
            self.loopback = fields.getboolean("loopback", True)
            self.print_config()

            # Experiment config
            self.max_sends = fields.getint("max_sends", 100)
            self.save_file_loc = fields.get("save_file_loc", "test_log.csv")
            self.is_sink = fields.getboolean("is_sink", False)
            self.send_delay_secs = fields.getint("send_delay_secs", 10)
            self.sink_loc = fields.getint("sink_loc", 1)
            self.sink_id = fields.getint("sink_id", 1)
            self.sink_save_file = fields.get("sink_save_file", "sink_log.csv")

        else:
            raise FileNotFoundError("No config file could be found at {}".format(config_file))

    def print_config(self):
        print("INFO - CONFIGURATION DESCRIPTION START")
        print("INFO - The following configuration was detected:")
        print("INFO - uid: {}".format(self.uid))
        print("INFO - port: {}".format(self.port))
        print("INFO - hop count: {}".format(self.hop_limit))
        print("INFO - sleep: {}".format(self.sleep))
        print("INFO - locators:ipv6: {}".format(self.locators_to_ipv6))
        print("INFO - packet buffer size: {} bytes".format(self.packet_buffer_size_bytes))
        print("INFO - my id: {}".format(self.my_id))
        print("INFO - CONFIGURATION DESCRIPTION END")
