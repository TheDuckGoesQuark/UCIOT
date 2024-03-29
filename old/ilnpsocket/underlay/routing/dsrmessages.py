import logging
import struct
from functools import reduce
from typing import List

from ilnpsocket.underlay.routing.ilnp import NO_NEXT_HEADER_VALUE
from ilnpsocket.underlay.routing.serializable import Serializable

TYPE_VALUE_SIZE: int = struct.calcsize("!BB")
LOCATOR_SIZE: int = struct.calcsize("!Q")


def parse_type(raw_bytes: memoryview) -> int:
    return int(raw_bytes[0])


class DSRHeader(Serializable):
    FORMAT = "!BBH"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, next_header: int, is_flow_state: bool, payload_length: int):
        self.next_header: int = next_header
        self.is_flow_state: bool = is_flow_state
        self.payload_length: int = payload_length

    def __str__(self):
        return str(vars(self))

    @classmethod
    def build(cls, payload_length: int) -> 'DSRHeader':
        return DSRHeader(NO_NEXT_HEADER_VALUE, False, payload_length)

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview) -> 'DSRHeader':
        """
        Creates an instance of DSRHeader from the given bytes object
        :param raw_bytes: bytes containing DSRHeader data
        :return: DSRHeader instance
        :rtype DSRHeader
        """
        next_header, flow_state, payload_length = struct.unpack(cls.FORMAT, raw_bytes[:cls.SIZE])
        flow_state = flow_state >> 7
        return DSRHeader(next_header, flow_state, payload_length)

    def __bytes__(self) -> bytes:
        return struct.pack(self.FORMAT, self.next_header, self.is_flow_state << 7, self.payload_length)

    def size_bytes(self):
        return self.SIZE


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
    TYPE = 1
    FORMAT = "!BBHQ"
    FIXED_PART_SIZE = struct.calcsize(FORMAT)

    def __init__(self, data_len: int, request_id: int, target_loc: int, route_list: RouteList):
        """
        https://tools.ietf.org/html/rfc4728#section-6.2
        :param data_len: length of option in octets, excluding the option type and data len fields
        :param request_id: unique value generated by initiator
        :param target_loc: locator of node that is target of the route request
        :param route_list: list of hops excluding initiator locator
        """
        self.data_len: int = data_len
        self.request_id: int = request_id
        self.target_loc: int = target_loc
        self.route_list: RouteList = route_list

    def __bytes__(self) -> bytes:
        return struct.pack(self.FORMAT, self.TYPE, self.data_len, self.request_id, self.target_loc) \
               + bytes(self.route_list)

    def __str__(self):
        return str(vars(self))

    def refresh_data_len(self):
        self.data_len = (self.FIXED_PART_SIZE - TYPE_VALUE_SIZE) + self.route_list.size_bytes()

    @classmethod
    def build(cls, request_id: int, target_loc: int) -> 'RouteRequest':
        data_len = cls.FIXED_PART_SIZE - TYPE_VALUE_SIZE
        return RouteRequest(data_len, request_id, target_loc, RouteList([]))

    def size_bytes(self) -> int:
        return self.FIXED_PART_SIZE + self.route_list.size_bytes()

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview) -> 'RouteRequest':
        opt_type, data_len, request_id, target_loc = struct.unpack(cls.FORMAT, raw_bytes[:cls.FIXED_PART_SIZE])
        list_offset = cls.FIXED_PART_SIZE
        route_list = RouteList.from_bytes(raw_bytes[list_offset:data_len + TYPE_VALUE_SIZE])
        return RouteRequest(data_len, request_id, target_loc, route_list)


class RouteReply(Serializable):
    TYPE = 2
    FORMAT = "!BBB"
    FIXED_PART_SIZE = struct.calcsize(FORMAT)

    def __init__(self, data_len: int, last_hop_external: bool, route_list: RouteList):
        self.data_len: int = data_len
        self.last_hop_external: bool = last_hop_external
        self.route_list: RouteList = route_list

    def __bytes__(self) -> bytes:
        return struct.pack(self.FORMAT, self.TYPE, self.data_len, self.last_hop_external << 7) + bytes(self.route_list)

    def __str__(self):
        return str(vars(self))

    def size_bytes(self) -> int:
        return self.FIXED_PART_SIZE + self.route_list.size_bytes()

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview):
        opt_type, opt_len, last_hop_external = struct.unpack(cls.FORMAT, raw_bytes[:cls.FIXED_PART_SIZE])
        last_hop_external = last_hop_external >> 7
        route_list = RouteList.from_bytes(raw_bytes[cls.FIXED_PART_SIZE:opt_len + TYPE_VALUE_SIZE])
        return RouteReply(opt_len, last_hop_external, route_list)

    @classmethod
    def build(cls, rreq: RouteRequest, request_src_loc: int, request_dest_loc: int) -> 'RouteReply':
        """
        Builds route reply from path in rreq. Prepends src_loc to route reply list, and appends dest_loc if not already
        at end of list
        :param rreq: rreq being replied to
        :param request_src_loc: src locator of rreq
        :param request_dest_loc: dest locator of rreq
        :return: route reply
        """
        route_list = rreq.route_list
        route_list.prepend(request_src_loc)

        # Only append if the dest was another interface than the requester dest loc
        # i.e. (ID1)> (L1) <(ID2)> (L2)
        # ID1 sends to L2ID2, ID2 replies when receiving on L1, so needs to append L2 to path
        # ID1 sends to L1ID2, ID2 replies when receiving on L1, L1 already at end of path so shouldn't be added.
        if route_list[len(route_list) - 1] != request_dest_loc:
            route_list.append(request_dest_loc)

        data_len = (cls.FIXED_PART_SIZE - TYPE_VALUE_SIZE) + route_list.size_bytes()

        return RouteReply(data_len, False, route_list)

    def change_route_list(self, better_path):
        self.route_list = RouteList(better_path)
        self.data_len = (self.FIXED_PART_SIZE - TYPE_VALUE_SIZE) + self.route_list.size_bytes()


class RouteError(Serializable):
    TYPE = 3
    FORMAT = "!BBBBQQ"
    FIXED_PART_SIZE = struct.calcsize(FORMAT)
    ERROR_TYPES = {
        1: "NODE_UNREACHABLE",
        2: "FLOW_STATE_UNSUPPORTED",
        3: "OPTION_NOT_SUPPORTED"
    }

    def __init__(self, data_len: int, error_type: int, salvage: int, src_loc: int, dest_loc: int, type_specific_info):
        self.data_len: int = data_len
        self.error_type: int = error_type
        self.salvage: int = salvage
        self.src_loc: int = src_loc
        self.dest_loc: int = dest_loc
        # TODO
        self.type_specific_info = type_specific_info

    def __bytes__(self) -> bytes:
        return struct.pack(self.FORMAT, self.TYPE, self.data_len, self.error_type, self.salvage, self.src_loc,
                           self.dest_loc) + bytes(self.type_specific_info)

    def size_bytes(self) -> int:
        return self.FIXED_PART_SIZE + self.type_specific_info.size_bytes()

    def __str__(self):
        return str(vars(self))

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview) -> 'RouteError':
        opt_type, data_len, error_type, salvage, src_loc, dest_loc = struct.unpack(cls.FORMAT,
                                                                                   raw_bytes[:cls.FIXED_PART_SIZE])
        # TODO routeerrortypes
        return RouteError(data_len, error_type, salvage, src_loc, dest_loc, None)


class PadOne(Serializable):
    TYPE = 244
    FORMAT = "!x"
    SIZE = struct.calcsize(FORMAT)

    def __bytes__(self) -> bytes:
        return struct.pack(self.FORMAT)

    def __str__(self):
        return str(vars(self))

    def size_bytes(self) -> int:
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview) -> 'PadOne':
        struct.unpack(cls.FORMAT, raw_bytes[:cls.SIZE])
        return PadOne()


MESSAGE_TYPES = {
    RouteRequest.TYPE: RouteRequest,
    RouteReply.TYPE: RouteReply,
    RouteError.TYPE: RouteError,
    PadOne.TYPE: PadOne
}


class DSRMessage(Serializable):
    def __init__(self, header: DSRHeader, messages: List[Serializable]):
        self.header = header
        self.messages = messages

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview) -> 'DSRMessage':
        header = DSRHeader.from_bytes(raw_bytes)
        messages = cls.__parse_messages(raw_bytes[header.SIZE:], header.payload_length)
        return DSRMessage(header, messages)

    @classmethod
    def __parse_messages(cls, payload_bytes: memoryview, payload_length: int) -> List[Serializable]:
        messages = []
        offset = 0
        while offset < payload_length:
            type_val = parse_type(payload_bytes[offset:])
            logging.debug("Message type: %d", type_val)
            message = MESSAGE_TYPES[type_val].from_bytes(payload_bytes[offset:])
            logging.debug("Message received: %s", message)
            offset = offset + message.size_bytes()
            messages.append(message)

        return messages

    def __bytes__(self):
        return bytes(self.header) + reduce((lambda b, m: b + bytes(m)), self.messages, bytes())

    def size_bytes(self):
        return reduce((lambda s, m: s + m.size_bytes()), self.messages, self.header.SIZE)
