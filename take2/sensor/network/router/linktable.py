from typing import Dict


class LinkTableEntry:
    def __init__(self, dest_id, next_hop_id, cost):
        self.dest_id = dest_id
        self.next_hop_id = next_hop_id
        self.cost = cost


class LinkTable:
    def __init__(self):
        self.link_entries: Dict[int, LinkTableEntry] = []

    def add_entry(self, dest_id, next_hop, cost):
        self.link_entries[dest_id] = LinkTableEntry(dest_id, next_hop, cost)

