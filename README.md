# pivoterpy
Parallelized Python implementation of the `Pivoter` clique counting algorithm.

Based on <u>The Power of Pivoting for Exact Clique Counting</u> by *S. Jain*, *C. Seshadhri*.

## quick start

```
# pip install pivoterpy

import pivoterpy as piv

G = piv.from_adj_matrix(array)

G.count()

G.global_counts
```



# Documentation

## usage
Requires a N x N binary matrix. Only upper triangle is used.

Edges are created for entries > 0 (or True).

```
G = Pivoter.from_adj_matrix(array)
```

Requires a M x 2 edge matrix and the positive integer number of nodes $n$.

Note: all elements must be non-negative tuples $(u,v)$. $n$ defaults to the largest $u+1$.
```
G = Pivoter.from_edge_list(array, n)
```


Values available after construction.
```
G.neighborhoods
G.degrees
G.by_degrees
G.degeneracy
G.node_by_degen_order
G.degen_order_by_node
G.degen_order_nbhds
```

## counting

Multiprocessing is generally only beneficial for especially large or dense graphs.

```
G.count(procs=4) # default is 0 (avoids mp.Pool)
G.count(vertex=True) # finds vertex counts
G.count(edge=True) # finds edge counts
G.count(rust=True) # uses Rust backend
```

Results available after completion:
```
G.max_k         # max clique size
G.global_ec     (alternating sum of counts)
G.global_counts
```

if `vertex` is True:
```
G.vertex_ec   # also G.curvatures
G.vertex_counts
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

- **pivoterpy** - parallelized pure Python implementation!