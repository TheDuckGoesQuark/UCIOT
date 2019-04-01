from multiprocessing import Queue

from sensor.network.groupmessages import HelloGroup
from sensor.network.netinterface import NetworkInterface


class RouterControlPlane:
    def __init__(self, net_interface: NetworkInterface, control_packet_queue: Queue):
        self.net_interface = net_interface
        self.control_packet_queue = control_packet_queue

    def initialize_locator(self) -> int:
        """
        Broadcast node arrival and try to join/start group
        :returns this nodes locator
        """
        hello_group_msg = HelloGroup()
        pass

    def handle_packet(self, param):
        pass

