import logging
from typing import Dict, Optional, Tuple, List

from sensor.network.router.controlmessages import Link, LSBMessage
from sensor.network.router.ilnp import ILNPAddress

logger = logging.getLogger(__name__)


class ExternalLink:
    """Represents a link to another locator, and all available next hops to reach that locator"""

    def __init__(self, locator: int):
        self.locator = locator
        # Next hop ids and their cost
        self.bridge_node_ids: Dict[int, int] = {}

    def add_bridge_node(self, node_id, cost):
        self.bridge_node_ids[node_id] = cost

    def remove_bridge_node(self, node_id):
        del self.bridge_node_ids[node_id]


class InternalNode:
    """Each node has internal links with other nodes, and external links with other locators"""

    def __init__(self, node_id: int):
        self.node_id = node_id
        # Internal nodes and their link cost
        self.internal_link_costs: Dict[InternalNode, int] = {}
        # Locators this node can reach and the link cost
        self.external_link_costs: Dict[int, ExternalLink] = {}

    def add_internal_neighbour(self, neighbour_node: 'InternalNode', cost: int):
        self.internal_link_costs[neighbour_node] = cost

    def get_internal_neighbours(self):
        return self.internal_link_costs.keys()

    def get_id(self):
        return self.node_id

    def get_internal_link_weight(self, neighbour_node: 'InternalNode'):
        return self.internal_link_costs[neighbour_node]

    def remove_internal_link(self, expired: 'InternalNode'):
        del self.internal_link_costs[expired]

    def add_external_link(self, linked_locator: int, node_id: int, cost: int):
        if linked_locator not in self.external_link_costs:
            self.external_link_costs[linked_locator] = ExternalLink(linked_locator)

        self.external_link_costs[linked_locator].add_bridge_node(node_id, cost)

    def get_linked_locators(self):
        return self.external_link_costs.keys()

    def get_links_to_linked_locators(self, linked_locator: int) -> ExternalLink:
        return self.external_link_costs[linked_locator]

    def remove_external_link(self, linked_locator: int, linking_node_id: int):
        # Remove the linkingg node as a bridge to that locator
        del self.external_link_costs[linked_locator].bridge_node_ids[linking_node_id]

        # Remove the external link if no more bridging nodes exist
        if len(self.external_link_costs[linked_locator].bridge_node_ids) == 0:
            del self.external_link_costs[linked_locator]

    def is_border_node(self) -> bool:
        return len(self.external_link_costs) > 0


def floyd_warshall(g) \
        -> Tuple[Dict[InternalNode, Dict[InternalNode, float]], Dict[InternalNode, Dict[InternalNode, int]]]:
    """Return dictionaries distance and next_v.
    distance[u][v] is the shortest distance from vertex u to v.
    next_v[u][v] is the next vertex after vertex v in the shortest path from u
    to v. It is None if there is no path between them. next_v[u][u] should be
    None for all u.
    g is a Graph object which can have negative edge weights.
    """
    distance: Dict[InternalNode, Dict[InternalNode, float]] = {v: dict.fromkeys(g, float('inf')) for v in g}
    next_v: Dict[InternalNode, Dict[InternalNode, int]] = {v: dict.fromkeys(g, None) for v in g}

    for v in g:
        for n in v.get_internal_neighbours():
            distance[v][n] = v.get_internal_link_weight(n)
            next_v[v][n] = n

    for v in g:
        distance[v][v] = 0
        next_v[v][v] = None

    for p in g:
        for v in g:
            for w in g:
                if distance[v][w] > distance[v][p] + distance[p][w]:
                    distance[v][w] = distance[v][p] + distance[p][w]
                    next_v[v][w] = next_v[v][p]

    return distance, next_v


class ZonedNetworkGraph:
    """Weighted graph of network, with full internal topology, and links to neighbouring networks"""

    def __init__(self):
        self.id_to_node: Dict[int, InternalNode] = {}
        self.locator_to_border_node_ids: Dict[int, List[int]] = {}

    def __iter__(self):
        return iter(self.id_to_node.values())

    def add_node(self, node_id: int):
        """Add a new node to the network"""
        node = InternalNode(node_id)
        self.id_to_node[node_id] = node

    def get_node(self, node_id) -> Optional[InternalNode]:
        """Get a node from the network graph"""
        return self.id_to_node.get(node_id, None)

    def get_internal_neighbour_ids(self, node_id) -> List[int]:
        node = self.get_node(node_id)
        return [neighbour.node_id for neighbour in node.internal_link_costs]

    def add_internal_link(self, from_node_id, to_node_id, cost=0):
        if from_node_id not in self.id_to_node:
            self.add_node(from_node_id)
        if to_node_id not in self.id_to_node:
            self.add_node(to_node_id)

        self.id_to_node[from_node_id].add_internal_neighbour(self.get_node(to_node_id), cost)
        self.id_to_node[to_node_id].add_internal_neighbour(self.get_node(from_node_id), cost)

    def add_external_link(self, border_node_id: int, external_locator: int, external_note_id: int, cost: int):
        local_node = self.get_node(border_node_id)

        # Add node from other locator as link
        local_node.add_external_link(external_locator, external_note_id, cost)

        # Add this node as a bridge to an external locator for quicker lookup
        if external_locator not in self.locator_to_border_node_ids:
            self.locator_to_border_node_ids[external_locator] = []

        self.locator_to_border_node_ids[external_locator].append(local_node.get_id())

    def remove_external_link(self, border_node_id: int, external_locator: int, external_node_id: int):
        local_node = self.get_node(border_node_id)

        # Remove link to node in other locator
        local_node.remove_external_link(external_locator, external_node_id)

        # Check if this node can still act as a bridge to that locator
        if external_locator not in local_node.get_linked_locators():
            self.__remove_node_as_locator_link(external_locator, local_node)

    def __remove_node_as_locator_link(self, locator: int, border_node: InternalNode):
        # Remove this node as a link to that locator
        self.locator_to_border_node_ids[locator].remove(border_node.get_id())

        if len(self.locator_to_border_node_ids[locator]) == 0:
            # Remove any record of that locator if this was the only link
            del self.locator_to_border_node_ids[locator]

    def get_internal_nodes(self):
        return self.id_to_node.values()

    def remove_internal_node(self, node_id):
        """Removes a node that is in the same network"""
        expired: InternalNode = self.get_node(node_id)
        # Remove links from internal neighbours
        for external_neighbour in expired.internal_link_costs:
            external_neighbour.remove_internal_link(expired)

        # Remove records of links to external neighbours via the node being deleted
        if expired.is_border_node():
            self.__remove_border_node(expired)

        # Remove from graph
        del self.id_to_node[node_id]

    def __remove_border_node(self, border_node: InternalNode):
        """Removes this node as a potential bridge to all its locators,"""
        for locator in border_node.external_link_costs:
            self.__remove_node_as_locator_link(locator, border_node)


def lsb_message_from_network_graph(network: ZonedNetworkGraph, sequence_number: int) -> LSBMessage[Link]:
    """Deconstructs graph into list of weighted links"""
    internal_links = set()
    external_links = set()

    for node in network.get_internal_nodes():
        node_id = node.get_id()

        for neighbour, cost in node.internal_link_costs.items():
            # Links are (lowest_id, highest_id) tuple for quick uniqueness check
            neighbour_id = neighbour.get_id()
            min_id = min(neighbour_id, node_id)
            max_id = max(neighbour_id, node_id)
            internal_links.add((min_id, max_id, cost))

    for locator, border_node_ids in network.locator_to_border_node_ids:
        for border_node_id in border_node_ids:
            external_links.add((locator, border_node_id))

    internal_link_list = [Link(a, b, cost) for a, b, cost in internal_links]
    external_link_list = [Link(loc, border, 0) for loc, border in external_links]
    lsb = LSBMessage(sequence_number, internal_link_list, external_link_list)

    return lsb


class ForwardingTable:
    """Stores a map of next hops for each destination id and locator, and caches the locators for often requested IDs"""

    def __init__(self):
        self.next_hop_internal: Dict[int, int] = {}
        self.next_hop_to_locator: Dict[int, int] = {}
        self.locator_cache: Dict[int, int] = {}

    def __str__(self):
        return str(vars(self))

    def get_next_hop(self, dest: ILNPAddress, dest_is_local) -> Optional[int]:
        """Finds the next hop to reach the node with the given ID if local, or the next hop to the locator otherwise"""
        if dest_is_local:
            return self.find_next_hop_for_local_node(dest.id)
        else:
            return self.find_next_hop_for_locator(dest.loc)

    def find_next_hop_for_local_node(self, dest_id) -> Optional[int]:
        """Finds the next hop to the node with the given id"""
        if dest_id in self.next_hop_internal:
            return self.next_hop_internal[dest_id]
        else:
            return None

    def find_next_hop_for_locator(self, dest_loc) -> Optional[int]:
        """Finds the next hop to reach the given locator"""
        if dest_loc in self.next_hop_to_locator:
            return self.next_hop_to_locator[dest_loc]
        else:
            return None

    def add_internal_entry(self, dest_id, next_hop):
        """Adds or replaces the next hop to reach the given id"""
        logger.info("Adding ID:{}, NH:{} to table".format(dest_id, next_hop))
        self.next_hop_internal[dest_id] = next_hop

    def add_external_entry(self, dest_loc, next_hop):
        """Adds or replaces the next hop to reach the given locator"""
        logger.info("Adding LOC:{}, NH:{} to table".format(dest_loc, next_hop))
        self.next_hop_to_locator[dest_loc] = next_hop

    def record_locator_for_id(self, node_id, node_locator):
        self.locator_cache[node_id] = node_locator

    def get_locator_for_id(self, node_id) -> Optional[int]:
        if node_id in self.locator_cache:
            return self.locator_cache[node_id]
        else:
            return None
