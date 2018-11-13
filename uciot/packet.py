class Packet:
    def __init__(self, header, payload):
        self.header = header
        self.payload = payload

    def decrement_hop_limit(self):
        self.header.hop_limit -= 1

    def print_packet(self):
        print("Header     : {}".format(self.header))
        print("Payload    : {}".format(self.payload))


class PacketHeader:
    """
    The header of the ILNP packet.
    """

    def __init__(self, message_buffer):
        self.version = message_buffer
        self.traffic_class = message_buffer
        self.flow_label = message_buffer
        self.payload_length = message_buffer
        self.next_header = message_buffer
        self.hop_limit = message_buffer
        self.src_locator = message_buffer
        self.src_identifier = message_buffer
        self.dest_locator = message_buffer
        self.dest_identifier = message_buffer

    def print_packet(self):
        print("ILNP Source: {}-{}".format(self.src_locator, self.src_identifier))
        print("ILNP Dest  : {}-{}".format(self.dest_locator, self.dest_identifier))
        print("Hop limit  : {}".format(self.hop_limit))

    @classmethod
    def parse_header(cls, buff):

        return packet
