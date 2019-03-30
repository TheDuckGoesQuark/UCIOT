import struct

from sensor.serializable import Serializable

DATA_TYPE = 0
CONTROL_TYPE = 1


class TransportWrapper(Serializable):
    FORMAT = "!BxH"
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, payload_type, payload_len, payload):
        self.payload_type = payload_type
        self.payload_len = payload_len
        self.payload = payload

    def __bytes__(self):
        if self.payload is not None:
            return struct.pack(self.FORMAT, self.payload_type, self.payload_len) + bytes(self.payload)
        else:
            return struct.pack(self.FORMAT, self.payload_type, self.payload_len)

    def size_bytes(self):
        return self.SIZE + self.payload_len

    @classmethod
    def from_bytes(cls, raw_bytes):
        payload_type, payload_len = struct.unpack(cls.FORMAT, raw_bytes[cls.SIZE:])

        if payload_len != 0:
            return TransportWrapper(payload_len, payload_type, raw_bytes[cls.SIZE:cls.SIZE + payload_len])
        else:
            return TransportWrapper(payload_len, payload_type, None)
