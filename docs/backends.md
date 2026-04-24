# Backends

**pivoterpy** dispatches clique counting to one of two supported backends selected by `backend=` on [`pivoter`](api/solver.md): **`rust`** (default) or **`python`**.

---

## Rust (`backend="rust"`)

- **What it is:** A PyO3 extension module (`pivoter_rust`) built from the crate in this repository, using **Rayon** for parallelism when `procs > 1`.
- **When to use it:** Default choice for speed on non-trivial graphs; same resolutions as Python (global, vertex, edge).
- **Requirement:** A wheel or a local `maturin develop` / `maturin build` install so `import pivoter_rust` succeeds.

If the extension is missing, you will see an **ImportError** pointing at `pivoter_rust`. Fix by installing a wheel or building from source ([Installation](installation.md)).

Implementation notes (high level): degeneracy ordering, neighborhood representations tuned for the Rust code paths, and parallel work over the search structure as described in the upstream Pivoter line of work—not identical line-by-line to the Python kernel, but intended to match **counts** for the same graph and parameters.

---

## Python (`backend="python"`)

- **What it is:** Pure Python kernel: degeneracy ordering, Succinct Clique Tree (SCT), and optional **`multiprocessing`** when `procs > 1`.
- **When to use it:** No Rust toolchain, debugging, teaching, or double-checking results on small instances.
- **Tradeoff:** Much slower on large or dense graphs than Rust, but no compiled extension.

---

## Choosing a backend

| | Rust | Python |
|---|------|--------|
| **Speed** | Fast | Reference speed |
| **Setup** | Needs compiled module | `pip install` / source without Rust |
| **Parallelism** | Rayon (`procs`) | `multiprocessing` (`procs`) |
| **Resolutions** | global, vertex, edge | global, vertex, edge |

Outputs are meant to be **consistent** between backends for the same graph and resolution (up to the usual integer arithmetic and any `min_k` / `max_k` truncation rules).

---

## CUDA

The repository contains experimental **CUDA** wrapper code (`CUDAKernel` / `_cu_backend`), but the public **`pivoter`** constructor only accepts **`python`** and **`rust`**. There is no supported `backend="cuda"` in the current API. Treat CUDA-related modules as internal or future work.

---

## Troubleshooting

| Symptom | Things to check |
|--------|------------------|
| `ImportError` for `pivoter_rust` | Build or install the extension; or use `backend="python"`. |
| Rust path slower than expected | Try adjusting `procs`; ensure release build (`maturin develop --release`). |
| Python MP hangs or errors | Reduce `procs`; test with `procs=1`; check graph size and pickling cost. |
| Mismatch Rust vs Python on tiny graph | File a bug with graph + parameters; both backends should agree. |
