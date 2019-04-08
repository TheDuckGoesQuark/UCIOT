import logging
from functools import reduce
from typing import Dict, Optional, Tuple, List, Set

from sensor.network.router.controlmessages import InternalLink, LSDBMessage, ExternalLink
from sensor.network.router.ilnp import ILNPAddress

logger = logging.getLogger(__name__)


class LocatorLink:
    """Represents a link to another locator, and all available next hops to reach that locator"""

    def __init__(self, locator: int):
        self.locator = locator
        # Next hop ids and their cost
        self.bridge_node_costs: Dict[int, int] = {}

    def add_bridge_node(self, node_id, cost):
        self.bridge_node_costs[node_id] = cost

    def remove_bridge_node(self, node_id):
        del self.bridge_node_costs[node_id]


class InternalNode:
    """Each node has internal links with other nodes, and external links with other locators"""

    def __init__(self, node_id: int, node_lambda: int):
        self.node_id = node_id
        self.node_lambda = node_lambda
        # Internal nodes and their link cost
        self.linked_nodes: Set[InternalNode] = set()
        # Locators this node can reach and the link cost
        self.locator_links: Dict[int, LocatorLink] = {}

    def add_internal_neighbour(self, neighbour_node: 'InternalNode'):
        self.linked_nodes.add(neighbour_node)

    def get_internal_neighbours(self) -> Set['InternalNode']:
        return self.linked_nodes

    def get_id(self) -> int:
        return self.node_id

    def remove_internal_link(self, node_to_remove: 'InternalNode'):
        self.linked_nodes.remove(node_to_remove)

    def add_external_link(self, linked_locator: int, node_id: int, cost: int):
        if linked_locator not in self.locator_links:
            self.locator_links[linked_locator] = LocatorLink(linked_locator)

        self.locator_links[linked_locator].add_bridge_node(node_id, cost)

    def get_linked_locators(self):
        return self.locator_links.keys()

    def get_links_to_locator(self, linked_locator: int) -> LocatorLink:
        return self.locator_links[linked_locator]

    def remove_link_to_locator(self, linked_locator: int, linking_node_id: int):
        # Remove the linking node as a bridge to that locator
        del self.locator_links[linked_locator].bridge_node_costs[linking_node_id]

        # Remove the external link if no more bridging nodes exist
        if len(self.locator_links[linked_locator].bridge_node_costs) == 0:
            del self.locator_links[linked_locator]

    def is_border_node(self) -> bool:
        return len(self.locator_links) > 0


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

    def get_border_node_ids(self) -> Set[int]:
        """Flattens locator to border node ids to provide the set of all border nodes"""
        return reduce(lambda current_set, next_list: current_set.update(next_list),
                      self.locator_to_border_node_ids.values(), set())

    def add_node(self, node_id: int, node_lambda: int):
        """Add a new node to the network"""
        node = InternalNode(node_id, node_lambda)
        self.id_to_node[node_id] = node

    def get_node(self, node_id) -> Optional[InternalNode]:
        """Get a node from the network graph"""
        return self.id_to_node.get(node_id, None)

    def get_internal_neighbour_ids(self, node_id) -> List[int]:
        node = self.get_node(node_id)
        return [neighbour.node_id for neighbour in node.linked_nodes]

    def add_internal_link(self, from_node_id: int, from_node_lambda: int, to_node_id: int, to_node_lambda: int):
        if from_node_id not in self.id_to_node:
            self.add_node(from_node_id, from_node_lambda)
        if to_node_id not in self.id_to_node:
            self.add_node(to_node_id, to_node_lambda)

        self.id_to_node[from_node_id].add_internal_neighbour(self.get_node(to_node_id))
        self.id_to_node[to_node_id].add_internal_neighbour(self.get_node(from_node_id))

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
        local_node.remove_link_to_locator(external_locator, external_node_id)

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
        for external_neighbour in expired.linked_nodes:
            external_neighbour.remove_internal_link(expired)

        # Remove records of links to external neighbours via the node being deleted
        if expired.is_border_node():
            self.__remove_border_node(expired)

        # Remove from graph
        del self.id_to_node[node_id]

    def __remove_border_node(self, border_node: InternalNode):
        """Removes this node as a potential bridge to all its locators,"""
        for locator in border_node.locator_links:
            self.__remove_node_as_locator_link(locator, border_node)

    def add_all(self, lsdbmessage: LSDBMessage) -> bool:
        """
        Adds all links in the lsdb message to this network graph
        :param lsdbmessage: message containing an lsdb
        :return: true if this message contained a link that wasn't already recorded
        """
        internal_links = lsdbmessage.internal_links
        external_links = lsdbmessage.external_links

        difference_found = False
        for link in internal_links:
            if self.contains_internal_link(link):
                self.add_internal_link(link.a, link.a_lambda, link.b, link.b_lambda)
                difference_found = True

        for link in external_links:
            if self.contains_external_link(link):
                self.add_external_link(
                    link.border_node_id, link.locator, link.bridge_node_id, link.bridge_lambda
                )
                difference_found = True

        return difference_found

    def contains_internal_link(self, link: InternalLink) -> bool:
        """
        Checks for the existence of the nodes described in the link, and for a link between them
        :param link:
        :return: True if link exists
        """
        node_a = self.get_node(link.a)
        if node_a is None:
            return False

        node_b = self.get_node(link.b)
        if node_b is None:
            return False

        return node_b in node_a.get_internal_neighbours()

    def contains_external_link(self, link: ExternalLink) -> bool:
        """
        Checks for the existence of external link
        :param link:
        :return: True if link exists
        """
        border_node = self.get_node(link.border_node_id)
        if border_node is None:
            return False

        linked_locators = border_node.get_linked_locators()
        if link.locator not in linked_locators:
            return False

        external_link = border_node.locator_links[link.locator]
        return link.bridge_node_id in external_link.bridge_node_costs.keys()


def lsdb_message_from_network_graph(network: ZonedNetworkGraph, sequence_number: int) -> LSDBMessage:
    """Deconstructs graph into list of weighted links"""
    # {(node_a_id, node_b_id):(node_a_lambda, node_b_lambda)}
    internal_links: Dict[Tuple[int, int], Tuple[int, int]] = {}
    # {(border_node_id, bridge_node_id):(bridge_node_locator, bridge_node_lambda)}
    locator_links: Set[Tuple[int, int, int, int]] = set()

    # Produce description of internal links
    for node in network.get_internal_nodes():
        node_id = node.get_id()

        for neighbour in node.get_internal_neighbours():
            # Links are (lowest_id, highest_id) tuple for quick uniqueness check
            neighbour_id = neighbour.get_id()

            if neighbour_id < node_id:
                min_id = neighbour_id
                min_id_lambda = neighbour.node_lambda
                max_id = node_id
                max_id_lambda = node.node_lambda
            else:
                min_id = node_id
                min_id_lambda = node.node_lambda
                max_id = neighbour_id
                max_id_lambda = neighbour.node_lambda

            internal_links[(min_id, max_id)] = (min_id_lambda, max_id_lambda)

    # Produce description of external links
    border_node_ids: Set[int] = network.get_border_node_ids()
    for border_node_id in border_node_ids:
        border_node = network.get_node(border_node_id)
        locator_links = border_node.locator_links.values()

        # For each locator this node can reach
        locator_link: LocatorLink
        for locator_link in locator_links:
            # For each node in the other locator that this node can reach
            for bridge_node_id, bridge_node_lambda in locator_link.bridge_node_costs.items():
                locator_links.add((border_node_id, bridge_node_id, locator_link.locator, bridge_node_lambda))

    internal_link_list = [InternalLink(a, cost_a, b, cost_b) for (a, b), (cost_a, cost_b) in internal_links.items()]
    external_link_list = [ExternalLink(border_id, locator, bridge_id, bridge_lambda)
                          for border_id, locator, bridge_id, bridge_lambda in locator_links]

    return LSDBMessage(sequence_number, internal_link_list, external_link_list)


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
