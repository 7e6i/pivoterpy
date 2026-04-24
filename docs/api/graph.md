# pivoterpy.graph

The `graph` module defines the `Graph` type used by [`pivoter`](solver.md). All public constructors are also exposed on the package as `pvt.from_edge_list`, `pvt.from_adj_matrix`, and `pvt.from_networkx`.

---

## `Graph`

Represents an undirected simple graph: internal vertex IDs are contiguous `0 .. n-1`, with an optional map back to original labels.

### Attributes

| Name | Type | Description |
|------|------|-------------|
| `edges` | `list[tuple[int, int]]` | Undirected edges as `(u, v)` with `u < v`, internal IDs |
| `n` | `int` | Number of vertices |
| `m` | `int` | Number of edges |
| `degrees` | `list[int]` | Degree per internal vertex ID |
| `nodes` | `list[int]` | `nodes[i]` is the original label for internal vertex `i` |
| `experimental` | — | Reserved (`None` after construction); not used by current backends |

### Constructor (`__init__`)

Normally you should use a classmethod below. The direct constructor builds a graph from already-normalized data:

```python
from pivoterpy.graph import Graph

edges = [(0, 1), (1, 2)]
G = Graph(edges=edges, n=3, nodes=[10, 20, 30])  # optional node id map
```

- `edges`: internal `(u, v)` pairs, `u < v`, each edge once.
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

Raises if no valid edges remain after filtering.

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
