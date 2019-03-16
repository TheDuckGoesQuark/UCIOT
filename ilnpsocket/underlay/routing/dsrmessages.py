import struct
from functools import reduce
from typing import List, Union

from underlay.routing.serializable import Serializable

TYPE_VALUE_SIZE: int = struct.calcsize("!BB")


class DSRHeader(Serializable):
    FORMAT = "!BBH"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, next_header: int, is_flow_state: bool, payload_length: int):
        self.next_header: int = next_header
        self.is_flow_state: bool = is_flow_state
        self.payload_length: int = payload_length

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
    LOCATOR_SIZE: int = struct.calcsize(LOCATOR_FORMAT)

    def __init__(self, locators: List[int]):
        self.locators: List[int] = locators

    @classmethod
    def from_bytes(cls, packet_bytes: memoryview) -> 'RouteList':
        n_bytes_in_list = len(packet_bytes)
        if n_bytes_in_list == 0:
            return RouteList([])
        else:
            num_locs = n_bytes_in_list / cls.LOCATOR_SIZE
            locators = list(struct.unpack(cls.LOCATOR_FORMAT.format(num_locs), packet_bytes))
            return RouteList(locators)

    def __len__(self):
        return len(self.locators)

    def __bytes__(self) -> bytes:
        return struct.pack(self.LOCATOR_FORMAT.format(len(self)), *self.locators)

    def size_bytes(self):
        return len(self) * self.LOCATOR_SIZE


class RouteRequest(Serializable):
    TYPE = 1
    FORMAT = "!BBHHQ"
    FIXED_PART_SIZE = struct.calcsize(FORMAT)

    def __init__(self, data_len: int, request_id: int, target_loc: int, route_list: RouteList):
        self.data_len: int = data_len
        self.request_id: int = request_id
        self.target_loc: int = target_loc
        self.route_list: RouteList = route_list

    def __bytes__(self) -> bytes:
        return struct.pack(self.FORMAT, self.TYPE, self.data_len, self.request_id, self.target_loc) \
               + bytes(self.route_list)

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

    def size_bytes(self) -> int:
        return self.FIXED_PART_SIZE + self.route_list.size_bytes()

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview):
        opt_type, opt_len, last_hop_external = struct.unpack(cls.FORMAT, raw_bytes[:cls.FIXED_PART_SIZE])
        last_hop_external = last_hop_external >> 7
        route_list = RouteList.from_bytes(raw_bytes[cls.FIXED_PART_SIZE:opt_len + TYPE_VALUE_SIZE])
        return RouteReply(opt_len, last_hop_external, route_list)


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
    def __init__(self, header: DSRHeader, messages: List[Union[Serializable]]):
        self.header = header
        self.messages = messages

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview) -> 'DSRMessage':
        header = DSRHeader.from_bytes(raw_bytes)
        messages = cls.__parse_messages(raw_bytes[header.SIZE:], header.payload_length)
        return DSRMessage(header, messages)

    @classmethod
    def __parse_type(cls, raw_bytes: memoryview) -> int:
        return raw_bytes[:1]

    @classmethod
    def __parse_messages(cls, payload_bytes: memoryview, payload_length: int) -> List[Serializable]:
        messages = []
        offset = 0
        while offset < payload_length:
            type_val = cls.__parse_type(payload_bytes[offset:])
            message = MESSAGE_TYPES[type_val].from_bytes(payload_bytes[:offset])
            offset = offset + message.size_bytes()
            messages.append(message)

        return messages

    def __bytes__(self):
        return bytes(self.header) + reduce((lambda b, m: b + bytes(m)), self.messages, bytes())

    def size_bytes(self):
        return reduce((lambda s, m: s + m.size_bytes()), self.messages, self.header.SIZE)
