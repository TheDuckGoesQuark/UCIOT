import struct

from sensor.network.router.serializable import Serializable


class Hello(Serializable):
    """
    Sent by node on startup to either join group or determine if it should start its own group.

    Src Locator value in packet is irrelevant at this stage
    """
    FORMAT = "!B3xI"
    SIZE = struct.calcsize(FORMAT)
    TYPE = 6

    def __init__(self, lambda_val: int):
        self.lambda_val = lambda_val

    def __bytes__(self):
        return struct.pack(self.FORMAT, self.TYPE, self.lambda_val)

    def size_bytes(self):
        return self.SIZE

    @classmethod
    def from_bytes(cls, raw_bytes):
        return Hello(struct.unpack(cls.FORMAT, raw_bytes[:cls.SIZE])[1])
