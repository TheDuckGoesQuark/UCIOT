import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class ForwardingTableEntry:
    def __init__(self, next_hop_id):
        self.next_hop_id = next_hop_id


class ForwardingTable:
    """Stores a map of next hops for each destination id"""

    def __init__(self):
        self.next_hop_internal: Dict[int, ForwardingTableEntry] = {}
        self.next_hop_to_locator: Dict[int, ForwardingTableEntry] = {}

    def __str__(self):
        return str(vars(self))

    def get_next_hop(self, dest_id):
        if dest_id in self.next_hop_internal:
            return self.next_hop_internal[dest_id].next_hop_id
        else:
            return None

    def add_internal_entry(self, dest_id, next_hop):
        logger.info("Adding ID:{}, NH:{} to table".format(dest_id, next_hop))
        self.next_hop_internal[dest_id] = ForwardingTableEntry(next_hop)

    def add_external_entry(self, dest_loc, next_hop):
        logger.info("Adding LOC:{}, NH:{} to table".format(dest_loc, next_hop))
        self.next_hop_to_locator[dest_loc] = ForwardingTableEntry(next_hop)

