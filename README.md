# README

# Questions for Saleem 

Subnetting (RFC6741) (Prefix 48 bits, subnet selector 16 bits)
- Should longest prefix routing be used (should still work?) for locator values? i.e. do 'subnets' still apply in ILNP?
- What does the locator prefix and subnet selector mean in terms of topology (possibly answered by the above)?

Address types
- Confirm understanding: Identifier -> Link layer address, Locator -> Network layer address 
- ILNP Equivalent of link local scope addresses (all nodes, all routers), do I need to support these?

NDB (RFC4861)
- Neighbor advertisement being used to announce a link-layer address change, would
these be replaced with locator update messages? Do i need to worry about these? 
I've left a stub where the NDP options can be easily inserted in the relevant icmp messages if so

# Reading
Understand 'link layer' address in ILNP and IP

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