from multiprocessing import Queue

from sensor.network.netinterface import NetworkInterface


class RouterDataPlane:
    def __init__(self, net_interface: NetworkInterface, data_packet_queue: Queue, for_me_queue: Queue):
        self.net_interface = net_interface
        self.data_packet_queue = data_packet_queue
        self.for_me_queue = for_me_queue

    def handle_packet(self, param):
        pass
