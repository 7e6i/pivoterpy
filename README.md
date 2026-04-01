# pivoterpy
Pure Python implementation of `Pivoter` clique counting algorithm.

Based on <u>The Power of Pivoting for Exact Clique Counting</u> by *S. Jain*, *C. Seshadhri*.


## quick start

```
# pip install pivoterpy

from pivoterpy import Pivoter

G = Pivoter.from_adj_matrix(array)

G.count()

G.clique_counts
```

## timings
- Tested on complete graphs with $k$ nodes.
- **CPU**: AMD Ryzen 5 3600, **RAM**: 2x16GB DDR4-3200 CL16

**Results**

| $k$  | 100  | 200  | 300  | 400  | 500  | 600  | 700  | 800  | 900  | 1000 |
| ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- |
| time | 0:00 | 0:02 | 0:15 | 1:01 | 0:29 | 1:02 | 1:53 | 2:06 | 3:17 | 4:51 |
| procs |      |      |      |      | 4    | 4    | 4    | 8    | 8    | 8    |



# Documentation

## usage
For edge lists, all entries must be $(u,v)$ with $u,v\in\mathbb{Z}$ and $0\le u < v < n$.

```
# (n x n) adjacency matrix. Entry > 0 indicates an edge.
G = Pivoter.from_adj_matrix(adj_matrix)

# (m x 2) edge list (and number of nodes)
G = Pivoter.from_edge_list(edge_list, n)

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
- Non multi-proc (default) is generally better for small dense graphs.
- Multi-proc is better for large graphs.

```
G.count(procs=4) # default is procs=0
G.count(get_curv=True) # vertex clique counts

# available results
G.ec
G.clique_counts

# with get_curv=True
G.vertex_clique_counts
G.curvatures
```

# Extras

## the academic lore...

> April 1971 
- Bron-Kerbosch algorithm created by... *C. Bron* and *J. Kerbosch*.
- [Algorithm 457, Finding All Cliques of an Undirected Graph [H]](https://dl.acm.org/doi/pdf/10.1145/362342.362367)

> October 2006
- *E. Tomitaa*, *A. Tanaka*, *H. Takahashia* say this is a difficult problem.
- [The worst-case time complexity for generating all maximal cliques
and computational experiments](https://snap.stanford.edu/class/cs224w-readings/tomita06cliques.pdf)


> Jun 2010, March 2011
- Double header by *D. Eppstein*, *M. Loffler*, *D. Strash*. ([code](https://github.com/darrenstrash/quick-cliques))
- [Listing All Maximal Cliques in Sparse Graphs in
Near-optimal Time](https://arxiv.org/pdf/1006.5440)
- [Listing All Maximal Cliques in
Large Sparse Real-World Graph](https://arxiv.org/pdf/1103.0318)
- *D. Strash* creates `quick-clicks` for maximal cliques. ([code](https://github.com/darrenstrash/quick-cliques))


> January 2020
- *S. Jain*, *C. Seshadhri* drop an absolute banger: `Pivoter`.
- [The Power of Pivoting for Exact Clique Counting](https://arxiv.org/abs/2001.06784)
- Code available on [GitHub](https://github.com/sjain12/Pivoter) and [BitBucket](https://bitbucket.org/sjain12/pivoter/src/)


## implementations
- Pivoter - Julia implementation by *charunupara*. ([code](https://github.com/charunupara/Pivoter))

- PyPivoter - Cython implementation by *rckormos*. ([code](https://github.com/rckormos/PyPivoter))

- **pivoterpy** - pure Python implementation with parallelization!




# todo
features
- make docs
- per edge clique counts
- get on PyPI
- max-clique size parameter

settings
- calculate ec, save clique counts?
- calculate curvs, save vertex clique counts?
- save edge clique counts?