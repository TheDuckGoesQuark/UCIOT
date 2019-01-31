# README

# Questions for Saleem 

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

On-Deman
- flood with routing request when destination unknown
- recipients that don't know path will append themselves to path message before replying

## Processes

Changing locators
- Update local knowledge of own locator values
- Inform active correspondent nodes (CNs) of the changes
- ID does not change. Immutable.

 Neighbourhood Discovery
- Apparently IPv6 method can be used
