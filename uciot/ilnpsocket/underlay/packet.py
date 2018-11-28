from math import floor, ceil


def parse_payload(offset_bits, payload_length, data):
    # Assume padding
    first_byte_index = ceil(offset_bits / 8)
    last_byte_index = first_byte_index + payload_length
    return data[first_byte_index:last_byte_index]


class Packet:
    def __init__(self, arriving_interface, data):
        self.arriving_interface = arriving_interface
        self.header = PacketHeader(bytearray(data))
        self.payload = parse_payload(len(self.header), self.header.payload_length, data)

    def decrement_hop_limit(self):
        self.header.hop_limit -= 1

    def __len__(self):
        return len(self.header) + (len(self.payload) * 8)

    def print_packet(self):
        self.header.print_header()
        print("Payload    : {}".format(self.payload))


class PacketHeader:
    """
    The header of the ILNP packet.
    """

    """ 
    Size in bits and names of each header field in order of appearance
    """
    version_size = 4
    traffic_class_size = 4
    flow_label_size = 20
    payload_length_size = 16
    next_header_size = 8
    hop_limit_size = 8
    address_field_size = 64
    min_length = version_size + traffic_class_size + flow_label_size + payload_length_size + next_header_size + hop_limit_size + address_field_size * 4

    def __init__(self, byte_array):
        # TODO add extension headers
        if len(byte_array) < (self.min_length / 8):
            raise ValueError

        current_bit = 0
        self.version = get_int_from_bytes(current_bit, self.version_size, byte_array)
        current_bit += self.version_size
        self.traffic_class = get_int_from_bytes(current_bit, self.traffic_class_size, byte_array)
        current_bit += self.traffic_class_size
        self.flow_label = get_int_from_bytes(current_bit, self.flow_label_size, byte_array)
        current_bit += self.flow_label_size
        self.payload_length = get_int_from_bytes(current_bit, self.payload_length_size, byte_array)
        current_bit += self.payload_length_size
        self.next_header = get_int_from_bytes(current_bit, self.next_header_size, byte_array)
        current_bit += self.next_header_size
        self.hop_limit = get_int_from_bytes(current_bit, self.hop_limit_size, byte_array)
        current_bit += self.hop_limit_size
        self.src_locator = get_int_from_bytes(current_bit, self.address_field_size, byte_array)
        current_bit += self.address_field_size
        self.src_identifier = get_int_from_bytes(current_bit, self.address_field_size, byte_array)
        current_bit += self.address_field_size
        self.dest_locator = get_int_from_bytes(current_bit, self.address_field_size, byte_array)
        current_bit += self.address_field_size
        self.dest_identifier = get_int_from_bytes(current_bit, self.address_field_size, byte_array)
        current_bit += self.address_field_size

        # Set total header size
        self.length = current_bit

    def __len__(self):
        return self.length

    def print_header(self):
        print("ILNP Source: {}-{}".format(self.src_locator, self.src_identifier))
        print("ILNP Dest  : {}-{}".format(self.dest_locator, self.dest_identifier))
        print("Hop limit  : {}".format(self.hop_limit))


def get_int_from_bytes(offset_bits, number_of_bits, message_bytes):
    """
    Isolates the requested range of bits from a byte array and converts the result
    to an integer using big endian order
    :param offset_bits: index of bit to start from
    :param number_of_bits: range of bits to include
    :param message_bytes: byte array to isolate bits from
    :return: integer value of bit range
    """
    start_byte_index = floor(offset_bits / 8)
    last_byte_index = ceil(number_of_bits / 8) + start_byte_index
    relevant_bytes = message_bytes[start_byte_index:last_byte_index]

    if not starts_on_byte_boundary(offset_bits):
        mask = 2 ** 8 - 1
        bits_to_trim = offset_bits % 8
        relevant_bytes[0] = (relevant_bytes[0] << bits_to_trim) & mask

    if not ends_on_byte_boundary(offset_bits, number_of_bits):
        bits_to_keep = (offset_bits + number_of_bits) % 8
        last_byte_index = len(relevant_bytes) - 1
        relevant_bytes[last_byte_index] = relevant_bytes[last_byte_index] & ((1 << bits_to_keep) - 1)

    return int.from_bytes(relevant_bytes, byteorder='big', signed=False)


def starts_on_byte_boundary(offset_bits):
    return offset_bits % 8 == 0


def ends_on_byte_boundary(offset_bits, number_of_bits):
    return (number_of_bits + offset_bits) % 8 == 0
