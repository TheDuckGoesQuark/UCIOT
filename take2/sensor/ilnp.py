import struct
from typing import Set, Union

from sensor.config import Configuration
from sensor.netinterface import NetworkInterface
from sensor.serializable import Serializable

NO_NEXT_HEADER_VALUE = 59


class ILNPAddress:
    def __init__(self, loc: int, id: int):
        self.loc: int = loc
        self.id: int = id

    def __str__(self):
        return "{}:{}".format(self.loc, self.id)


class ILNPPacket(Serializable):
    MAX_PAYLOAD_SIZE: int = 65535
    ILNPv6_HEADER_FORMAT: str = "!IHBB4Q"
    HEADER_SIZE: int = struct.calcsize(ILNPv6_HEADER_FORMAT)

    def __init__(self, src: ILNPAddress, dest: ILNPAddress, next_header: int = 0,
                 hop_limit: int = 32, version: int = 6, traffic_class: int = 0,
                 flow_label: int = 0, payload_length: int = 0,
                 payload: Union[bytearray, bytes] = None):
        # First octet
        self.version: int = version
        self.traffic_class: int = traffic_class
        self.flow_label: int = flow_label

        # Second Octet
        self.payload_length: int = payload_length
        self.next_header: int = next_header
        self.hop_limit: int = hop_limit

        # Third Octet
        self.src: ILNPAddress = src

        # Fourth Octet
        self.dest: ILNPAddress = dest

        self.payload: bytearray = payload

    def __str__(self):
        barrier = ("-" * 21) + "\n"
        row_format = "{:>15}|{:<15}\n"
        field_dic = vars(self)
        view = "\n" + barrier
        for name, value in field_dic.items():
            view += row_format.format(name, str(value))

        view += barrier
        return view

    @classmethod
    def from_bytes(cls, packet_bytes: bytearray) -> 'ILNPPacket':
        values = struct.unpack(cls.ILNPv6_HEADER_FORMAT, packet_bytes[:cls.HEADER_SIZE])

        flow_label: int = values[0] & 1048575
        traffic_class: int = (values[0] >> 20 & 255)
        version: int = values[0] >> 28
        payload_length: int = values[1]
        next_header: int = values[2]
        hop_limit: int = values[3]
        src: ILNPAddress = ILNPAddress(values[4], values[5])
        dest: ILNPAddress = ILNPAddress(values[6], values[7])

        payload = packet_bytes[cls.HEADER_SIZE:cls.HEADER_SIZE + payload_length]

        return ILNPPacket(src, dest, next_header, hop_limit, version, traffic_class, flow_label, payload_length,
                          payload)

    def decrement_hop_limit(self) -> None:
        self.hop_limit -= 1

    def __bytes__(self) -> bytes:
        first_octet = self.flow_label | (self.traffic_class << 20) | (self.version << 28)
        header_bytes = struct.pack(self.ILNPv6_HEADER_FORMAT,
                                   first_octet,
                                   self.payload_length, self.next_header, self.hop_limit,
                                   self.src.loc, self.src.id, self.dest.loc, self.dest.id)

        return header_bytes + self.payload

    def size_bytes(self):
        return self.HEADER_SIZE + self.payload_length


class AddressHandler:
    def __init__(self, my_id: int, my_locators: Set[int]):
        self.my_id = my_id
        self.my_locators = my_locators

    def is_my_address(self, address: ILNPAddress) -> bool:
        return (address.loc in self.my_locators) and address.id == self.my_id

    def is_from_me(self, packet: ILNPPacket) -> bool:
        return self.is_my_address(packet.src)

    def is_for_me(self, packet: ILNPPacket) -> bool:
        return self.is_my_address(packet.dest)

    def is_my_locator(self, locator: int) -> bool:
        return locator in self.my_locators

    def get_random_src_locator(self) -> int:
        return next(x for x in self.my_locators)


class ILNPSocket:
    def __init__(self, config: Configuration):
        self.config: Configuration = config
        self.sends_left = config.max_sends
        self.net_interface: NetworkInterface = NetworkInterface(config)

        self.start_net_interface_daemon()

    def start_net_interface_daemon(self):
        self.net_interface.daemon = True
        self.net_interface.start()

    def close(self):
        self.net_interface.close()
        self.net_interface.join()

    def send(self, data):
        if self.sends_left <= 0:
            self.close()
            raise IOError("Battery low: socket closing")
        elif self.isClosed():
            raise IOError("Socket is closed.")
        else:
            self.net_interface.send(data)

    def isClosed(self):
        self.net_interface.is_alive()
