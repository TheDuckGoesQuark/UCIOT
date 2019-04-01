import struct

from sensor.network.serializable import Serializable

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


class HelloGroup(Serializable):
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


class HelloGroupAck(Serializable):
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


class OKGroup(Serializable):
    """
    Confirmation message sent by node to tell neighbours which group it joined

    Src Locator will be the joined group
    """
    FORMAT = "!B3x"
    SIZE = struct.calcsize(FORMAT)

    def __bytes__(self):
        return struct.pack(self.FORMAT, OK_GROUP_TYPE)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return OKGroup()


class OKGroupAck(Serializable):
    """
    Confirmation message sent to newly joined node informing it who is the current central node.
    """
    FORMAT = "!B3xQ"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, central_node_id):
        self.central_node_id = central_node_id

    def __bytes__(self):
        return struct.pack(self.FORMAT, OK_GROUP_ACK_TYPE, self.central_node_id)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return OKGroupAck(struct.unpack(cls.FORMAT, raw_bytes)[1])


class KeepAlive(Serializable):
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


class ChangeCentral(Serializable):
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


class ChangeCentralAck(Serializable):
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


class SensorDisconnect(Serializable):
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


class SensorDisconnectAck(Serializable):
    """
    Acknowledgement of a sensor disconnect sent to node that is disconnecting in case it has further processing to do
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
