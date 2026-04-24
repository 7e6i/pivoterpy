# Changelog

All notable changes to **pivoterpy** are summarized here. Release versions follow `Cargo.toml` / package metadata where applicable.

---

## 2.1.1

### Fixed

- Forgot to mute my timing println statements in the Rust backend. Might add them as a feature in a future release.

## 2.1.0

### Changed

- **Graph API:** `from_edge_list()` infers the number of vertices from **unique** endpoints; vertex IDs are mapped to a contiguous internal range `0 .. n-1` with the original labels preserved on the `Graph` object.
- **`vertex_counts`:** Now a **`dict[int, list[int]]`** keyed by the **original** node id (after any compression), not a nested list indexed only by internal ids.

### Rust backend

- Neighborhood representation moved from bitsets to a **neighbor list** layout suited to the current kernels.
- Global counting: level-1 recursion uses a **compressed bitset** where applicable.
- **Degeneracy:** Matula–Beck ordering replaced by **Batagelj–Završnik** degeneracy processing.
- **Parallelism:** Order of parallel work for global/vertex passes was revised.
- **Combinatorics:** Precomputed **Pascal’s triangle** for binomial-style work in the pipeline.

### Removed

- **Experimental Rust global backend** (the alternate global path toggled via graph flags) was removed in favor of a single supported Rust pipeline.

### Python

- **Unified entry points** for calling backends from the solver layer.
- **Rust backend** module refactor for clearer FFI boundaries.

### Tests

- Expanded **test suite** for graph constructors and global / vertex / edge counts.

---

## Earlier history

For older development notes not yet folded into this changelog, see [`changes.md` in the repository](https://github.com/7e6i/pivoterpy/blob/main/changes.md).
