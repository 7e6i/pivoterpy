
# changes
- pvt.from_edge_list() now infers n from the number of unique nodes in the edge list

- graph object now translates node IDs to 0..n-1 internal IDs

- P.vertex_counts now returns a dict of lists. keys are the originally provided nodes

- rust setup uses a neighborhood list instead of bitsets

- rust global level 1 recursion uses a compressed bitset

- swapped matula-beck for batagelj-zaversnik degeneracy ordering algorithm

# todo

- make new tests for vertex counts (since it is a dict now)

- reimplement the rust vertex and edge count function with new logic (from global)