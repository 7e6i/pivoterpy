# pivoterpy.graph

The `graph` module contains the `Graph` class which serves as the data structure to hold and process network topologies for the `pivoter` solver.

---

## `Graph` (Class)

The `Graph` class represents the graph data structure and provides several constructors for initializing from common formats. It automatically translates node IDs into an internal contiguous space, calculates node degrees, and tracks total edges and vertices.

### Attributes

- `edges` (`list[tuple[int, int]]`): The internal edge list representation.
- `n` (`int`): The number of unique nodes in the graph.
- `m` (`int`): The number of edges in the graph.
- `degrees` (`list[int]`): A list of vertex degrees, mapped to internal node IDs.
- `nodes` (`list[int]`): A mapping of internal node IDs back to their original IDs.

### Constructors

#### `from_edge_list`

Creates a `Graph` from a list of `(u, v)` edge tuples. Compresses non-contiguous vertex IDs into a contiguous `0` to `N-1` internal space, ignoring self-loops and duplicate edges.

```python
import pivoterpy as pvt

edges = [(0, 1), (1, 2), (2, 0)]
G = pvt.from_edge_list(edges)
```

#### `from_adj_matrix`

Creates a `Graph` from the upper triangle of a square adjacency matrix. Edges are inferred from entries greater than `0`.

```python
import pivoterpy as pvt

matrix = [,,]
G = pvt.from_adj_matrix(matrix)
```

#### `from_networkx`

Creates a `Graph` from an existing NetworkX graph object.

```python
import networkx as nx
import pivoterpy as pvt

nx_graph = nx.complete_graph(3)
G = pvt.from_networkx(nx_graph)
```