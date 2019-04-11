import struct
import logging
from typing import List, Dict, Union, Tuple

from sensor.network.router.serializable import Serializable

logger = logging.getLogger(__name__)


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


class LocatorHopList(Serializable):
    """List of next hop locators"""
    FORMAT: str = "!Q"
    HOP_SIZE: int = struct.calcsize(FORMAT)

    def __init__(self, locators: List[int]):
        self.locator_hops: List[int] = locators

    @classmethod
    def from_bytes(cls, packet_bytes: memoryview) -> 'LocatorHopList':
        if len(packet_bytes) == 0:
            logger.debug("Empty route list read")
            return LocatorHopList([])

        locators = []
        for entry in struct.iter_unpack(cls.FORMAT, packet_bytes):
            locators.append(entry[0])

        return LocatorHopList(locators)

    def __contains__(self, item: int) -> bool:
        return item in self.locator_hops

    def __str__(self):
        return str(vars(self))

    def __len__(self):
        return len(self.locator_hops)

    def __getitem__(self, index):
        return self.locator_hops[index]

    def __bytes__(self) -> bytes:
        arr = bytearray(len(self) * self.HOP_SIZE)
        offset = 0
        for locator in self.locator_hops:
            arr[offset:offset + self.HOP_SIZE] = struct.pack(self.FORMAT, locator)
            offset += self.HOP_SIZE

        return bytes(arr)

    def size_bytes(self):
        return len(self) * self.HOP_SIZE

    def append(self, loc: int):
        self.locator_hops.append(loc)


class LocatorRouteRequest(Serializable):
    TYPE = 2
    FORMAT = "!HBx"
    FIXED_PART_SIZE = struct.calcsize(FORMAT)

    def __init__(self, request_id: int, allow_cached_replies: bool, locator_hop_list: LocatorHopList):
        """
        Request for a path from the ILNP src.id to the ILNP dest.id
        :param request_id: sequence number generated by sending node that can identify duplicate requests
        :param allow_cached_replies: if True, nodes that aren't the
        destination can reply with their known path to the destination
        :param locator_hop_list: locator hops that must be taken to reach the destination node
        """
        self.request_id: int = request_id
        self.allow_cached_replies: bool = allow_cached_replies
        self.locator_hop_list: LocatorHopList = locator_hop_list

    def __bytes__(self) -> bytes:
        return struct.pack(self.FORMAT, self.request_id, self.allow_cached_replies << 7) + bytes(self.locator_hop_list)

    def __str__(self):
        return str({name: str(x) for name, x in vars(self).items()})

    def size_bytes(self) -> int:
        return self.FIXED_PART_SIZE + self.locator_hop_list.size_bytes()

    @classmethod
    def from_bytes(cls, bytes_view: memoryview) -> 'LocatorRouteRequest':
        request_id, allow_cached_replies = struct.unpack(cls.FORMAT, bytes_view[:cls.FIXED_PART_SIZE])
        allow_cached_replies: bool = False if allow_cached_replies == 0 else True

        list_bytes = bytes_view[cls.FIXED_PART_SIZE:]
        route_list = LocatorHopList.from_bytes(list_bytes)
        return LocatorRouteRequest(request_id, allow_cached_replies, route_list)


class LocatorRouteReply(Serializable):
    TYPE = 3

    def __init__(self, route_list: LocatorHopList):
        self.route_list: LocatorHopList = route_list

    def __bytes__(self) -> bytes:
        return bytes(self.route_list)

    def __str__(self):
        return str(self.route_list)

    def size_bytes(self) -> int:
        return self.route_list.size_bytes()

    @classmethod
    def from_bytes(cls, bytes_view: memoryview):
        route_list = LocatorHopList.from_bytes(bytes_view)
        return LocatorRouteReply(route_list)


class LocatorLinkError(Serializable):
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
    def from_bytes(cls, raw_bytes: memoryview) -> 'LocatorLinkError':
        lost_link_locator = struct.unpack(cls.FORMAT, raw_bytes)[0]
        return LocatorLinkError(lost_link_locator)


class InternalLink(Serializable):
    FORMAT = "!QIQI"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, a, a_lambda, b, b_lambda):
        self.a = a
        self.a_lambda = a_lambda
        self.b = b
        self.b_lambda = b_lambda

    def __bytes__(self):
        return struct.pack(self.FORMAT, self.a, self.a_lambda, self.b, self.b_lambda)

    def __str__(self):
        return str(vars(self))

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return InternalLink(*struct.unpack(cls.FORMAT, raw_bytes))


class ExternalLink(Serializable):
    FORMAT = "!QQQI"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, border_node_id, locator, bridge_node_id, bridge_lambda):
        self.border_node_id = border_node_id
        self.locator = locator
        self.bridge_node_id = bridge_node_id
        self.bridge_lambda = bridge_lambda

    def __bytes__(self):
        return struct.pack(self.FORMAT, self.border_node_id, self.locator, self.bridge_node_id, self.bridge_lambda)

    def __str__(self):
        return str(vars(self))

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes) -> 'ExternalLink':
        return ExternalLink(*struct.unpack(cls.FORMAT, raw_bytes))


def link_list_to_bytes(link_list: List[Union[InternalLink, ExternalLink]], entry_class) -> bytearray:
    entry_size = entry_class.SIZE

    byte_arr = bytearray(len(link_list) * entry_size)
    offset = 0
    for link in link_list:
        byte_arr[offset:offset + entry_size] = bytes(link)
        offset += entry_size

    return byte_arr


def link_list_from_bytes(list_bytes: memoryview, n_links: int, entry_class) \
        -> List[Union[InternalLink, ExternalLink]]:
    offset = 0
    entry_size = entry_class.SIZE

    links = []
    for idx in range(n_links):
        link_bytes = list_bytes[offset:offset + entry_size]
        link = entry_class.from_bytes(link_bytes)
        links.append(link)
        offset += entry_size

    return links


class LSDBMessage(Serializable):
    """For sharing link state databases"""

    TYPE = 5
    FORMAT = "!HBB"
    FIXED_PART_SIZE = struct.calcsize(FORMAT)

    def __init__(self, seq_number: int, internal_links: List[InternalLink], external_links: List[ExternalLink]):
        self.seq_number = seq_number
        self.internal_links: List[InternalLink] = internal_links
        self.external_links: List[ExternalLink] = external_links

    def __bytes__(self) -> bytes:
        list_bytes: bytearray = link_list_to_bytes(self.internal_links, InternalLink)
        list_bytes.extend(link_list_to_bytes(self.external_links, ExternalLink))

        return struct.pack(self.FORMAT, self.seq_number, len(self.internal_links), len(self.external_links)) \
               + bytes(list_bytes)

    def size_bytes(self) -> int:
        return self.FIXED_PART_SIZE + \
               len(self.internal_links) * InternalLink.SIZE + \
               len(self.external_links) * ExternalLink.SIZE

    def __str__(self):
        string = ""
        string += "\nInternal"
        for link in self.internal_links:
            string += "\n{}".format(str(link))

        string += "\nExternal"
        for link in self.external_links:
            string += "\n{}".format(str(link))

        return string

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview) -> 'LSDBMessage':
        seq_number, num_internal, num_external = struct.unpack(cls.FORMAT, raw_bytes[:cls.FIXED_PART_SIZE])

        # Parse internal links list
        offset = cls.FIXED_PART_SIZE
        end = offset + InternalLink.SIZE * num_internal
        internal_links = link_list_from_bytes(raw_bytes[offset:end], num_internal, InternalLink)

        # Parse external links list
        offset = end
        end = offset + ExternalLink.SIZE * num_external
        external_links = link_list_from_bytes(raw_bytes[offset:end], num_external, ExternalLink)

        return LSDBMessage(seq_number, internal_links, external_links)


class ExpiredLinkList(Serializable):
    """For informing other nodes that a link has been lost"""

    TYPE = 6
    FORMAT = "!Q"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, lost_link_ids: List[int]):
        self.lost_link_ids = lost_link_ids

    def __len__(self):
        return len(self.lost_link_ids)

    def __bytes__(self) -> bytes:
        arr = bytearray(self.size_bytes())
        offset = 0
        for locator in self.lost_link_ids:
            arr[offset:offset + self.SIZE] = struct.pack(self.FORMAT, locator)
            offset += self.SIZE

        return bytes(arr)

    def size_bytes(self) -> int:
        return len(self) * self.SIZE

    def __str__(self):
        return str(vars(self))

    @classmethod
    def from_bytes(cls, raw_bytes: memoryview) -> 'ExpiredLinkList':
        entries = []

        for locator in struct.iter_unpack(cls.FORMAT, raw_bytes):
            entries.append(locator)

        return ExpiredLinkList(entries)


DATA_TYPE = 0

TYPE_TO_CLASS: Dict[int, Serializable] = {
    DATA_TYPE: None,
    Hello.TYPE: Hello,
    LocatorRouteRequest.TYPE: LocatorRouteRequest,
    LocatorRouteReply.TYPE: LocatorRouteReply,
    LocatorLinkError.TYPE: LocatorLinkError,
    LSDBMessage.TYPE: LSDBMessage,
    ExpiredLinkList.TYPE: ExpiredLinkList
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
            body = raw_bytes[header.SIZE:]
        else:
            body = message_class.from_bytes(body_bytes)

        return ControlMessage(header, body)

    def __str__(self):
        return str(self.header) + str(self.body)

    def __bytes__(self):
        return bytes(self.header) + bytes(self.body)

    def size_bytes(self):
        return ControlHeader.SIZE + self.header.payload_length

    def is_control_message(self):
        return self.header.payload_type != DATA_TYPE


def build_data_message(data_bytes) -> ControlMessage:
    return ControlMessage(ControlHeader(DATA_TYPE, len(data_bytes)), data_bytes)
