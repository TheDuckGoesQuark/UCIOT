import struct
from functools import reduce
from typing import List, Union

from underlay.routing.serializable import Serializable


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
        num_locs = len(packet_bytes) / cls.LOCATOR_SIZE
        locators = list(struct.unpack(cls.LOCATOR_FORMAT.format(num_locs), packet_bytes))
        return RouteList(locators)

    def __len__(self):
        return len(self.locators)

    def __bytes__(self) -> bytes:
        return struct.pack(self.LOCATOR_FORMAT.format(len(self)), *self.locators)

    def size_bytes(self):
        return len(self) * self.LOCATOR_SIZE


class RouteRequest(RouteList, Serializable):
    TYPE = 1


class RouteReply(RouteList):
    TYPE = 2


class RouteError:
    TYPE = 3


class PadOne:
    TYPE = 244


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
        return bytes(self.header) + (reduce((lambda b, m: b + bytes(m)), self.messages, bytes()))

    def size_bytes(self):
        return reduce((lambda s, m: s + m.size_bytes()), self.messages, self.header.SIZE)
