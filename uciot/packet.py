class Packet:
    """
    The payload of the UDP datagram used to imitate ILNP packets. 
    """

    def __init__(self, bytes):
        self.version = bytes
        self.src_address = bytes
        self.dest_address = bytes
        self.payload = bytes
        self.hop_limit = bytes

    def decrement_hop_limit(self):
        self.hop_limit -= 1

    def print_packet(self):
        print("ILNP Source: {}".format(self.src_address))
        print("ILNP Dest  : {}".format(self.dest_address))
        print("Payload    : {}".format(self.payload))
        print("Hop limit  : {}".format(self.hop_limit))

    @classmethod
    def parse_packet(cls, packet):
        """Parses object from packet json"""
        # packet = json.loads(packet)
        # return Packet(str(packet.src_address), str(packet.dest_address), str(packet.payload), str(packet.hop_limit))
        return packet