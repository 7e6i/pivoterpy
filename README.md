# pivoterpy
A one-stop-shop for all your clique counting needs. Python, Rust (and hopefully CUDA soon) implementations of the `Pivoter` clique counting algorithm.


> *"I fear not the man who has implemented 1000 clique algorithms, I fear the man who has implemented 1 clique algorithm a thousand times" - Sun Tzu, The Art of War*

Let $G=(V,E)$ be a graph with $|V|=n$ nodes and $|E|=m$ edges. Let $C_k$ be the number of global cliques of size $k$. Let $C_k(v)$ and $C_k(e)$ be the number of vertex and edge cliques of size $k$ for vertex $v$ and edge $e$, respectively. Let $\mathcal{K}$ be the size of the largest clique in the graph.


## quick start

```
import pivoterpy as pvt

G = pvt.from_adj_matrix(array)

P = pvt.pivoter(G)

P.global_counts
```



# Documentation

## initialization

Use the following constructors to load a graph.

```
G = pvt.from_adj_matrix(array)
```

- Requires a $n \times n$ binary matrix. Only the upper triangle is scanned.

- Edges are created for entries > 0 (or True).

```
G = pvt.from_edge_list(array, n=None)
```

- Requires a $m \times 2$ edge list.

- All elements must be integer edge tuples $(u,v)$ such that $0 \le u,v < n$.

- Number of nodes $n$ is inferred from the largest node provided. Used the argument `n` to set a larger value.

```
G = pvt.from_networkx(graph)
```

- Requires a NetworkX graph object.
 

## counting

To get started, create simply call the `pivoter` method with a graph. Default arguments are shown for reference.
```
P = pvt.pivoter(
    G, 
    resolution='global', 
    backend='python', 
    procs=1, 
    min_k=None, 
    max_k=None
)
```
## arguments
`resolution`
- one of `g[lobal]`, `v[ertex]`, or `e[dge]`.
- because of how math works, global counts can be derived from vertex counts
- the same applies to vertex from edge counts (and thus global from edge counts)
- increasing the reslution does change the complexity class so be careful

`backend`
- one of `p[ython]` or `r[ust]`
- multiprocessing and all resolutions are implemented for both backends

`procs`
- as many as you are willing to sacrifice for speed.
- if `procs=0` and `backend='python'` then `mp.Pool` is skipped entirely
 
`min_k`
- only cliques of size $k \geq min_k$ will be counted
- all counts with $k < min_k$ will be set to 0
- the length of all counts list will be at least $min_k+1$

`max_k`
- only cliques of size $k \leq max_k$ will be counted

> Note: If `min_k` or `max_k` are set, `P.vertex_ec`, `P.curvatures`, and `P.global_ec` will be still return values, although they will likely be incorrect.


## results

With `resolution='edge'` the below are available (including `vertex` and `global` results).
```
P.edge_counts   # dict of lists, keys are (u,v) with u < v
```
With `resolution='vertex'` the below are available (including `global` results).
```
P.vertex_counts # jagged list of lists of ints
P.vertex_ec     # list of ints, alternating sum of counts
P.curvatures    # list of floats
```

With `resolution='global'` the below are available.
```
P.global_counts # list of ints
P.global_ec     # int, alternating sum of counts
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

- **pivoterpy** - a new and improved Python/Rust implementation!


## citation
Below is the preferred BibTeX citation for this repository.

```
@software{anderson_pivoterpy_2026,
  author       = {Spencer Anderson},
  title        = {{pivoterpy}},
  year         = {2026},
  version      = {2.0.0},
  url          = {https://github.com/7e6i/pivoterpy}
}
```


## experimental

There is an experimental Rust backend available for `resolution='global'`. To access it, set `G.experimental=True` before calling `pivoter`.

This code parallelizes work for each level 2 node in the SCT (rather than only level 1), and compresses the neighborhoods and degeneracy out neighborhoods for each node. This helps to reduce memory overhead taken up by unused vertices for each recursion path, and helps to balance the load by allowing for improved Rayon work-stealing.