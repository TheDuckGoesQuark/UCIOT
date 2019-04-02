import struct
from abc import ABC
from typing import Union

from sensor.network.router.serializable import Serializable

# Joining
HELLO_GROUP_TYPE = 0
HELLO_GROUP_ACK_TYPE = 1

# Confirm Join
OK_GROUP_TYPE = 2
OK_GROUP_ACK_TYPE = 3

# Inform Neighbours
NEW_SENSOR_TYPE = 4
NEW_SENSOR_ACK_TYPE = 5

# Keep Alive
KEEPALIVE_TYPE = 6

# Update Central
CHANGE_CENTRAL_TYPE = 7
CHANGE_CENTRAL_ACK_TYPE = 8

# Handle Failure
SENSOR_DISCONNECT_TYPE = 9
SENSOR_DISCONNECT_ACK_TYPE = 10


class GroupMessage(Serializable, ABC):
    """
    Base class for all group messages.

    First byte signifies group message type and so can be used for further parsing
    """

    @classmethod
    def parse_type(cls, message_bytes: Union[bytearray, bytes]) -> int:
        return message_bytes[0]


class HelloGroup(GroupMessage):
    """
    Sent by node on startup to either join group or determine if it should start its own group.

    Src Locator value in packet is irrelevant at this stage
    """
    FORMAT = "!B3x"
    SIZE = struct.calcsize(FORMAT)

    def __bytes__(self):
        return struct.pack(self.FORMAT, HELLO_GROUP_TYPE)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return HelloGroup()


class HelloGroupAck(GroupMessage):
    """
    Sent by neighbours of new node after HelloGroup for it to determine which group to join based on lambda values.

    Receiving node determines available groups from src locator of packet
    """
    FORMAT = "!BxH"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, lamda_val):
        self.lambda_val = lamda_val

    def __bytes__(self):
        return struct.pack(self.FORMAT, HELLO_GROUP_ACK_TYPE, self.lambda_val)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return HelloGroupAck(struct.unpack(cls.FORMAT, raw_bytes)[1])


class OKGroup(GroupMessage):
    """
    Confirmation message sent by node to tell neighbours which group it joined,
    with it's calculated cost metric for the new neighbours to advertise

    Src Locator will be the joined group
    """
    FORMAT = "!BxH"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, cost):
        self.cost = cost

    def __bytes__(self):
        return struct.pack(self.FORMAT, OK_GROUP_TYPE, self.cost)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        type_val, cost = struct.unpack(cls.FORMAT, raw_bytes)
        return OKGroup(cost)


class Link(Serializable):
    """Record of two node IDs and the cost of the path between them"""
    FORMAT = "!QQH2x"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, node_a_id, node_b_id, cost):
        self.node_a_id = node_a_id
        self.node_b_id = node_b_id
        self.cost = cost

    def __eq__(self, other):
        """Two links are equal if they have the same nodes at either side"""
        return self.node_a_id == other.node_a_id and self.node_b_id == other.node_b_id \
               or self.node_a_id == other.node_b_id and self.node_b_id == other.node_a_id

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return Link(*struct.unpack(cls.FORMAT, raw_bytes[:cls.SIZE]))

    def __bytes__(self):
        return struct.pack(self.FORMAT, self.node_a_id, self.node_b_id, self.cost)


class OKGroupAck(GroupMessage):
    """
    Confirmation message sent to newly joined node informing it who is the current central node, and
    provides the full link database of the network
    """
    HEADER_FORMAT = "!BxHQ"
    SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self, num_entries, central_node_id, entry_list):
        self.num_entries = num_entries
        self.central_node_id = central_node_id
        self.entry_list = entry_list

    def __bytes__(self):
        entry_list_bytes = bytearray(Link.SIZE * self.num_entries)
        entry_list_bytes_view = memoryview(entry_list_bytes)
        for i in range(self.num_entries):
            offset = i * Link.SIZE
            entry_list_bytes_view[offset:offset + Link.SIZE] = bytes(self.entry_list[i])

        return struct.pack(self.HEADER_FORMAT, OK_GROUP_ACK_TYPE, self.num_entries,
                           self.central_node_id) + entry_list_bytes

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        type_val, num_entries, central_node_id = struct.unpack(cls.HEADER_FORMAT, raw_bytes[:cls.SIZE])
        entry_list = []
        # Use memory view due to frequent splitting
        bytes_view = memoryview(raw_bytes)
        for idx in range(num_entries):
            offset = idx * Link.SIZE
            entry_list.append(Link.from_bytes(bytes_view[offset:offset + Link.SIZE]))

        return OKGroupAck(num_entries, central_node_id, entry_list)


class NewSensor(GroupMessage):
    """
    Message informing all nodes in network of new node link
    """
    HEADER_FORMAT = "!B3x"
    SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self, link_entry: Link):
        self.link_entry = link_entry

    def __bytes__(self):
        return struct.pack(self.HEADER_FORMAT, NEW_SENSOR_TYPE) + bytes(self.link_entry)

    def size_bytes(self):
        return self.SIZE + Link.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        link = Link.from_bytes(raw_bytes[cls.SIZE:])
        return NewSensor(link)


class NewSensorAck(GroupMessage):
    """
    Sent to confirm reception of new sensor link
    """
    FORMAT = "!B3x"
    SIZE = struct.calcsize(FORMAT)

    def __bytes__(self):
        return struct.pack(self.FORMAT, NEW_SENSOR_ACK_TYPE)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return NewSensorAck()


class KeepAlive(GroupMessage):
    """
    Periodic message informing neighbours that this node is still live
    """
    FORMAT = "!B3x"
    SIZE = struct.calcsize(FORMAT)

    def __bytes__(self):
        return struct.pack(self.FORMAT, KEEPALIVE_TYPE)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return KeepAlive()


class ChangeCentral(GroupMessage):
    """
    Sent by central node to inform all other nodes who the new central node is.
    """
    FORMAT = "!B3xQ"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, central_node_id):
        self.central_node_id = central_node_id

    def __bytes__(self):
        return struct.pack(self.FORMAT, CHANGE_CENTRAL_TYPE, self.central_node_id)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return ChangeCentral(struct.unpack(cls.FORMAT, raw_bytes)[1])


class ChangeCentralAck(GroupMessage):
    """
    Acknowledgement of new central node change.
    """
    FORMAT = "!B3x"
    SIZE = struct.calcsize(FORMAT)

    def __bytes__(self):
        return struct.pack(self.FORMAT, CHANGE_CENTRAL_ACK_TYPE)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return ChangeCentralAck()


class SensorDisconnect(GroupMessage):
    """
    Sent by node about to leave network, or by neighbours of node that hasn't sent keepalive in a while

    Src id is id of node that has disconnected
    """
    FORMAT = "!B3x"
    SIZE = struct.calcsize(FORMAT)

    def __bytes__(self):
        return struct.pack(self.FORMAT, SENSOR_DISCONNECT_TYPE)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return SensorDisconnect()


class SensorDisconnectAck(GroupMessage):
    """
    Acknowledgement of a sensor disconnect sent to node that is
    disconnecting in case it has further processing to do once it knows the group is aware of its leaving
    """
    FORMAT = "!B3x"
    SIZE = struct.calcsize(FORMAT)

    def __bytes__(self):
        return struct.pack(self.FORMAT, SENSOR_DISCONNECT_ACK_TYPE)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return SensorDisconnectAck()
