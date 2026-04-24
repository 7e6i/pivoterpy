# Usage

This page covers graph construction, running the solver, tuning parameters, and practical caveats. For install steps see [Installation](installation.md). For execution engines see [Backends](backends.md).

---

## Graph constructors

```python
import pivoterpy as pvt

G = pvt.from_adj_matrix(matrix)   # square; upper triangle only, edge if entry > 0
G = pvt.from_edge_list(edges)     # list of (u,v); labels relabeled to 0..n-1
G = pvt.from_networkx(nx_graph)   # best when nodes are 0..n-1; see API for other cases
```

Details: [`Graph` API](api/graph.md).

---

## Running the solver

```python
P = pvt.pivoter(
    G,
    resolution="global",
    backend="rust",
    procs=1,
    min_k=None,
    max_k=None,
)
```

Counting runs inside the constructor; there is no separate `.run()` call. Full parameter reference: [`pivoter` API](api/solver.md).

### `resolution`

One of `global` / `g`, `vertex` / `v`, or `edge` / `e` (case-insensitive).

- **Global** — one list: total number of $k$-cliques for each $k$.
- **Vertex** — per-vertex counts (and derived global totals).
- **Edge** — per-edge counts (and derived vertex + global).

Finer resolutions cost more work. The implementation can derive coarser summaries from finer ones (for example edge → vertex → global) in a single run, so pick the **coarsest** resolution that answers your question.

### `backend`

`rust` (default) or `python`. Same algorithmic outputs; performance differs. See [Backends](backends.md).

### `procs`

Parallelism:

- **Python:** `procs > 1` uses a process pool over level-1 branches of the Succinct Clique Tree (SCT); `procs == 1` skips the pool entirely.
- **Rust:** forwarded as the Rayon thread count for the Rust kernel.

Very large `procs` is not always faster (overhead and memory). Start near your CPU core count and adjust.

### `min_k` and `max_k`

Optional bounds on clique size $k$ (integers in `[0, n]`; if both are set, require `min_k <= max_k`).

- Counts for $k < \text{min_k}$ are zeroed.
- Arrays are truncated so you only keep $k \leq \text{max_k}$.

**Important:** Euler characteristics (`global_ec`, `vertex_ec`) and **curvatures** are computed from whatever lists remain. If you truncate with `min_k` / `max_k`, those derived quantities are **not** guaranteed to match the full clique complex.

---

## Results by resolution

With **`edge`** you get `edge_counts`, `vertex_counts`, `global_counts`, and global/vertex EC where applicable.

With **`vertex`** you get `vertex_counts` (dict: original vertex id → list indexed by $k$), `vertex_ec`, `curvatures`, and `global_counts` / `global_ec`.

With **`global`** you get `global_counts` and `global_ec`.

Keys for edges are `(u, v)` with `u < v` in **original** vertex ids after any relabeling from `from_edge_list`.

---

## Interrupts and errors

The Python backend configures worker processes to ignore `SIGINT` so the main process can catch **Ctrl+C** cleanly. Other failures may print a message and exit the process from inside the solver wrapper; see [Backends](backends.md) if the Rust extension fails to import.

---

## Multiprocessing notes

Using **`backend="python"`** with **`procs > 1`** forks worker processes. On some platforms, pickling large graphs adds overhead; if debugging, use `procs=1` first.

---

## When counts look wrong

- Confirm the graph you intended: especially **adjacency** (upper triangle only) and **NetworkX** node labels (see [Graph API](api/graph.md#from_networkx)).
- If you use **`min_k` / `max_k`**, remember partial lists and derived topology metrics.
- Compare **Python** vs **Rust** on a small graph to rule out input issues.
