# pivoterpy
Pure Python implementation of Pivoter clique counting algorithm.

## installation

```
# pip install git+https://github.com/7e6i/pivoterpy

from pivoterpy import Pivoter
```

## setup
For edge lists, all entries must be (u,v) with 0<= u < v < n.

```
# (n x n) adjacency matrix
G = Pivoter("adj", array=matrix)

# (m x 2) edge list (and number of nodes)
G = Pivoter("edge", array=edge_list, n=nodes)

# available after construction
G.neighborhoods
G.degrees
G.by_degrees
G.degeneracy
G.node_by_degen_order
G.degen_order_by_node
G.degen_order_nbhds
```

## counting
Non mp better for small dense graphs.
Mp better for large sparse graphs.

```
# calculations
G.count_cliques(get_curv=True) 
G.count_cliques_mp(procs=4)


# available results
G.ec
G.clique_counts

# if get_curv=True
G.vertex_clique_counts
G.curvatures
```


# todo
- per edge clique counts
- get on PyPI