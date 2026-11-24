# pivoterpy.graph

The `graph` module defines the `Graph` type used by [`pivoter`](solver.md). All public constructors are also exposed on the package as `pvt.from_edge_list`, `pvt.from_edge_file`, `pvt.from_adj_matrix`, and `pvt.from_networkx`.

---

## `Graph`

Represents an undirected simple graph: internal vertex IDs are contiguous `0 .. n-1`, with an optional map back to original labels.

Edges are stored in a flat native-endian `uint32` buffer (a `bytes` object, two `uint32` values per edge), so memory is `8 * m` bytes rather than one Python object per edge. On a 117M-edge graph that is roughly 0.9 GB instead of ~7.5 GB. Because it is a `bytes` object, the Rust backend borrows it directly with no copy on the way in.

### Attributes

| Name | Type | Description |
|------|------|-------------|
| `edges` | `Sequence[tuple[int, int]]` | Lazy view over the internal edges as `(u, v)` with `u < v`. Supports `len`, iteration, indexing, slicing, and set comparison; it is **not** a `list` |
| `n` | `int` | Number of vertices |
| `m` | `int` | Number of edges |
| `degrees` | `list[int]` | Degree per internal vertex ID |
| `nodes` | `list[int]` | `nodes[i]` is the original label for internal vertex `i` |
| `experimental` | — | Reserved (`None` after construction); not used by current backends |

Use `list(G.edges)` or `G.edge_bytes()` when you explicitly need a materialized form. `G.edge_bytes()` returns the native-endian flat buffer, which the Rust backend consumes without copying.

### Constructor (`__init__`)

Normally you should use a classmethod below. The direct constructor builds a graph from already-normalized data:

```python
from pivoterpy.graph import Graph

edges = [(0, 1), (1, 2)]
G = Graph(edges=edges, n=3, nodes=[10, 20, 30])  # optional node id map
```

- `edges`: internal `(u, v)` pairs, `u < v`, each edge once. May also be an existing flat `array('I')` buffer (`u0, v0, u1, v1, ...`).
- `n`: vertex count (must cover all indices appearing in `edges`).
- `nodes`: length `n`; defaults to `[0, 1, ..., n-1]` if omitted.

---

## `from_edge_list`

```python
Graph.from_edge_list(array: list[tuple[int, int]]) -> Graph
```

Builds a graph from arbitrary integer vertex labels. Labels are compressed to `0 .. n-1`, duplicates and self-loops are dropped, and `nodes` records the inverse map.

```python
import pivoterpy as pvt

G = pvt.from_edge_list([(0, 1), (1, 2), (5, 0)])
```

Raises if no valid edges remain after filtering. Duplicate removal uses NumPy `unique` when NumPy is installed, and a compact `set` of 64-bit keys otherwise.

```python
G = pvt.from_edge_list([(0, 1), (1, 2), (5, 0)], deduplicate=False)
```

Pass `deduplicate=False` when the input is already simple (or when you would rather deduplicate later) to skip the extra pass.

---

## `from_edge_file`

```python
Graph.from_edge_file(
    path,
    comments: str = "#",
    delimiter: str | None = None,
    deduplicate: bool = False,
) -> Graph
```

Streams a whitespace-delimited edge list from disk directly into the compact buffer. This is the recommended entry point for large graphs: it never builds a list of Python tuples.

- `.gz` paths are decompressed transparently.
- Lines starting with `comments` are skipped, as are blank or short lines and self-loops.
- `delimiter` defaults to arbitrary whitespace; pass e.g. `","` for CSV.
- `deduplicate` defaults to `False` because SNAP-style `*ungraph` files are already simple.

```python
import pivoterpy as pvt

G = pvt.from_edge_file("stress/data/com-orkut.ungraph.txt.gz")
```

---

## `from_adj_matrix`

```python
Graph.from_adj_matrix(array: Sequence[Sequence[int | float | bool]]) -> Graph
```

Expects a square matrix. Only the **strict upper triangle** is read; an edge `(i, j)` is added when `array[i][j] > 0` (so `True` counts as an edge). Diagonal and lower triangle are ignored.

```python
import pivoterpy as pvt

matrix = [
    [0, 1, 0],
    [0, 0, 1],
    [0, 0, 0],
]
G = pvt.from_adj_matrix(matrix)
```

Vertex `i` in the matrix stays internal vertex `i` (no relabeling).

---

## `from_networkx`

```python
Graph.from_networkx(G: object) -> Graph
```

Imports `G.edges()` and uses `G.number_of_nodes()` as `n`. This matches graphs whose nodes are already integers `0 .. n-1` (for example `nx.path_graph(5)`).

If your graph uses arbitrary labels (strings, non-contiguous integers, etc.), prefer relabeling first or use `from_edge_list(list(your_graph.edges()))`, which applies the same compression as the edge-list path.

```python
import networkx as nx
import pivoterpy as pvt

Gnx = nx.complete_graph(4)
G = pvt.from_networkx(Gnx)
```

NetworkX is not a hard dependency of the core package; install it when you need this constructor.
