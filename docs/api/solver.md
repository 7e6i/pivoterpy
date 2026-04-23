# pivoterpy.solver

The `solver` module contains the primary engine for clique counting and topological analysis. 

---

## `pivoter` (Class)

The main stateful solver for clique counting. It takes a pre-processed `Graph` object, dispatches the workload to the specified backend (Python or Rust), and stores the resulting topological data.

```python
from pivoterpy import pivoter

P = pivoter(
    graph, 
    resolution="global", 
    backend="rust", 
    procs=4
)