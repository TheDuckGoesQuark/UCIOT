import struct
from typing import Optional, Union

from sensor.network.router.groupmessages import GroupMessage
from sensor.network.router.serializable import Serializable

DATA_TYPE = 0
LOCAL_CONTROL_TYPE = 1
EXTERNAL_CONTROL_TYPE = 2


class TransportWrapper(Serializable):
    """
    Informs parser if data contains data or control packets.
    """

    FORMAT = "!BxH"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, payload_type: int, payload_len: int, payload: Optional[Union[bytes, bytearray, GroupMessage]]):
        self.payload_type = payload_type
        self.body_len = payload_len
        self.body: Optional[Union[bytes, bytearray, GroupMessage]] = payload

    def __bytes__(self):
        if self.body is not None:
            return struct.pack(self.FORMAT, self.payload_type, self.body_len) + bytes(self.body)
        else:
            return struct.pack(self.FORMAT, self.payload_type, self.body_len)

    def size_bytes(self):
        return self.SIZE + self.body_len

    def is_control_packet(self):
        return self.payload_type == LOCAL_CONTROL_TYPE

    @classmethod
    def from_bytes(cls, raw_bytes):
        payload_type, payload_len = struct.unpack(cls.FORMAT, raw_bytes[:cls.SIZE])

        if payload_len != 0:
            return TransportWrapper(payload_type, payload_len, raw_bytes[cls.SIZE:cls.SIZE + payload_len])
        else:
            return TransportWrapper(payload_type, payload_len, None)


def build_data_wrapper(data: bytes) -> TransportWrapper:
    return TransportWrapper(DATA_TYPE, len(data), data)


def build_local_control_wrapper(data: bytes) -> TransportWrapper:
    return TransportWrapper(LOCAL_CONTROL_TYPE, len(data), data)


def build_external_control_wrapper(data: bytes) -> TransportWrapper:
    return TransportWrapper(EXTERNAL_CONTROL_TYPE, len(data), data)
