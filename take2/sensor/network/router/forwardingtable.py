import logging
from functools import reduce
from typing import Dict, List, Tuple

from sensor.network.router.groupmessages import Link

logger = logging.getLogger(__name__)


class ForwardingTableEntry:
    def __init__(self, next_hop_id):
        self.next_hop_id = next_hop_id


class ForwardingTable:
    """Stores a map of next hops for each destination id"""

    def __init__(self):
        self.next_hop_internal: Dict[int, ForwardingTableEntry] = {}
        self.next_hop_to_locator: Dict[int, ForwardingTableEntry] = {}

    def __str__(self):
        return str(vars(self))

    def get_next_internal_hop(self, dest_id):
        if dest_id in self.next_hop_internal:
            return self.next_hop_internal[dest_id].next_hop_id
        else:
            return None

    def add_internal_entry(self, dest_id, next_hop):
        logger.info("Adding ID:{}, NH:{} to table".format(dest_id, next_hop))
        self.next_hop_internal[dest_id] = ForwardingTableEntry(next_hop)

    def add_external_entry(self, dest_loc, next_hop):
        logger.info("Adding LOC:{}, NH:{} to table".format(dest_loc, next_hop))
        self.next_hop_to_locator[dest_loc] = ForwardingTableEntry(next_hop)


# https://www.sanfoundry.com/python-program-implement-floyd-warshall-algorithm/
class Vertex:
    def __init__(self, node_id):
        self.id = node_id
        self.adjacent: Dict[Vertex, int] = {}

    def add_neighbor(self, neighbour_vertex, cost):
        self.adjacent[neighbour_vertex] = cost

    def get_neighbours(self):
        return self.adjacent.keys()

    def get_id(self):
        return self.id

    def get_weight(self, neighbour_vertex):
        return self.adjacent[neighbour_vertex]

    def remove_neighbour(self, expired):
        del self.adjacent[expired]


def floyd_warshall(g) -> Tuple[Dict[Vertex, Dict[Vertex, float]], Dict[Vertex, Dict[Vertex, int]]]:
    """Return dictionaries distance and next_v.

    distance[u][v] is the shortest distance from vertex u to v.
    next_v[u][v] is the next vertex after vertex v in the shortest path from u
    to v. It is None if there is no path between them. next_v[u][u] should be
    None for all u.

    g is a Graph object which can have negative edge weights.
    """
    distance: Dict[Vertex, Dict[Vertex, float]] = {v: dict.fromkeys(g, float('inf')) for v in g}
    next_v: Dict[Vertex, Dict[Vertex, int]] = {v: dict.fromkeys(g, None) for v in g}

    for v in g:
        for n in v.get_neighbours():
            distance[v][n] = v.get_weight(n)
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


class LinkGraph:
    """Weighted graph of network"""

    def __init__(self):
        self.vertices: Dict[int, Vertex] = {}
        self.costs = {}

    def __iter__(self):
        return iter(self.vertices.values())

    def add_vertex(self, node_id):
        new_vertex = Vertex(node_id)
        self.vertices[node_id] = new_vertex

    def get_vertex(self, node_id):
        if node_id in self.vertices:
            return self.vertices[node_id]
        else:
            return None

    def get_neighbour_ids(self, node_id) -> List[int]:
        vertex = self.get_vertex(node_id)
        return [neighbour.id for neighbour in vertex.adjacent]

    def add_edge(self, from_node_id, to_node_id, cost=0):
        if from_node_id not in self.vertices:
            self.add_vertex(from_node_id)
        if to_node_id not in self.vertices:
            self.add_vertex(to_node_id)

        self.vertices[from_node_id].add_neighbor(self.vertices[to_node_id], cost)
        self.vertices[to_node_id].add_neighbor(self.vertices[from_node_id], cost)

    def get_vertices(self):
        return self.vertices.keys()

    def to_link_list(self) -> List[Link]:
        """Deconstructs graph into list of weighted links"""
        links = set()
        for vertex in self.vertices.values():
            for neighbour, cost in vertex.adjacent.items():
                min_id = min(neighbour.id, vertex.id)
                max_id = max(neighbour.id, vertex.id)
                links.add((min_id, max_id, cost))

        return [Link(node_a, node_b, cost) for node_a, node_b, cost in links]

    def update_forwarding_table(self, forwarding_table: ForwardingTable, root_id: int):
        """Recalculate best next hop for each node in local network based on current values"""
        logger.info("Starting forwarding table update")
        costs, next_hops = floyd_warshall(self)
        self.costs = costs
        new_internal_table = {}
        start = self.get_vertex(root_id)
        for end in self:
            if end is root_id or next_hops[start][end] is None:
                continue

            new_internal_table[end.id] = ForwardingTableEntry(next_hops[start][end])

        logger.info("Updated forwarding table")
        logger.info(str(forwarding_table))

        forwarding_table.next_hop_internal = new_internal_table

    def get_center(self) -> int:
        logger.info("Calculating the center of the group")
        costs, next_hops = floyd_warshall(self)
        vertex_to_max_distance = {}
        for vertex in self:
            vertex_to_max_distance[vertex] = max([cost for cost in costs[vertex].values()])

        center = None
        min_max_cost = None
        for vertex, max_cost in vertex_to_max_distance.items():
            if center is None:
                center = vertex
                min_max_cost = max_cost
            elif max_cost < min_max_cost:
                center = vertex
                min_max_cost = max_cost

        logger.info("Elected {} as center".format(center.id))
        return center.id

    def add_edges(self, entry_list: List[Link]):
        logger.info("Adding list of links to graph")
        for entry in entry_list:
            self.add_edge(entry.node_a_id, entry.node_b_id, entry.cost)

    def get_neighbours_to_flood(self, my_id, origin_id) -> List[int]:
        # Get all nodes the same number of hops away as me from source and assume they've been reached
        logger.info("Getting list of neighbours to flood")
        seen = set()
        me = self.get_vertex(my_id)
        start = self.get_vertex(origin_id)
        while me not in seen:
            for neighbour in start.adjacent:
                seen.add(neighbour)

        return [neighbour.id for neighbour in me.adjacent.keys() if neighbour not in seen]

    def remove_vertex(self, expired_node):
        expired: Vertex = self.get_vertex(expired_node)
        # Remove links from neighbours
        for neighbour in expired.adjacent:
            neighbour.remove_neighbour(expired)

        # Remove from graph
        del self.vertices[expired_node]

    def get_distance(self, node_one_id, node_two_id):
        if node_one_id == node_two_id:
            return 0

        v_a = self.get_vertex(node_one_id)
        v_b = self.get_vertex(node_two_id)

        return self.costs[v_a][v_b]
