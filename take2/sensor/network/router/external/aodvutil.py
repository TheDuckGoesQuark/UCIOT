import collections
from typing import List, Dict, Deque, Tuple, Optional, Set

from sensor.network.router.ilnp import ILNPPacket

NUM_REQUEST_IDS = 512


class RecentRequestBuffer:
    def __init__(self):
        self.recently_seen: Deque[Tuple[int, int]] = collections.deque(15 * [()])

    def __str__(self):
        return str([str(x) for x in self.recently_seen])

    def add(self, src_id, request_id):
        self.recently_seen.appendleft((src_id, request_id))

    def __contains__(self, src_id_request_id: Tuple[int, int]) -> bool:
        return src_id_request_id in self.recently_seen


class RequestRecord:
    def __init__(self, dest_loc: int, num_attempts: int):
        self.dest_loc: int = dest_loc
        self.num_attempts: int = num_attempts
        self.time_since_last_attempt: int = 0

    def increment_num_attempts(self):
        self.num_attempts = self.num_attempts + 1

    def increment_time_since_last_attempt(self):
        self.time_since_last_attempt = self.time_since_last_attempt + 1


class RequestRecords:
    def __init__(self):
        self.records: List[Optional[RequestRecord]] = [None] * NUM_REQUEST_IDS

    def __str__(self):
        return str([str(record) for record in self.records])

    def __contains__(self, request_id: int) -> bool:
        return self.records[request_id] is not None

    def add(self, request_id: int, dest_loc: int, num_attempts: int = 0):
        self.records[request_id] = RequestRecord(dest_loc, num_attempts)

    def pop(self, request_id: int):
        record = self.records[request_id]
        self.records[request_id] = None
        return record

    def pop_by_dest(self, dest_loc: int):
        requests_for_dest = [request_id for request_id, request in enumerate(self.records)
                             if request is not None and request.dest_loc == dest_loc]

        for request in requests_for_dest:
            self.pop(request)

    def age_records(self):
        for record in self.records:
            if record is not None:
                record.increment_time_since_last_attempt()

    def pop_records_older_than(self, age: int) -> List[RequestRecord]:
        old_records = []

        for request_id in range(len(self.records)):
            if request_id not in self:
                continue
            elif self.records[request_id].time_since_last_attempt > age:
                old_records.append(self.pop(request_id))

        return old_records


class DestinationQueues:
    """
    Maintains list of packets waiting for route to destination, and the request id of the RREQ that is fetching the
    route.
    """

    def __init__(self):
        self.dest_queues: Dict[int, List[ILNPPacket]] = {}

    def __contains__(self, dest_loc: int) -> bool:
        return dest_loc in self.dest_queues

    def __getitem__(self, dest_loc: int) -> List[ILNPPacket]:
        return self.dest_queues[dest_loc]

    def __str__(self):
        return str({dest: [str(packet) for packet in queue] for dest, queue in self.dest_queues.items()})

    def add_packet(self, packet: ILNPPacket):
        """
        Adds packet to existing queue for destination, or creates one and adds it if doesn't already exist
        :param packet: packet to add to queue
        """
        dest_loc = packet.dest.loc

        if dest_loc not in self:
            self.dest_queues[dest_loc] = [packet]
        else:
            self.dest_queues[dest_loc].append(packet)

    def remove_dest_queue(self, dest_loc: int):
        del self.dest_queues[dest_loc]

    def pop_dest_queue(self, dest_loc: int) -> List[ILNPPacket]:
        return self.dest_queues.pop(dest_loc)


