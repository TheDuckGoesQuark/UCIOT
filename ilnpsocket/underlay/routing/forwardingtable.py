import threading
import time


class ForwardingTable:
    """
    Forwarding table stores the next hops for destination locators. It is routinely cleared and so will require
    updating.
    """

    def __init__(self, refresh_delay_secs):
        self.entries = {}
        self.refresh_thread = RefreshTableThread(refresh_delay_secs, self)
        self.refresh_thread.daemon = True
        self.refresh_thread.start()

    def has_entry_for(self, locator):
        return locator in self.entries

    def retrieve_entry_for(self, locator):
        return self.entries[locator]

    def add_entry(self, destination_locator, next_hop_locator, cost):
        if destination_locator in self.entries:
            self.entries[destination_locator] = [ForwardingEntry(next_hop_locator, cost)]
        else:
            self.entries[destination_locator].append([ForwardingEntry(next_hop_locator, cost)])

    def record_entry(self, dest_locator, arriving_locator, route_cost):
        """
        Uses the packet source and hop count to estimate number of hops to source address.
        This information alongside the arriving interface is used to identify the best next-hop
        for packets for that address
        :param route_cost: cost of route
        :param dest_locator: locator reachable via arriving locator
        :param arriving_locator: interface packet arrived on
        """
        if self.has_entry_for(dest_locator):
            entry = self.retrieve_entry_for(dest_locator)

            if entry.should_be_replaced_by(route_cost):
                entry.change_path(arriving_locator, route_cost)
        else:
            self.add_entry(dest_locator, arriving_locator, route_cost)

    def find_next_hops(self, packet_dest_locator):
        if self.has_entry_for(packet_dest_locator):
            return self.retrieve_entry_for(packet_dest_locator).next_hop_locator
        else:
            return []

    def decrement_and_clear(self):
        for entry_list in self.entries.values():
            entry_list[:] = map(lambda x: x.decrement_ltl(), entry_list)
            entry_list[:] = filter(lambda x: x.left_to_live > 0, entry_list)

    def print_contents(self):
        print("INFO - Current state of forwarding table before refreshing:")
        print("INFO - Destination, NextHop, Cost")
        for dest, entry in self.entries.items():
            print("INFO - {}, {}, {}".format(dest, entry.next_hop_locator, entry.cost))


class RefreshTableThread(threading.Thread):
    def __init__(self, refresh_delay, routing_table):
        super(RefreshTableThread, self).__init__()
        self.routing_table = routing_table
        self.refresh_delay = refresh_delay
        self.running = True

    def run(self):
        while self.running:
            self.routing_table.print_contents()
            self.routing_table.decrement_and_clear()
            time.sleep(self.refresh_delay)

    def stop(self):
        self.running = False


class ForwardingEntry:
    def __init__(self, next_hop_locator, cost):
        self.cost = cost
        self.next_hop_locator = next_hop_locator
        self.left_to_live = 10

    def should_be_replaced_by(self, route_cost):
        """A lower cost, or  equally good but more recent route cost will be preferred."""
        if self.left_to_live == 0:
            return True
        else:
            return self.cost >= route_cost

    def change_path(self, new_next_hop, new_cost):
        """Updates next hop and cost for this destination entry"""
        self.next_hop_locator = new_next_hop
        self.cost = new_cost
        self.reset_ltl()

    def reset_ltl(self):
        self.left_to_live = 10

    def decrement_ltl(self):
        self.left_to_live = self.left_to_live - 1
