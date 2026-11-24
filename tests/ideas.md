# Performance ideas: widening the Rust accumulator

Context: `BigUint` is used for clique **counts**, not node IDs. Node indices are
already `usize` throughout the Rust backend, so this is not about graph size.

Where `BigUint` is used today:

- `src/cpu/utils.rs:33` — `precompute_ncr` returns `Vec<Vec<BigUint>>`.
- `src/cpu/core.rs` — all accumulators and worker/reduce maps:
  - global: `Vec<BigUint>` (`core.rs:56, 82-88, 131, 154`)
  - vertex/edge: `HashMap<_, Vec<BigUint>>` (`core.rs:285-299, 372-382, 512-529, 607-630`)
  - exported return types.

## Why `BigUint` can't just be replaced

Counts grow combinatorially with vertex count, not with ID magnitude:

- `K_70` has `C(70,35) ~ 1.1e20` 35-cliques, already over `u64::MAX` (~1.8e19).
- `K_128` has `C(128,64) ~ 2.4e37`, just under `u128::MAX` (~3.4e38).
- Denser/larger graphs (or summing `global_counts` across `k`) exceed `u128`.

A `u32` overflow is easy even for triangles: `K_65600` alone exceeds 4.3e9.
So a blanket `u64`/`u32` switch silently corrupts results on exactly the dense
graphs used to stress a clique counter.

## Where BigUint cost comes from

- `BigUint` is heap-backed (`Vec<u32>`) even for small values, so every
  `target[k] += ncr_0` in the leaf loops can allocate.
- The per-thread `HashMap<K, Vec<BigUint>>` merges churn many small allocations,
  especially for `vertex`/`edge` resolution.
- Expected impact: likely real for vertex/edge, smaller for global where bitset
  pivoting dominates. **Profile before refactoring** — don't trust intuition.

## Candidate changes (in priority order)

### 1. Width-adaptive fast path (main idea)

Keep exactness but avoid big-int arithmetic on ordinary graphs:

1. **Per-root bound check (cheap).** For a root with `c = num_cands`, the
   worst-case contribution is bounded by
   `sum_{i=0}^{min(c, max_k - 1)} C(c, i)` (the complete-graph case).
   Compute with saturating `u128`, early-exiting once it passes `u64::MAX`.
   O(`max_k`) per root, negligible.
2. **Dispatch per root.** Roots are already independent Rayon tasks
   (`core.rs:48-80`). Run `branch_*` with `u64` counters when the bound fits,
   fall back to `BigUint` only for roots that overflow.
3. **Factor the branch code over a count type.** A small trait
   (`zero`, `checked_add` / `add_assign`) with `u64` and `BigUint` impls, or a
   macro, so `branch_global` / `branch_vertex` / `branch_edge` aren't triplicated.
   `u64` converts to Python `int` natively via PyO3.
4. **Alternative if dispatch is too complex:** accumulate in `u64` with
   `checked_add` and a per-root overflow flag; recompute only overflowing roots
   with `BigUint`. Simpler, rare double work, still exact. The bound check above
   avoids even that.

### 2. Flatten the NCR table

`Vec<Vec<BigUint>>` → a flat `Vec<...>` (or `Vec<Box<[BigUint]>>`) for cache
locality; consider `u64` cells below the overflow threshold and `BigUint` above.

### 3. `u32` node indices (separate, memory-focused)

Real graphs won't exceed `u32` vertices, but this buys memory, not much speed,
and fights `FixedBitSet`'s `usize` API with conversions. Could help cache
behavior on huge-edge-count graphs (`compressed_nbhds` is `Vec<Vec<usize>>`,
duplicated into the degen variant). Treat as a memory optimization, not a
replacement for the big-int work.

## What NOT to change: the ID mappings

Three distinct mappings exist; none forces `BigUint`:

1. **Original labels → `0..n-1`** — Python (`Graph.from_edge_list`,
   `graph.py:81-109`). Rust never sees arbitrary labels.
2. **Internal IDs → compressed valid roots** — Rust `setup_graph`
   (`utils.rs:181-214`); prunes vertices whose core can't support `min_k` and
   reindexes survivors so bitsets stay dense. This is a performance
   optimization, not an ID-normalization requirement. Moving it to Python would
   pass larger bitsets / re-add the filter cost. Leave it.
3. **Internal IDs → original labels on output** — Rust `valid_roots`
   (`core.rs:324, 551-552`) then Python `_remapping` (`solver.py:259-287`).

## Suggested sequence

1. Benchmark current code: `K_30`–`K_60`, Karate, a sparse real graph, and a
   dense random `G(n, 0.3)`, at `procs=1` and `procs=N`, global vs edge.
2. `perf` / flamegraph to quantify leaf/reduce BigUint work vs bitset pivoting.
   (`setup_graph` already has commented-out timers in `utils.rs`.)
3. If significant, implement the per-root `u64`-with-`BigUint`-fallback path and
   re-benchmark.
4. Verify against the Python backend and the existing suite on dense graphs so
   the fallback path is actually exercised.
5. Leave ID mappings alone unless a memory profile says otherwise.
