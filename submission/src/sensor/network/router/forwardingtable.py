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
        # Next hop ids and their lambda
        self.bridge_node_lambdas: Dict[int, int] = {}

    def get_bridge_node_lambdas(self) -> Dict[int, int]:
        return self.bridge_node_lambdas

    def add_bridge_node(self, node_id, cost):
        self.bridge_node_lambdas[node_id] = cost

    def remove_bridge_node(self, node_id):
        del self.bridge_node_lambdas[node_id]


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
        del self.locator_links[linked_locator].bridge_node_lambdas[linking_node_id]

        # Remove the external link if no more bridging nodes exist
        if len(self.locator_links[linked_locator].bridge_node_lambdas) == 0:
            del self.locator_links[linked_locator]

    def get_locator_of_bridge_node(self, bridge_node_id: int) -> Optional[int]:
        for locator_link in self.locator_links.values():
            if bridge_node_id in locator_link.bridge_node_lambdas:
                return locator_link.locator

        return None

    def is_border_node(self) -> bool:
        return len(self.locator_links) > 0


class ZonedNetworkGraph:
    """Weighted graph of network, with full internal topology, and links to neighbouring networks"""

    def __init__(self, my_id: int, my_lambda: int):
        self.id_to_node: Dict[int, InternalNode] = {}
        self.locator_to_border_node_ids: Dict[int, List[int]] = {}

        self.add_node(my_id, my_lambda)

    def __iter__(self):
        return iter(self.get_all_nodes())

    def __str__(self):
        lsdb = self.to_lsdb_message(0)
        return str(lsdb)

    def get_all_nodes(self):
        return self.id_to_node.values()

    def get_border_node_ids(self) -> Set[int]:
        """Flattens locator to border node ids to provide the set of all border nodes"""
        border_node_set = set()
        for border_node_list in self.locator_to_border_node_ids.values():
            border_node_set.update(border_node_list)

        return border_node_set

    def add_node(self, node_id: int, node_lambda: int):
        """Add a new node to the network"""
        logger.info("Adding node {} to network ".format(node_id))
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

        logger.info("Adding link between {} and {}".format(from_node_id, to_node_id))
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

    def remove_internal_link(self, node_a: InternalNode, node_b: InternalNode):
        """Removes the link between two nodes"""
        node_a.remove_internal_link(node_b)
        node_b.remove_internal_link(node_a)

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
            if not self.contains_internal_link(link):
                self.add_internal_link(link.a, link.a_lambda, link.b, link.b_lambda)
                difference_found = True

        for link in external_links:
            if not self.contains_external_link(link):
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
        return link.bridge_node_id in external_link.bridge_node_lambdas.keys()

    def to_lsdb_message(self, sequence_number: int) -> LSDBMessage:
        """Deconstructs graph into list of weighted links"""
        # {(node_a_id, node_b_id):(node_a_lambda, node_b_lambda)}
        internal_links: Dict[Tuple[int, int], Tuple[int, int]] = {}
        # {(border_node_id, bridge_node_id, bridge_node_locator, bridge_node_lambda)}
        locator_links: Set[Tuple[int, int, int, int]] = set()

        # Produce description of internal links
        for node in self.get_internal_nodes():
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
        border_node_ids: Set[int] = self.get_border_node_ids()
        for border_node_id in border_node_ids:
            border_node = self.get_node(border_node_id)
            locator_links_for_this_node = border_node.locator_links.values()

            locator_link: LocatorLink
            for locator_link in locator_links_for_this_node:
                # For each node in the other locator that this node can reach
                for bridge_node_id, bridge_node_lambda in locator_link.bridge_node_lambdas.items():
                    locator_links.add((border_node_id, bridge_node_id, locator_link.locator, bridge_node_lambda))

        internal_link_list = [InternalLink(a, cost_a, b, cost_b) for (a, b), (cost_a, cost_b) in internal_links.items()]
        external_link_list = [ExternalLink(border_id, locator, bridge_id, bridge_lambda)
                              for border_id, bridge_id, locator, bridge_lambda in locator_links]

        return LSDBMessage(sequence_number, internal_link_list, external_link_list)

    def remove_link(self, node_a_id: int, node_b_id: int) -> bool:
        """
        Removes the link between node a and node b.
        Node a is assumed to be an internal node in all cases
        :returns true if a change was made i.e. this link existed and was removed
        """
        node_a: InternalNode = self.get_node(node_a_id)
        node_b: InternalNode = self.get_node(node_b_id)

        node_b_is_in_a_different_locator = node_b is None
        if node_b_is_in_a_different_locator:
            # Find what locator this node is in
            locator = node_a.get_locator_of_bridge_node(node_b_id)
            if locator is not None:
                self.remove_external_link(node_a_id, locator, node_b_id)
                return True
        elif node_b in node_a.get_internal_neighbours():
            self.remove_internal_link(node_a, node_b)
            return True

        # Link must have already been removed woah
        return False


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

    def find_next_hop_for_locator(self, dest_loc: int) -> Optional[int]:
        """Finds the next hop to reach the given locator"""
        if dest_loc in self.next_hop_to_locator:
            return self.next_hop_to_locator[dest_loc]
        else:
            return None

    def add_internal_entry(self, dest_id: int, next_hop: int):
        """Adds or replaces the next hop to reach the given id"""
        logger.info("Adding ID:{}, NH:{} to table".format(dest_id, next_hop))
        self.next_hop_internal[dest_id] = next_hop

    def add_external_entry(self, dest_loc: int, next_hop: int):
        """Adds or replaces the next hop to reach the given locator"""
        logger.info("Adding LOC:{}, NH:{} to table".format(dest_loc, next_hop))
        self.next_hop_to_locator[dest_loc] = next_hop

    def record_locator_for_id(self, node_id: int, node_locator: int):
        self.locator_cache[node_id] = node_locator

    def get_locator_for_id(self, node_id) -> Optional[int]:
        if node_id in self.locator_cache:
            return self.locator_cache[node_id]
        else:
            return None

    def clear(self):
        self.next_hop_internal.clear()
        self.next_hop_to_locator.clear()


def get_distance_and_next_hops(network_graph: ZonedNetworkGraph, root_node_id: int):
    """Get possible next hops that provide same distance to destination for all destinations"""
    # { end node: cost}
    distance_from_root: Dict[InternalNode, float] = {}
    # { end node: [next hops that are the same distance] }
    next_hops_for_destination: Dict[InternalNode, List[InternalNode]] = {}

    root = network_graph.get_node(root_node_id)
    distance_from_root[root] = 0
    next_hops_for_destination[root] = None
    # Nodes to be visited
    queue = []

    # Initialise next hop with one hop neighbours
    depth = 1
    for neighbour in root.get_internal_neighbours():
        distance_from_root[neighbour] = depth
        next_hops_for_destination[neighbour] = [neighbour]
        queue.append(neighbour)

    while queue:
        depth += 1
        current = queue.pop()
        for neighbour in current.get_internal_neighbours():
            # If not already seen
            if neighbour not in distance_from_root:
                distance_from_root[neighbour] = depth
                next_hops_for_destination[neighbour] = next_hops_for_destination[current]
                queue.append(neighbour)
            # If seen, but an alternative path is found at the same distance, record other next hop
            elif distance_from_root[neighbour] == depth \
                    and next_hops_for_destination[current] not in next_hops_for_destination[neighbour]:
                next_hops_for_destination[neighbour].extend(next_hops_for_destination[current])

    return distance_from_root, next_hops_for_destination


def update_forwarding_table(network_graph: ZonedNetworkGraph, root_node_id: int, forwarding_table: ForwardingTable):
    forwarding_table.clear()

    distance_from_root: Dict[InternalNode, float]
    next_hops_for_destination: Dict[InternalNode, List[InternalNode]]
    distance_from_root, next_hops_for_destination = get_distance_and_next_hops(network_graph, root_node_id)

    destination: InternalNode
    next_hops: List[InternalNode]
    current_distance_to_locator: Dict[int, float] = {}
    for destination, next_hops in next_hops_for_destination.items():
        # If more options, choose the one with the best lambda
        if next_hops is None:
            continue
        elif len(next_hops) > 0:
            next_hop = reduce(lambda best, nxt: nxt if best is None or nxt.node_lambda > best.node_lambda else best,
                              next_hops, None)
        else:
            next_hop = next_hops.pop()

        # Add entry to internal forwarding table
        forwarding_table.add_internal_entry(destination.node_id, next_hop.node_id)

        # If this is a border node that can get us to a locator
        if destination.is_border_node():
            linked_locators = destination.get_linked_locators()
            for locator in linked_locators:
                # Replace if better connection to that locator exists
                if locator not in current_distance_to_locator \
                        or current_distance_to_locator[locator] > distance_from_root[destination]:
                    current_distance_to_locator[locator] = distance_from_root[destination]
                    forwarding_table.add_external_entry(locator, next_hop.node_id)

    # Finally, add next hop for other locators if I am the border node.
    root = network_graph.get_node(root_node_id)
    if root.is_border_node():
        logger.info("Adding my external links")
        for locator in root.get_linked_locators():
            logger.info("Choosing best next hop for loc {}".format(locator))
            # Gets best next hop from available links to that locator
            best = None
            for node_id, node_lambda in root.get_links_to_locator(locator).get_bridge_node_lambdas().items():
                if best is None or node_lambda > best[1]:
                    best = (node_id, node_lambda)

            logger.info("Chose {}".format(best[0]))
            forwarding_table.add_external_entry(locator, best[0])
