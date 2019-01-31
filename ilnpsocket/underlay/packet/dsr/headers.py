import struct


class RouteRequest:
    HEADER_DESCRIPTION_FORMAT = "!BB2x"
    HEADER_DESCRIPTION_SIZE = struct.calcsize(HEADER_DESCRIPTION_FORMAT)
    LOCATOR_FORMAT = "!Q"
    LOCATOR_SIZE = struct.calcsize(LOCATOR_FORMAT)
    TYPE = 255

    def __init__(self, num_of_locs, request_id, locators):
        """
        When a route is not known between two nodes, a route discovery request can be sent.
        Each node forwarding the request will append their own locator to the packet, and
        increment the num_of_locs counter. Once received at the destination, a route reply
        must be generated and sent to the requesting node.

        :param num_of_locs: number of locators appended to path so far. Can also be considered the hop count
        :param request_id: unique identifier used by the requester
        :param locators: list of locator hops in order of occurrence.
        """
        self.num_of_locs = num_of_locs
        self.request_id = request_id
        self.locators = locators

    @classmethod
    def parse_message(cls, packet_bytes):
        header_description = struct.unpack(cls.HEADER_DESCRIPTION_FORMAT, packet_bytes[:cls.HEADER_DESCRIPTION_SIZE])

        num_of_locs = header_description[0]
        request_id = header_description[1]

        list_format = cls.LOCATOR_FORMAT.format(num_of_locs)
        locator_list = []
        start = cls.HEADER_DESCRIPTION_SIZE
        for value in range(num_of_locs):
            end = start + cls.LOCATOR_SIZE
            locator_list.append(struct.unpack(cls.LOCATOR_FORMAT, packet_bytes[start:end]))
            start += cls.LOCATOR_SIZE

        return RouteRequest(num_of_locs, request_id, list_format)

    def __bytes__(self):
        return struct.pack(self.HEADER_DESCRIPTION_FORMAT, self.num_of_locs, self.request_id, self.locators_to_bytes())

    def locators_to_bytes(self):
        tuple_bytes = bytearray(self.num_of_locs * self.LOCATOR_SIZE)
        start = 0
        for i in range(self.num_of_locs):
            end = start + self.LOCATOR_SIZE
            tuple_bytes[start:end] = struct.pack(self.LOCATOR_FORMAT, self.locators[i])

        return tuple_bytes

