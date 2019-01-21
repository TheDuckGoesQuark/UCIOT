import math
from math import floor, ceil


def parse_payload(offset_bits, payload_length, data):
    # Assume padding
    first_byte_index = ceil(offset_bits / 8)
    last_byte_index = first_byte_index + payload_length
    return data[first_byte_index:last_byte_index]


class Packet:
    def __init__(self, payload, src, dest, header=None):
        if header is None:
            self.header = PacketHeader(src[0], src[1], dest[0], dest[1], len(payload))
        else:
            self.header = header

        self.payload = payload

    def decrement_hop_limit(self):
        self.header.hop_limit -= 1

    def print_packet(self):
        self.header.print_header()
        print("Payload    : {}".format(self.payload))

    @classmethod
    def from_bytes(cls, packet_bytes):
        header = PacketHeader.parse_header(bytearray(packet_bytes))
        payload = parse_payload(header.length, header.payload_length, packet_bytes)
        return Packet(payload, None, None, header)

    def to_bytes(self):
        packet_bytes = self.header.to_bytes()
        packet_bytes.append(self.payload)
        return packet_bytes

    def get_payload(self):
        return self.payload


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
    min_length = version_size \
                 + traffic_class_size \
                 + flow_label_size \
                 + payload_length_size \
                 + next_header_size \
                 + hop_limit_size \
                 + address_field_size * 4

    def __init__(self, src_locator, src_identifier, dest_locator, dest_identifier, payload_length, next_header=0,
                 hop_limit=32, version=1, traffic_class=1, flow_label=1, length=min_length):
        self.version = version
        self.traffic_class = traffic_class
        self.flow_label = flow_label
        self.payload_length = payload_length
        self.next_header = next_header
        self.hop_limit = hop_limit
        self.src_locator = src_locator
        self.src_identifier = src_identifier
        self.dest_locator = dest_locator
        self.dest_identifier = dest_identifier
        self.length = length

    def to_bytes(self):
        nBytes = math.ceil(self.length / 8)
        arr = bytearray(nBytes)

    def print_header(self):
        print("ILNP Source: {}-{}".format(self.src_locator, self.src_identifier))
        print("ILNP Dest  : {}-{}".format(self.dest_locator, self.dest_identifier))
        print("Hop limit  : {}".format(self.hop_limit))

    @classmethod
    def parse_header(cls, byte_array):
        if len(byte_array) < (cls.min_length / 8):
            raise ValueError

        current_bit = 0
        version = get_int_from_bytes(current_bit, cls.version_size, byte_array)
        current_bit += cls.version_size
        traffic_class = get_int_from_bytes(current_bit, cls.traffic_class_size, byte_array)
        current_bit += cls.traffic_class_size
        flow_label = get_int_from_bytes(current_bit, cls.flow_label_size, byte_array)
        current_bit += cls.flow_label_size
        payload_length = get_int_from_bytes(current_bit, cls.payload_length_size, byte_array)
        current_bit += cls.payload_length_size
        next_header = get_int_from_bytes(current_bit, cls.next_header_size, byte_array)
        current_bit += cls.next_header_size
        hop_limit = get_int_from_bytes(current_bit, cls.hop_limit_size, byte_array)
        current_bit += cls.hop_limit_size
        src_locator = get_int_from_bytes(current_bit, cls.address_field_size, byte_array)
        current_bit += cls.address_field_size
        src_identifier = get_int_from_bytes(current_bit, cls.address_field_size, byte_array)
        current_bit += cls.address_field_size
        dest_locator = get_int_from_bytes(current_bit, cls.address_field_size, byte_array)
        current_bit += cls.address_field_size
        dest_identifier = get_int_from_bytes(current_bit, cls.address_field_size, byte_array)
        current_bit += cls.address_field_size

        # Set total header size
        length = current_bit

        return PacketHeader(version, traffic_class, flow_label, payload_length, next_header, hop_limit, src_locator,
                            src_identifier, dest_locator, dest_identifier, length)


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


def pack_in_byte(lower, upper):
    return lower | (upper << 4)


def unpack_byte(byte_val, lower=True):
    if lower:
        return byte_val & 15
    else:
        return (byte_val >> 4) & 15
