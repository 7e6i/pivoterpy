# pivoterpy.solver

The solver runs the Pivoter algorithm on a [`Graph`](graph.md) instance and exposes clique counts (and derived quantities) at the requested resolution.

---

## `pivoter`

Stateful object constructed with a graph and options; counting runs immediately in `__init__` (there is no separate `.run()` call from user code).

```python
import pivoterpy as pvt

G = pvt.from_edge_list([(0, 1), (1, 2), (2, 0)])
P = pvt.pivoter(
    G,
    resolution="global",
    backend="rust",
    procs=1,
    min_k=None,
    max_k=None,
)
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `graph` | (required) | A `pivoterpy.graph.Graph` instance. |
| `resolution` | `"global"` | `"global"` / `"g"`, `"vertex"` / `"v"`, or `"edge"` / `"e"` (case-insensitive). Finer resolutions can derive coarser ones (e.g. edge → vertex → global) without a second run. |
| `backend` | `"rust"` | `"rust"` / `"r"` or `"python"` / `"p"`. Rust requires the compiled `pivoter_rust` extension. |
| `procs` | `1` | Parallelism: Python uses a process pool over level-1 SCT branches when `procs > 1`; Rust uses Rayon with the given thread count. |
| `min_k` | `None` | If set, cliques with `k < min_k` are zeroed out in the stored arrays. Must satisfy `0 <= min_k <= n`. |
| `max_k` | `None` | If set, counts are truncated so only `k <= max_k` are retained. Must satisfy `0 <= max_k <= n` and `min_k <= max_k` when both set. |

Internal counting effectively starts at **k = 3** for nontrivial Pivoter work; entries for `k in {0,1,2}` are filled with graph statistics (`_cleanup`). If the graph has no edges large enough to support cliques above 2, raw counting may be skipped and trivial counts still apply.

### Errors

Invalid arguments raise `AssertionError` with a short message. Unexpected backend failures print a message and call `sys.exit(1)`; `KeyboardInterrupt` is allowed to propagate after a short message.

### Properties (results)

Availability depends on `resolution`:

| Property | Global | Vertex | Edge | Description |
|----------|--------|--------|------|-------------|
| `global_counts` | yes | yes | yes | `list[int]`: index `k` = number of `k`-cliques in `G`. |
| `global_ec` | yes | yes | yes | `int \| None`: alternating sum \(\sum_{k \ge 1} (-1)^{k+1} C_k\) over global counts. |
| `vertex_counts` | — | yes | yes | `dict[int, list[int]]`: original vertex id → counts per `k`. |
| `vertex_ec` | — | yes | yes | `dict[int, int]`: local Euler characteristic per vertex. |
| `curvatures` | — | yes | yes | `dict[int, float]`: Levitt / combinatorial curvature per vertex. |
| `edge_counts` | — | — | yes | `dict[tuple[int,int], list[int]]`: undirected edge `(u,v)` with `u < v` in **original** ids → counts per `k`. |

When a property is not meaningful for the chosen resolution, the underlying field may be `None` (for example `vertex_counts` on pure `global` runs).

> **Note:** If you set `min_k` or `max_k`, Euler characteristics and curvatures are still computed from the truncated lists and may not match the values for the full clique complex.

### Example: vertex resolution

```python
import pivoterpy as pvt

G = pvt.from_edge_list([(0, 1), (1, 2), (2, 0)])
P = pvt.pivoter(G, resolution="vertex", backend="python")
assert P.global_counts is not None
assert 0 in P.vertex_counts
print(P.curvatures)
```

### Example: restricting clique sizes

```python
P = pvt.pivoter(G, min_k=3, max_k=5)
# Only k = 3,4,5 nontrivial clique counts are trusted; smaller k may be zeroed.
```
