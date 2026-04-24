# Algorithm and references

## Pivoter

**Pivoter** is an exact clique counting algorithm due to **Shweta Jain** and **C. Seshadhri**, described in:

- [*The Power of Pivoting for Exact Clique Counting*](https://arxiv.org/abs/2001.06784) (January 2020).

It avoids listing every maximal clique by organizing computation around a **Succinct Clique Tree (SCT)** and pivoting ideas adapted from classical clique enumeration, with degeneracy-based structure exploited for sparse graphs.

Reference code from the authors:

- [GitHub — sjain12/Pivoter](https://github.com/sjain12/Pivoter)
- [Bitbucket mirror](https://bitbucket.org/sjain12/pivoter/src/)

**pivoterpy** reimplements that workflow with a Python kernel and a Rust extension; it is not a line-for-line port of the authors’ Julia/C code, but follows the same family of ideas.

---

## Degeneracy ordering

**pivoterpy** uses a **degeneracy ordering** of vertices (Batagelj–Završnik style in the current Rust pipeline) as part of the search structure. That choice affects performance and recursion shape, not the final counts for a fixed simple graph.

---

## Related work (short timeline)

These are classic touchpoints in **maximal clique listing** and **clique counting**; Pivoter sits in the “exact counting with careful pivoting / structure” line.

**April 1971 — Bron–Kerbosch**

- *C. Bron* and *J. Kerbosch* — foundational backtracking for cliques.
- [ACM Algorithm 457 (PDF)](https://dl.acm.org/doi/pdf/10.1145/362342.362367)

**October 2006 — Tomita et al.**

- Worst-case analysis and experiments on maximal clique generation.
- [Paper (Stanford CS224W readings)](https://snap.stanford.edu/class/cs224w-readings/tomita06cliques.pdf)

**2010–2011 — Eppstein, Löffler, Strash**

- Near-optimal listing in sparse graphs and large sparse instances.
- [arXiv:1006.5440](https://arxiv.org/pdf/1006.5440) · [arXiv:1103.0318](https://arxiv.org/pdf/1103.0318)
- Practical code: [quick-cliques](https://github.com/darrenstrash/quick-cliques)

---

## Other Pivoter implementations

- **Pivoter** (Julia) — [charunupara/Pivoter](https://github.com/charunupara/Pivoter)
- **PyPivoter** (Cython) — [rckormos/PyPivoter](https://github.com/rckormos/PyPivoter)
- **pivoterpy** (this project) — Python + Rust

---

## Citation

Cite the **original Pivoter paper** for the algorithm.

If you also want to cite this package:

```bibtex
@software{anderson_pivoterpy_2026,
  author       = {Spencer Anderson},
  title        = {{pivoterpy}},
  year         = {2026},
  version      = {2.1.1},
  url          = {https://github.com/7e6i/pivoterpy}
}
```
