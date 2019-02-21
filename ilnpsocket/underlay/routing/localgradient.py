import logging
import struct

from underlay.icmp.icmpheader import ICMPHeader
from threading import Timer


def doNothing():
    pass


class GradientService:

    def __init__(self, router):
        """
        Initializes GradientService with forwarding table and the maximum gradient.

        Gradient service steps:
        Create gradient where sinks broadcast advertisemt, hop count is incremented each time and this is used
        to calculate gradient of each node along the way.

        Nodes capable of forwarding periodically send single hop packets to all locators at higher gradients

        :type router: Router
        :param router: router that can be used to forward any control messages
        """
        self.awaiting_route = {}
        self.router = router
        self.my_gradient = 2 ** 8 - 1
        self.forwarding_table = ForwardingTable()
        self.sink_addresses = {}

    def handle_message(self, packet, locator_interface):
        packet.payload = ICMPHeader.from_bytes(packet.payload)

        if packet.payload.message_type is SinkAdvertisment.TYPE:
            logging.debug("Received sink advertisement")
            self.handle_sink_advertisement(packet, locator_interface)

    def get_next_hop(self, dest_locator, dest_identifier):
        return self.forwarding_table.get_next_hop(dest_locator, dest_identifier)

    def recently_received_sink_adv(self, sink_addr):
        return self.sink_addresses[sink_addr].is_alive()

    def handle_sink_advertisement(self, packet, locator_interface):
        adv = SinkAdvertisment.from_bytes(packet.payload.body)

        sink_addr = (packet.src_locator, packet.src_identifier)

        if sink_addr not in self.sink_addresses:
            self.register_sink(packet.src_locator, packet.src_identifier, adv.hop_count, locator_interface)
        elif self.recently_received_sink_adv(sink_addr):
            pass
            # TODO
        else:
            pass
            # TODO

    def register_sink(self, locator, identifier, hop_count, locator_interface):
        self.sink_addresses[(locator, identifier)] = Timer(20, doNothing)
        self.forwarding_table.add_sink(locator, identifier, hop_count, locator_interface)


class SinkAdvertisment:
    TYPE = 200
    FORMAT = "!B"

    def __init__(self, hop_count=0):
        self.hop_count = hop_count

    def __bytes__(self):
        return struct.pack(self.FORMAT, self.hop_count)

    @classmethod
    def from_bytes(cls, packet_bytes):
        return SinkAdvertisment(struct.unpack(cls.FORMAT, packet_bytes)[0])


class ForwardingTable:
    """
    Forwarding table keeps track of the best next hops to reach the given
    """
    def __init__(self):


    def get_next_hop(self, locator, identifier):
        pass

    def add_sink(self, locator, identifier, hop_count, next_hop):
        pass

class ForwardingTableEntry:
    def __init__(self, locator, identifier, cost, next_hop):

