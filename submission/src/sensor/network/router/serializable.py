import abc


class Serializable(abc.ABC):
    """
    Interface for classes that can be serialized to bytes
    """

    @abc.abstractmethod
    def __bytes__(self):
        pass

    @abc.abstractmethod
    def size_bytes(self):
        pass

    @classmethod
    @abc.abstractmethod
    def from_bytes(cls, raw_bytes):
        pass
