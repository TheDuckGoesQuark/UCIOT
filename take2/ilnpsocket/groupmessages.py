from ilnpsocket.serializable import Serializable


class HelloGroup(Serializable):
    def __init__(self):


    def __bytes__(self):
        pass

    def size_bytes(self):
        pass


    @classmethod
    def from_bytes(cls, raw_bytes):
        pass