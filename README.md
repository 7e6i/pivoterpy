# pivoterpy
Parallelized pure Python implementation of the `Pivoter` clique counting algorithm.

Based on <u>The Power of Pivoting for Exact Clique Counting</u> by *S. Jain*, *C. Seshadhri*.

>*The fasest clique counter this side of the Mississippi. - Sun Tzu*

## quick start

```
# pip install pivoterpy

from pivoterpy import Pivoter

G = Pivoter.from_adj_matrix(array)

G.count()

G.clique_counts
```

## benchmarks
- **CPU**: AMD Ryzen 5 3600, **RAM**: 32GB DDR4-3200MHz CL16
- Tested on complete graphs with n nodes.
- All times shown are the average of 10 runs (in **seconds**).
- Setup refers to initialization time (nbhds, degen. ordering, etc)

---

|   n   | setup | no mp | 4 procs | 8 procs |
| ----- | ----- | ----- | ------- | ------- |
| 300   | 0.02  |       |         |         |
| 600   | 0.09  | 0:04  |         |         |
| 900   | 0.22  | 0:13  | 0:04    |         |
| 1200  | 0.36  |       | 0:11    | 0:11    |
| 1500  | 0.69  |       |         | 0:22    |


# Documentation

## usage
Requires a N x N adjacency matrix. Only upper triangle is used.

Edges are created for entries > 0 (or True).

```
G = Pivoter.from_adj_matrix(array)
```

Requies a M x 2 edge matrix and the positive integer number of nodes $n$.

Note: all elements must be $(u,v)$ with $u,v\in\mathbb{Z}$ and $0\le u < v < n$.
```
G = Pivoter.from_edge_list(array, n)
```


Values available after construction.
```
G.neighborhoods         # list of sets
G.degrees               # list of ints
G.by_degrees            # list of sets
G.degeneracy            # int
G.node_by_degen_order   # list of ints
G.degen_order_by_node   # list of ints
G.degen_order_nbhds     # list of sets
```

## counting

Multiprocessing is generally only beneficial for especially large or dense graphs.

```
G.count(procs=4) # default is procs=0 (avoids mp.Pool)
G.count(get_curv=True) # default is get_curv=False
```

Results available after completion.
```
G.max_k         # max clique size
G.global_ec     # G.ec
G.global_counts # G.clique_counts
```

With `get_curv` set to `True`.
```
G.vertex_curv   # G.curvatures
G.vertex_counts # G.vertex_clique_counts
```

# Extras

## the lore...

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