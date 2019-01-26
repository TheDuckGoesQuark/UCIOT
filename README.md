# README

# Questions for Saleem 

Subnetting (RFC6741) (Prefix 48 bits, subnet selector 16 bits)
- Should longest prefix routing be used (should still work?)
- What does the locator prefix and subnet selector mean in terms of topology?

Address types
- ILNP Equivalent of link local scope addresses (all nodes, all routers)?

NDB (RFC4861)
- Neighbor advertisement being used to announce a link-layer address change, would
these be replaced with locator update messages?

## Routing Methods

Random Walks
Probabilistic load balancing.
- Simple
- Low memory and computation cost 
- Unrealistic topologies

Multipath
Maintain multiple paths between nodes to reduce traffic on 'best' routes
- Inherent load balancing
- More computation and memory footprint

## Processes

 Changing locators
- Update local knowledge of own locator values
- Inform active correspondent nodes (CNs) of the changes
- ID does not change. Immutable.

 Neighbourhood Discovery
- Apparently IPv6 method can be used