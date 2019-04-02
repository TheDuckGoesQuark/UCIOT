import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class LinkTableEntry:
    def __init__(self, dest_id, next_hop_id, cost):
        self.dest_id = dest_id
        self.next_hop_id = next_hop_id
        self.cost = cost


class LinkTable:
    def __init__(self):
        self.link_entries: List[LinkTableEntry] = []

    def add_entry(self, dest_id, next_hop, cost):
        logger.info("Adding ID:{}, NH:{}, CT:{} to table".format(dest_id, next_hop, cost))
        self.link_entries.append(LinkTableEntry(dest_id, next_hop, cost))

