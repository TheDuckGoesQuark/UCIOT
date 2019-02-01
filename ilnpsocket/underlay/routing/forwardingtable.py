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
        self.entries[destination_locator] = ForwardingEntry(next_hop_locator, cost)

    def record_path(self, dest_locator, arriving_locator, route_cost):
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
            return [self.retrieve_entry_for(packet_dest_locator)]
        else:
            return []

    def clear_table(self):
        self.entries.clear()


class RefreshTableThread(threading.Thread):
    def __init__(self, refresh_delay, routing_table):
        super(RefreshTableThread, self).__init__()
        self.routing_table = routing_table
        self.refresh_delay = refresh_delay
        self.running = True

    def run(self):
        while self.running:
            self.routing_table.clear_table()
            time.sleep(self.refresh_delay)

    def stop(self):
        self.running = False


class ForwardingEntry:
    def __init__(self, next_hop_locator, cost):
        self.cost = cost
        self.next_hop_locator = next_hop_locator

    def should_be_replaced_by(self, route_cost):
        """A lower cost, or  equally good but more recent route cost will be preferred."""
        return self.cost >= route_cost

    def change_path(self, new_next_hop, new_cost):
        """Updates next hop and cost for this destination entry"""
        self.next_hop_locator = new_next_hop
        self.cost = new_cost