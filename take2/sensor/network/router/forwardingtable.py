import logging
from typing import Dict, Optional

from sensor.network.router.ilnp import ILNPAddress

logger = logging.getLogger(__name__)


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
        if node_id in self.locator_cache :
            return self.locator_cache[node_id]
        else:
            return None

