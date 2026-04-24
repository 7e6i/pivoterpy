# pivoterpy

Exact clique counting in Python and Rust, powered by the Pivoter algorithm. One Python API, two backends (**Rust** and pure **Python**), global / vertex / edge resolutions, and optional parallelism.

[Install](installation.md) · [Usage](usage.md) · [Backends](backends.md) · [Algorithm](algorithm.md) · [Changelog](changelog.md) · API: [`Graph`](api/graph.md) · [`pivoter`](api/solver.md)

---

## Quick start

```python
import pivoterpy as pvt

G = pvt.from_edge_list([(0, 1), (1, 2), (2, 0)])
P = pvt.pivoter(G)
print(P.global_counts)
```

`global_counts[k]` is the number of $k$-cliques in $G$ (see [Usage](usage.md) for vertex/edge resolution and tuning).

---

## Why this exists

Pivoter ([Jain & Seshadhri, 2020](https://arxiv.org/abs/2001.06784)) counts cliques without enumerating every maximal clique. **pivoterpy** wraps a Rust implementation (default) and a Python reference backend for the same workflow. Background reading and citations live on the [Algorithm](algorithm.md) page.

---

## Project links

- **Source:** [github.com/7e6i/pivoterpy](https://github.com/7e6i/pivoterpy)
- **Upstream reference implementation:** [github.com/sjain12/Pivoter](https://github.com/sjain12/Pivoter)
