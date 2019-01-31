import struct

from ilnpsocket.underlay.packet.icmp.locatorupdate import LocatorUpdateHeader
from ilnpsocket.underlay.packet.icmp.ndp import RouterSolicitation, RouterAdvertisement, NeighborSolicitation, NeighborAdvertisement, Redirect

icmp_type_to_class = {
    RouterSolicitation.TYPE: RouterSolicitation,
    RouterAdvertisement.TYPE: RouterAdvertisement,
    NeighborSolicitation.TYPE: NeighborSolicitation,
    NeighborAdvertisement.TYPE: NeighborAdvertisement,
    Redirect.TYPE: Redirect,
    LocatorUpdateHeader.TYPE: LocatorUpdateHeader
}


class ICMPMessage:
    NEXT_HEADER_VALUE = 58
    HEADER_DESCRIPTION_FORMAT = "!BBH"
    HEADER_SIZE = struct.calcsize(HEADER_DESCRIPTION_FORMAT)

    def __init__(self, message_type, code, checksum, body):
        self.message_type = message_type
        self.code = code
        self.checksum = checksum
        self.body = body

    def is_error(self):
        return self.message_type < 127

    def apply_function_to_router(self, router):
        self.body.apply_function_to_router(router)

    def __bytes__(self):
        header = struct.pack(self.HEADER_DESCRIPTION_FORMAT, self.message_type, self.code, self.checksum)
        if self.body is not None:
            header += bytes(self.body)

        return header

    @classmethod
    def parse_message(cls, message_bytes):
        vals = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, message_bytes[:cls.HEADER_SIZE])
        message_type = vals[0]

        if message_type in icmp_type_to_class:
            body = icmp_type_to_class[message_type].parse_message(message_bytes[cls.HEADER_SIZE:])
        else:
            raise ValueError("Unsupported or unknown icmp type value: {}".format(message_type))

        code = vals[1]
        checksum = vals[2]

        if calc_checksum(message_type, code, body.calc_checksum()) != checksum:
            raise ValueError("Calculated checksum doesn't match checksum in header.")

        return ICMPMessage(message_type, code, checksum, body)


def calc_checksum(message_type, code, body_checksum):
    """
    Checksum field is calculated from the one's complement of the sum of every 2 bytes combined to form one 16-bit
    number.in the icmp header.
    Checksum field is omitted from this calculation
    :param message_type: value of the type field
    :param code: value of the code field
    :param body_checksum: checksum of the icmp body
    :return: checksum of ICMP header
    """
    return -(body_checksum + ((message_type << 8) | code)) + 1
