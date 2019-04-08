import struct

import logging
from typing import List, Dict

from sensor.network.router.serializable import Serializable

LOCATOR_SIZE: int = struct.calcsize("!Q")


class Hello(Serializable):
    """
    Sent by node on startup to either join group or determine if it should start its own group.

    Src Locator value in packet is irrelevant at this stage
    """
    FORMAT = "!I"
    SIZE = struct.calcsize(FORMAT)
    TYPE = 1

    def __init__(self, lambda_val: int):
        self.lambda_val = lambda_val

    def __bytes__(self):
        return struct.pack(self.FORMAT, self.lambda_val)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return Hello(struct.unpack(cls.FORMAT, raw_bytes[:cls.SIZE])[0])


class RouteList(Serializable):
    LOCATOR_FORMAT: str = "!{}Q"

    def __init__(self, locators: List[int]):
        self.locators: List[int] = locators

    @classmethod
    def from_bytes(cls, packet_bytes: memoryview) -> 'RouteList':
        n_bytes_in_list = len(packet_bytes)
        if n_bytes_in_list == 0:
            logging.debug("Empty route list read")
            return RouteList([])
        else:
            num_locs = n_bytes_in_list // LOCATOR_SIZE
            logging.debug("Expecting %d locators", num_locs)
            list_format = cls.LOCATOR_FORMAT.format(num_locs)
            logging.debug("Format string: %s", list_format)
            locators = list(struct.unpack(list_format, packet_bytes))
            return RouteList(locators)

    def __contains__(self, item: int) -> bool:
        return item in self.locators

    def __str__(self):
        return str(vars(self))

    def __len__(self):
        return len(self.locators)

    def __getitem__(self, index):
        return self.locators[index]

    def __bytes__(self) -> bytes:
        return struct.pack(self.LOCATOR_FORMAT.format(len(self)), *self.locators)

    def size_bytes(self):
        return len(self) * LOCATOR_SIZE

    def prepend(self, loc):
        self.locators.insert(0, loc)

    def append(self, loc):
        self.locators.append(loc)


class RouteRequest(Serializable):
    TYPE = 2
    FORMAT = "!HBxQ"
    FIXED_PART_SIZE = struct.calcsize(FORMAT)

    def __init__(self, request_id: int, locator_discovery: bool, target_loc: int, route_list: RouteList):
        """
        https://tools.ietf.org/html/rfc4728#section-6.2
        :param data_len: length of option in octets, excluding the option type and data len fields
        :param request_id: unique value generated by initiator
        :param target_loc: locator of node that is target of the route request
        :param route_list: list of hops excluding initiator locator
        """
        self.request_id: int = request_id
        self.locator_discovery: bool = locator_discovery
        self.target_loc: int = target_loc
        self.route_list: RouteList = route_list

    def __bytes__(self) -> bytes:
        return struct.pack(self.FORMAT, self.request_id, self.locator_discovery << 7, self.target_loc) \
               + bytes(self.route_list)

    def __str__(self):
        return str(vars(self))

    def size_bytes(self) -> int:
        return self.FIXED_PART_SIZE + self.route_list.size_bytes()

    @classmethod
    def from_bytes(cls, bytes_view: memoryview) -> 'RouteRequest':
        request_id, locator_discovery, target_loc = struct.unpack(cls.FORMAT, bytes_view[:cls.FIXED_PART_SIZE])

        list_bytes = bytes_view[cls.FIXED_PART_SIZE:]
        route_list = RouteList.from_bytes(list_bytes)
        return RouteRequest(request_id, locator_discovery, target_loc, route_list)


class RouteReply(Serializable):
    TYPE = 3

    def __init__(self, route_list: RouteList):
        self.route_list: RouteList = route_list

    def __bytes__(self) -> bytes:
        return bytes(self.route_list)

    def __str__(self):
        return str(self.route_list)

    def size_bytes(self) -> int:
        return self.route_list.size_bytes()

    @classmethod
    def from_bytes(cls, bytes_view: memoryview):
        route_list = RouteList.from_bytes(bytes_view)
        return RouteReply(route_list)


class RouteError(Serializable):
    """Informs nodes prior to a link break that a locator is no longer accessible from the origin locator"""
    TYPE = 4
    FORMAT = "!Q"
    FIXED_PART_SIZE = struct.calcsize(FORMAT)

    def __init__(self, lost_link_locator: int):
        self.lost_link_locator: int = lost_link_locator

    def __bytes__(self) -> bytes:
        return struct.pack(self.FORMAT, self.lost_link_locator)

    def size_bytes(self) -> int:
        return self.FIXED_PART_SIZE

    def __str__(self):
        return str(vars(self))

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview) -> 'RouteError':
        lost_link_locator = struct.unpack(cls.FORMAT, raw_bytes)[0]
        return RouteError(lost_link_locator)


class Link(Serializable):
    FORMAT = "!QQI"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, a, b, cost):
        self.a = a
        self.b = b
        self.cost = cost

    def __bytes__(self):
        return struct.pack(self.FORMAT, self.a, self.b, self.cost)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return Link(*struct.unpack(cls.FORMAT, raw_bytes))


def link_list_to_bytes(link_list: List[Link]) -> bytearray:
    byte_arr = bytearray(len(link_list) * Link.SIZE)
    offset = 0
    for link in link_list:
        byte_arr[offset:offset + Link.SIZE] = bytes(link)
        offset += Link.SIZE

    return byte_arr


def link_list_from_bytes(list_bytes: memoryview, n_links: int) -> List[Link]:
    offset = 0

    links = []
    for idx in range(n_links):
        link_bytes = list_bytes[offset:offset + Link.SIZE]
        link = Link.from_bytes(link_bytes)
        links.append(link)
        offset += Link.SIZE

    return links


class LSBMessage(Serializable):
    """For sharing link state databases"""

    TYPE = 5
    FORMAT = "!HBB"
    FIXED_PART_SIZE = struct.calcsize(FORMAT)

    def __init__(self, seq_number: int, internal_links: List[Link], external_links: List[Link]):
        self.seq_number = seq_number
        self.internal_links = internal_links
        self.external_links = external_links

    def __bytes__(self) -> bytes:
        internal_list_bytes = link_list_to_bytes(self.internal_links)
        external_list_bytes = link_list_to_bytes(self.external_links)

        return struct.pack(self.FORMAT, self.seq_number, len(self.internal_links), len(self.external_links)) \
               + internal_list_bytes + external_list_bytes

    def size_bytes(self) -> int:
        return self.FIXED_PART_SIZE

    def __str__(self):
        return str(vars(self))

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview) -> 'LSBMessage':
        seq_number, num_internal, num_external = struct.unpack(cls.FORMAT, raw_bytes[:cls.FIXED_PART_SIZE])

        # Parse internal links list
        offset = cls.FIXED_PART_SIZE
        end = offset + Link.SIZE * num_internal
        internal_links = link_list_from_bytes(raw_bytes[offset:end], num_internal)

        # Parse external links list
        offset = end
        end = offset + Link.SIZE * num_external
        external_links = link_list_from_bytes(raw_bytes[offset:end], num_external)

        return LSBMessage(seq_number, internal_links, external_links)


DATA_TYPE = 0

TYPE_TO_CLASS: Dict[int, Serializable] = {
    DATA_TYPE: None,
    Hello.TYPE: Hello,
    RouteRequest.TYPE: RouteRequest,
    RouteReply.TYPE: RouteReply,
    RouteError.TYPE: RouteError,
    LSBMessage.TYPE: LSBMessage,
}


class ControlHeader(Serializable):
    FORMAT = "!BB2x"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, payload_type: int, payload_length: int):
        self.payload_type: int = payload_type
        self.payload_length: int = payload_length

    def __str__(self):
        return str(vars(self))

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview) -> 'ControlHeader':
        payload_type, payload_length = struct.unpack(cls.FORMAT, raw_bytes[:cls.SIZE])
        return ControlHeader(payload_type, payload_length)

    def __bytes__(self) -> bytes:
        return struct.pack(self.FORMAT, self.payload_type, self.payload_length)

    def size_bytes(self):
        return self.SIZE


class ControlMessage(Serializable):
    def __init__(self, header: ControlHeader, body: Serializable):
        self.header = header
        self.body = body

    @classmethod
    def from_bytes(cls, raw_bytes: bytes) -> 'ControlMessage':
        view = memoryview(raw_bytes)
        header = ControlHeader.from_bytes(view[:ControlHeader.SIZE])

        body_bytes = view[header.SIZE:]
        message_class = TYPE_TO_CLASS[header.payload_type]

        if message_class is None:
            body = body_bytes
        else:
            body = message_class.from_bytes(body_bytes)

        return ControlMessage(header, body)

    def __bytes__(self):
        return bytes(self.header) + bytes(self.body)

    def size_bytes(self):
        return ControlHeader.SIZE + self.header.payload_length

    def is_control_message(self):
        return self.header.payload_type != DATA_TYPE


def build_data_message(data_bytes) -> ControlMessage:
    return ControlMessage(ControlHeader(DATA_TYPE, len(data_bytes)), data_bytes)