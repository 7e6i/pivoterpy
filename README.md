# pivoterpy
Pure Python implementation of Pivoter clique counting algorithm.

See instructions below on how to use, but first, the lore.

## the lore...

> April 1971 
- Bron-Kerbosch algorithm created by... *C. Bron* and *J. Kerbosch*.
- [Algorithm 457, Finding All Cliques of an Undirected Graph [H]](https://dl.acm.org/doi/pdf/10.1145/362342.362367)

> October 2006
- *E. Tomitaa*, *A. Tanaka*, *H. Takahashia* say this is a difficult problem.
- [The worst-case time complexity for generating all maximal cliques
and computational experiments](https://snap.stanford.edu/class/cs224w-readings/tomita06cliques.pdf)


> Jun 2010, March 2011
- Double header by *D. Eppstein*, *M. Loffler*, *D. Strash* ([code](https://github.com/darrenstrash/quick-cliques))
- [Listing All Maximal Cliques in Sparse Graphs in
Near-optimal Time](https://arxiv.org/pdf/1006.5440)
- [Listing All Maximal Cliques in
Large Sparse Real-World Graph](https://arxiv.org/pdf/1103.0318)


> January 2020
- *S. Jain*, *C. Seshadhri* drop an absolute banger: Pivoter ([code](https://github.com/sjain12/Pivoter)).
- [The Power of Pivoting for Exact Clique Counting](https://arxiv.org/abs/2001.06784)

> April 2022
- **PyPivoter**: a python wrapper for the original C++ implementation ([code](https://github.com/rckormos/PyPivoter))


> Oct 2025
- **pivoterpy**: pure Python implementation (with parallelization!)


## installation

```
# pip install git+https://github.com/7e6i/pivoterpy

from pivoterpy import Pivoter
```

## usage
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
features
- per edge clique counts
- get on PyPI
- max-clique size parameter

settings
- calculate ec, save clique counts?
- calculate curvs, save vertex clique counts?
- save edge clique counts?