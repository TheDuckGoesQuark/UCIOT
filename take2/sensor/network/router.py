import threading

from sensor.config import Configuration
from sensor.network.netinterface import NetworkInterface


class Router(threading.Thread):
    def __init__(self, config:Configuration):
        self.net_interface: NetworkInterface = NetworkInterface(config)
        pass

    def close(self):
        self.join()

    def join(self):
        self.net_interface.close()
        self.join()

    def get_next_hop(self, dest_id) -> int:
        return None

    def send(self, data, dest_id):
        pass

    def receive_from(self, timeout):
        pass


