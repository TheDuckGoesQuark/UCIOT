from multiprocessing import Queue

from sensor.network.router.ilnp import ILNPPacket
from sensor.network.router.netinterface import NetworkInterface


class RouterDataPlane:
    def __init__(self, net_interface: NetworkInterface, data_packet_queue: Queue, for_me_queue: Queue, my_addr,
                 forwarding_table):
        self.net_interface = net_interface
        self.data_packet_queue = data_packet_queue
        self.for_me_queue = for_me_queue
        self.my_addr = self.my_addr
        self.forwarding_table = forwarding_table

    def handle_packet(self, packet: ILNPPacket):
        if packet.
        self.for_me_queue.put((packet.payload.body, packet.src.id))
