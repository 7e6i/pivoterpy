# Getting started

## Requirements

- **Python** 3.8 or newer
- **Rust toolchain** (stable), only if you build the extension from source. Pre-built wheels include the compiled backend.

Optional:

- **NetworkX** if you use `pvt.from_networkx`
- **NumPy** if you build graphs from `ndarray` adjacency matrices (anything that indexes like a square matrix works)

## Install from PyPI

When [releases](https://github.com/7e6i/pivoterpy/releases) are published, wheels are built for Linux, Windows, and macOS:

```bash
pip install pivoterpy
```

## Install from source

Clone the repository, then build and install the PyO3 extension with [Maturin](https://www.maturin.rs/):

```bash
cd pivoterpy
pip install maturin
maturin develop --release
```

That installs the package in editable mode with the Rust extension (`pivoter_rust`) linked for your current virtual environment.

To produce wheels without installing:

```bash
maturin build --release --out dist
```

## Python-only backend

If you cannot build or import the Rust extension, you can still run clique counting with the pure Python implementation:

```python
import pivoterpy as pvt

G = pvt.from_edge_list([(0, 1), (1, 2), (2, 0)])
P = pvt.pivoter(G, backend="python")
```

The Rust backend is the default when the extension is available (`backend="rust"`).

## Development dependencies

For tests, docs site ([Zensical](https://zensical.org/)), and local packaging:

```bash
pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest
```

## Quick start

```python
import pivoterpy as pvt

G = pvt.from_adj_matrix(
    [
        [0, 1, 1],
        [1, 0, 1],
        [1, 1, 0],
    ]
)

P = pvt.pivoter(G)
print(P.global_counts)  # counts of k-cliques by k
```

See [Usage](usage.md) for resolution options (`global` / `vertex` / `edge`), multiprocessing, and result fields.
