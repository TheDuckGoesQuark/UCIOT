import threading
import time
from typing import Dict, List


class ForwardingEntry:
    def __init__(self, next_hop_locator: int, cost: int):
        self.cost: int = cost
        self.next_hop_locator: int = next_hop_locator
        self.left_to_live: int = 10

    def should_be_replaced_by(self, route_cost: int) -> bool:
        """A lower cost, or  equally good but more recent route cost will be preferred."""
        if self.left_to_live == 0:
            return True
        else:
            return self.cost >= route_cost

    def reset_ltl(self):
        self.left_to_live = 10

    def decrement_ltl(self):
        self.left_to_live = self.left_to_live - 1


class NextHopList:
    def __init__(self):
        self.entries: List[ForwardingEntry] = []

    def __contains__(self, next_hop_loc: int) -> bool:
        return next_hop_loc in self.entries

    def __len__(self) -> int:
        return len(self.entries)

    def add_or_update(self, next_hop_loc: int, cost: int):
        if next_hop_loc in self:
            entry = self.get_entry_for_next_hop(next_hop_loc)
            entry.cost = cost
            entry.reset_ltl()
        else:
            self.entries.append(ForwardingEntry(next_hop_loc, cost))

    def get_entry_for_next_hop(self, next_hop_loc: int) -> ForwardingEntry:
        for entry in self.entries:
            if entry.next_hop_locator == next_hop_loc:
                return entry

        raise ValueError("No entry for %d" % next_hop_loc)

    def refresh_ltl_for_hop(self, next_hop_loc: int):
        self.get_entry_for_next_hop(next_hop_loc).reset_ltl()

    def age_entries(self):
        for entry in self.entries:
            entry.decrement_ltl()

        self.entries[:] = [entry for entry in self.entries if entry.left_to_live > 0]


class ForwardingTable:
    """
    Forwarding table stores the next hops for destination locators. It is routinely cleared and so will require
    updating.
    """

    DEFAULT_COST = 50

    def __init__(self, refresh_delay_secs: int):
        self.entries: Dict[int, NextHopList] = {}

        self.refresh_thread: threading.Thread = RefreshTableThread(refresh_delay_secs, self)
        self.refresh_thread.daemon = True
        self.refresh_thread.start()

    def refresh_entry(self, dest_loc: int, next_hop_loc: int):
        self.entries[dest_loc].refresh_ltl_for_hop(next_hop_loc)

    def __contains__(self, locator: int) -> bool:
        return locator in self.entries and len(self.entries[locator]) > 0

    def get_next_hop_list(self, dest_loc: int) -> NextHopList:
        return self.entries[dest_loc]

    def add_entry(self, dest_loc: int, next_hop_loc: int, cost: int = DEFAULT_COST):
        """
        :param dest_loc: destination that can be reached via the next hop
        :param next_hop_loc: next hop locator to reach the destination
        :param cost: cost of route via the next hop
        """
        if dest_loc not in self:
            self.entries[dest_loc] = NextHopList()

        self.entries[dest_loc].add_or_update(next_hop_loc, cost)

    def decrement_and_clear(self):
        next_hop_lists = self.entries.values()
        for next_hop_list in next_hop_lists:
            next_hop_list.age_entries()

        self.entries[:] = [next_hop_list for next_hop_list in next_hop_lists if len(next_hop_list) > 0]


class RefreshTableThread(threading.Thread):
    def __init__(self, refresh_delay: int, forwarding_table: ForwardingTable):
        super(RefreshTableThread, self).__init__()
        self.routing_table: ForwardingTable = forwarding_table
        self.refresh_delay: int = refresh_delay
        self.stopped: threading.Event = threading.Event()

    def run(self):
        while not self.stopped.is_set():
            self.routing_table.decrement_and_clear()
            time.sleep(self.refresh_delay)

    def stop(self):
        self.stopped.set()
