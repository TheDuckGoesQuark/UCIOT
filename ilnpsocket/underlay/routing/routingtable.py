import threading
import time


class RoutingTable:
    def __init__(self, max_hop_limit, refresh_delay_secs):
        self.max_hop_limit = max_hop_limit
        self.entries = {}
        self.refresh_thread = RefreshTableThread(refresh_delay_secs, self)
        self.refresh_thread.daemon = True
        self.refresh_thread.start()

    def has_entry_for(self, locator):
        return locator in self.entries

    def retrieve_entry_for(self, locator):
        return self.entries[locator]

    def calc_route_cost(self, packet):
        return self.max_hop_limit - packet.hop_limit

    def add_entry(self, destination_locator, next_hop_locator, cost):
        self.entries[destination_locator] = RoutingEntry(next_hop_locator, cost)

    def update_routing_table(self, packet, locator_interface):
        route_cost = self.calc_route_cost(packet)

        if self.has_entry_for(packet.dest_locator):
            entry = self.retrieve_entry_for(packet.dest_locator)

            if entry.should_be_replaced_by(route_cost):
                entry.change_path(locator_interface, route_cost)
        else:
            self.add_entry(packet.dest_locator, locator_interface, route_cost)

    def find_next_hop(self, packet_dest_locator):
        if self.has_entry_for(packet_dest_locator):
            return self.retrieve_entry_for(packet_dest_locator)
        else:
            return None

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


class RoutingEntry:
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
