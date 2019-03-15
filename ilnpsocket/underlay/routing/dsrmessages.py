import struct
from typing import List, Union


class DSRHeader:
    FORMAT = "!BBH"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, next_header: int, is_flow_state: bool, payload_length: int):
        self.next_header: int = next_header
        self.is_flow_state: bool = is_flow_state
        self.payload_length: int = payload_length

    @classmethod
    def from_bytes(cls, raw_bytes: bytes) -> 'DSRHeader':
        """
        Creates an instance of DSRHeader from the given bytes object
        :param raw_bytes: bytes containing DSRHeader data
        :return: DSRHeader instance
        :rtype DSRHeader
        """
        next_header, flow_state, payload_length = struct.unpack(cls.FORMAT, raw_bytes[:cls.SIZE])
        flow_state = flow_state >> 7
        return DSRHeader(next_header, flow_state, payload_length)

    def __len__(self) -> int:
        return self.SIZE + self.payload_length

    def __bytes__(self) -> bytes:
        return struct.pack(self.FORMAT, self.next_header, self.is_flow_state << 7, self.payload_length) + self.options


class RouteList:
    HEADER_DESCRIPTION_FORMAT: str = "!BB2x"
    HEADER_DESCRIPTION_SIZE: int = struct.calcsize(HEADER_DESCRIPTION_FORMAT)
    LOCATOR_FORMAT: str = "!Q"
    LOCATOR_SIZE: int = struct.calcsize(LOCATOR_FORMAT)

    def __init__(self, num_of_locs: int, request_id: int, locators: List):
        """
        :param num_of_locs: number of locators appended to path so far. Can also be considered the hop count
        :param request_id: unique identifier used by the requester
        :param locators: list of locator hops in order of occurrence.
        """
        self.num_of_locs: int = num_of_locs
        self.request_id: int = request_id
        self.locators: List = locators

    @classmethod
    def from_bytes(cls, packet_bytes: bytes) -> 'RouteList':
        num_of_locs, request_id = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT,
                                                packet_bytes[:cls.HEADER_DESCRIPTION_SIZE])

        locator_list = []
        start = cls.HEADER_DESCRIPTION_SIZE
        for value in range(num_of_locs):
            end = start + cls.LOCATOR_SIZE
            locator_list.append(struct.unpack(cls.LOCATOR_FORMAT, packet_bytes[start:end])[0])
            start += cls.LOCATOR_SIZE

        return RouteList(num_of_locs, request_id, locator_list)

    def __bytes__(self) -> bytes:
        return struct.pack(self.HEADER_DESCRIPTION_FORMAT, self.num_of_locs, self.request_id) + self.locators_to_bytes()

    def locators_to_bytes(self) -> bytes:
        tuple_bytes = bytearray(self.num_of_locs * self.LOCATOR_SIZE)
        start = 0
        for i in range(self.num_of_locs):
            end = start + self.LOCATOR_SIZE
            tuple_bytes[start:end] = struct.pack(self.LOCATOR_FORMAT, self.locators[i])
            start = end

        return tuple_bytes

    def append_locator(self, locator: List) -> None:
        self.locators.append(locator)
        self.num_of_locs = self.num_of_locs + 1

    def append_locators(self, locators: List) -> None:
        self.locators.extend(locators)
        self.num_of_locs = self.num_of_locs + len(locators)

    def already_in_list(self, locator: List):
        return locator in self.locators

    def calc_checksum(self) -> int:
        return 0


class RouteReply(RouteList):
    TYPE = 1


class RouteRequest(RouteList):
    TYPE = 2


class RouteError:
    TYPE = 3


class DSRMessage:
    def __init__(self, header: DSRHeader, messages: List[Union[RouteRequest, RouteReply, RouteError]]):
        self.header = header
        self.messages = messages

    @classmethod
    def from_bytes(cls, raw_bytes: bytes) -> 'DSRMessage':
        header = DSRHeader.from_bytes(raw_bytes)
        messages = []
        offset = header.SIZE
        while (offset < header.payload_length):


        return DSRMessage(header, messages)
