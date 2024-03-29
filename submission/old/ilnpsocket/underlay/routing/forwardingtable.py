import logging
from typing import Dict, List


class ForwardingEntry:
    """
    A record of the cost of a route via the next hop
    """

    def __init__(self, next_hop_locator: int, cost: int):
        self.cost: int = cost
        self.next_hop_locator: int = next_hop_locator
        self.left_to_live: int = 10

    def __str__(self):
        return str(vars(self))

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
    """
    A list of possible next hops, which can be aged and removed
    """

    def __init__(self):
        self.entries: Dict[int, ForwardingEntry] = {}

    def __contains__(self, next_hop_loc: int) -> bool:
        return next_hop_loc in self.entries

    def __len__(self) -> int:
        return len(self.entries)

    def __str__(self):
        return str([str(entry) for entry in self.entries])

    def add_or_update(self, next_hop_loc: int, cost: int):
        if next_hop_loc in self:
            entry: ForwardingEntry = self.get_entry_for_next_hop(next_hop_loc)
            entry.cost = cost
            entry.reset_ltl()
        else:
            self.entries[next_hop_loc] = ForwardingEntry(next_hop_loc, cost)

    def get_entry_for_next_hop(self, next_hop_loc: int) -> ForwardingEntry:
        try:
            return self.entries[next_hop_loc]
        except KeyError:
            raise ValueError("No entry for %d" % next_hop_loc)

    def refresh_ltl_for_hop(self, next_hop_loc: int):
        self.get_entry_for_next_hop(next_hop_loc).reset_ltl()

    def age_entries(self):
        for entry in self.entries.values():
            entry.decrement_ltl()

        self.entries = {loc: entry for loc, entry in self.entries.items() if entry.left_to_live > 0}


class ForwardingTable:
    """
    Forwarding table stores the next hops for destination locators. It is routinely cleared and so will require
    updating.
    """

    DEFAULT_COST = 50

    def __init__(self):
        self.entries: Dict[int, NextHopList] = {}
        logging.debug("Forwarding table initialized")

    def refresh_entry(self, dest_loc: int, next_hop_loc: int):
        self.entries[dest_loc].refresh_ltl_for_hop(next_hop_loc)
        logging.debug("Finished refreshing forwarding table entries")

    def __contains__(self, locator: int) -> bool:
        return locator in self.entries and len(self.entries[locator]) > 0

    def __str__(self):
        val = ""
        for name, next_hop_list in self.entries.items():
            val += "{:>15} | {:<15}\n".format(name, str(next_hop_list))

        return val

    def get_next_hop_list(self, dest_loc: int) -> NextHopList:
        return self.entries[dest_loc]

    def add_or_update_entry(self, dest_loc: int, next_hop_loc: int, cost: int = DEFAULT_COST):
        """
        :param dest_loc: destination that can be reached via the next hop
        :param next_hop_loc: next hop locator to reach the destination
        :param cost: cost of route via the next hop
        """
        logging.debug("Adding dest %d via next hop %s with cost %d to forwarding table", dest_loc, next_hop_loc, cost)
        if dest_loc not in self:
            self.entries[dest_loc] = NextHopList()

        self.entries[dest_loc].add_or_update(next_hop_loc, cost)

    def decrement_and_clear(self) -> bool:
        """
        Ages the contents of the forwarding table, and removes any entries that haven't been proven in a while
        :return: true if any entries were removed
        """
        logging.debug("Aging entries and removing expired")
        removed = False
        next_hop_lists = self.entries.values()
        for next_hop_list in next_hop_lists:
            original_num_entries = len(next_hop_list)
            next_hop_list.age_entries()
            if original_num_entries != len(next_hop_list):
                removed = True

        self.entries = {dest_loc: next_hop_list for dest_loc, next_hop_list in self.entries.items()
                        if len(next_hop_list) > 0}

        return removed
