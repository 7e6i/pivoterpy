# pivoterpy

> *"I fear not the man who has implemented 1000 clique counting algorithms, I fear the man who has implemented 1 clique counting algorithm a thousand times" - Sun Tzu, The Art of War*

**pivoterpy** — exact clique counting in Python and Rust, powered by the Pivoter algorithm ([Jain & Seshadhri, 2020](https://arxiv.org/abs/2001.06784)). You get a small Python API: build a graph, run `pivoter`, read counts at **global**, **vertex**, or **edge** resolution. Work is done by a **Rust** extension by default, with a pure **Python** backend when you need it.

**Repo:** [github.com/7e6i/pivoterpy](https://github.com/7e6i/pivoterpy) · **Documentation:** [7e6i.github.io/pivoterpy](https://7e6i.github.io/pivoterpy/)

---

## Install

```bash
pip install pivoterpy
```

From source (needs [Rust](https://www.rust-lang.org/) + [Maturin](https://www.maturin.rs/)): clone the repo, then `maturin develop --release` in the project root. More detail: [Installation](https://7e6i.github.io/pivoterpy/installation/).

---

## Quick start

```python
import pivoterpy as pvt

G = pvt.from_edge_list([(0, 1), (1, 2), (2, 0)])
P = pvt.pivoter(G)  # default: resolution="global", backend="rust"

# P.global_counts[k] == number of k-cliques
print(P.global_counts)
```

Use `resolution="vertex"` or `"edge"` for local counts; `backend="python"` if the Rust wheel is not available. See [Usage](https://7e6i.github.io/pivoterpy/usage/).

---

## Citation

Always cite the original **Pivoter** paper: [arXiv:2001.06784](https://arxiv.org/abs/2001.06784).

BibTeX for this package:

```bibtex
@software{anderson_pivoterpy_2026,
  author       = {Spencer Anderson},
  title        = {{pivoterpy}},
  year         = {2026},
  version      = {2.1.1},
  url          = {https://github.com/7e6i/pivoterpy}
}
```
