# Performance, memory, and GPU ideas

Written against the post-P0 code (commit `4427768`). Items that have already
landed are summarized once under [Already landed](#already-landed) and should
not be re-proposed; everything else is open work.

Measurements below are global counts, `min_k=3, max_k=3`, Rust backend, `procs=4`,
on this machine unless noted. Triangle totals were checked against SNAP.

| Graph | Edges | Peak RSS | Solve |
|---|---:|---:|---:|
| `com-dblp` | 1.05M | 90 MB | 0.17 s |
| `as-skitter` | 11.1M | 500 MB | 39 s |
| `com-lj` | 34.7M | 1.58 GB | 34 s |
| `com-orkut` | 117M | 2.76 GB | 188 s |
| `com-friendster` | 1.8B | untested | untested |

The current pain is **not memory** anymore. `com-lj` with default `min_k=None,
max_k=None` (all clique sizes) ran 40+ minutes without finishing and without any
output explaining which stage it was in. That motivates sections 1 and 2.

---

## Already landed

- `Graph` stores one native-endian `uint32` buffer (`bytes`, 8 bytes/edge);
  `Graph.edges` is a lazy `Sequence` view; `G.edge_bytes()` is borrowed by Rust.
- `pvt.from_edge_file()` streams plain or `.gz` edge lists directly into that
  buffer; `from_edge_list(deduplicate=True)` packs 64-bit keys and uses NumPy
  `unique` when available.
- Rust kernels take `&Bound<PyBytes>`; `setup_graph` builds flat CSR
  (`offsets` + `nbrs`, `u32` neighbors) and compacts full neighborhoods in place,
  so there is no PyO3 edge copy, no `Vec<Vec<u32>>`, and no `by_degrees`.
- The Python backend is single-process; `procs` only controls Rayon.
- The stress harness streams through `from_edge_file` and writes indented JSON.

Remaining known gaps from that work:

- `Graph.degrees` is still a `list[int]` (~110 MB at orkut: 3M Python ints plus
  list slots). An `array('I')` would cut it ~10x, but it is a public attribute and
  some tests compare it to a list, so it needs an API decision.
- `setup_graph` still uses several `usize` `n`-sized arrays (`pos`, `vert`,
  `degen_ranks`, `core_numbers`, cursors). `u32` would save ~60-80 MB at orkut;
  low priority now that peak is under 3 GB.

---

## 1. Status / progress reporting (`verbose` flag)

Goal: a long run must say what stage it is in and roughly how much is left,
without slowing the search and without changing results.

### Proposed surface

```python
pivoter(G, resolution="g", backend="rust", procs=4, verbose=0)
```

- `verbose=0` — silent (today's behavior).
- `verbose=1` — one line per major stage, with timings and sizes.
- `verbose=2` — periodic progress while searching (default every ~2 s).

Also honor `PIVOTERPY_VERBOSE=1|2` so CLI tools and the stress harness can enable
it without threading a kwarg through. Everything goes to **stderr**; stdout and
return values are unchanged.

### Stages and where to hook them

| Stage | Where | What to report |
|---|---|---|
| `load` | `Graph.from_edge_file` / harness | lines/s, `n`, `m`, elapsed (only at `verbose>=1`; cheap counters every ~1M lines) |
| `solve` config | `solver._run` | backend, resolution, bumped `min_k`/`max_k`, `n`, `m` |
| `setup` | `utils::setup_graph` | CSR build, degeneracy ordering, core pruning, compaction — each with `Instant`, plus `v_prime`, `max_p`, degeneracy, edge count kept |
| `search` | `core::count_*` worker + poll loop | roots done / total, work %, elapsed, rate, ETA, largest remaining root |
| `reduce` | `core::count_*` after the channel closes | map size, elapsed |
| `derive/cleanup/remap` | `solver._coarser_counts`, `_cleanup`, `_remapping` | elapsed, entry counts |

`setup_graph` used to have timing `println!`s (still commented at the top of
`src/cpu/utils.rs`). Replace them with a returned `SetupStats` struct, and format
once in Python.

### Rust search progress: implementation sketch

Every `count_*` already owns a main thread that polls `py.check_signals()` every
50 ms while a Rayon worker thread runs (`src/cpu/core.rs:103-115, 318-330,
~500-520`). That loop is the natural printer: it holds the GIL, it already wakes
up on a fixed schedule, and it does not touch the hot path.

```rust
struct Progress {
    phase: AtomicU8,          // 0 setup, 1 search, 2 reduce
    roots_done: AtomicUsize,
    work_done: AtomicU64,     // weighted units
    total_roots: usize,
    total_work: u64,
    t0: Instant,              // set when search starts
}
```

- Wrap the per-root map in `roots_done.fetch_add(1, Relaxed)` and
  `work_done.fetch_add(weight, Relaxed)`, where `weight` is a monotone proxy for
  that root's cost. Rayon's own task granularity does not help here because the
  biggest root is a single task.
- In the poll loop, every ~2 s (track the last print time), read the counters and
  print one line. `Relaxed` is fine; these are diagnostics.
- Keep the existing 50 ms wakeup so Ctrl+C stays responsive. Do not print from
  inside `branch_*`; that would contend on a shared stream.

Example output:

```
[pivoter] setup: n=3997962 m=34681189 csr 6.1s degen 9.4s prune 2.2s compact 9.1s
          v'=... max_p=... degeneracy=...
[pivoter] search: 812/3980000 roots (0.4% work) 142.3s 5.7 roots/s eta ~3h12m
[pivoter] reduce: 0.3s | total 171.4s
```

### Choosing the work weight (ETA quality)

Roots are processed largest-first (`.rev()` in `core.rs`), and per-root cost is
strongly superlinear in `c = len(degen_nbhds[v])` (worst case `2^c`, in practice
clique-density dependent). Consequences:

- `roots_done / total_roots` is a terrible ETA: the first 0.1% of roots may be
  most of the work, and progress would sit near 0% for hours.
- Use a precomputed cost proxy at setup time, e.g. `w(v) = c^2` or
  `w(v) = sum_{u in degen_nbhds[v]} deg(u)`, and report
  `work_done / total_work`. Document that it is a heuristic.
- Report the largest remaining root size as a separate "long pole" indicator.
- Optional refinement: after the first N finished roots, fit a tiny cost model
  (`time ~ a + b*w`) from observed per-root durations and re-estimate. Persisting
  the histogram per (graph fingerprint, resolution, k) would make repeat runs
  show a useful ETA immediately.

### Python backend

`PythonKernel.execute` loops over `valid_roots` serially; print every
`max(1, len(valid_roots)//100)` roots when `verbose>=2`. Same stage lines from
`solver._run`. No atomics needed.

### Stress harness

- Add `--verbose` to the driver and forward it to the worker (env var or flag),
  so stderr from the subprocess shows live progress.
- Record `phases: {load, setup, search, reduce, derive, cleanup, remap}` and the
  per-root cost histogram in the result JSON when verbose. Timings do not change
  results, but keeping them separate from the existing `solve_s` keeps old and
  new results comparable.
- The histogram is also the input to the GPU decision in section 2, so build it
  once and reuse it.

### Pitfalls

- Do not let progress printing serialize the search: all printing happens on the
  poll thread, never on Rayon workers.
- Cap output to one line per interval and avoid carriage-return spam when stderr
  is not a TTY.
- `verbose` must not change the returned counts or allocation behavior (no
  enabling of otherwise-dead structures).
- Make the flag available through the stress harness and the CLI, not just the
  Python API, or the 40-minute run still has no feedback.

---

## 2. GPU idea: offload short-but-wide roots

### What would fit a GPU

The SCT search is recursive, branchy, and uses growing bitsets — a poor fit.
But two properties make a *subset* of the work GPU-friendly:

1. **Roots are independent.** Every root produces a partial count vector that is
   summed at the end. No cross-root dependencies.
2. **The tail is short and wide.** Degeneracy ordering means most roots have few
   candidates (`c` small), so their recursion is shallow and their local
   adjacency is tiny: for `c <= 64`, a local neighborhood row is a single `u64`
   bitmask; the whole local subgraph is `64 x 64` bits = 512 bytes. There are
   millions of such roots on graphs like `com-lj`/`com-orkut`, which is exactly
   the shape GPUs like: many identical, small, independent problems.

Meanwhile the *head* of the distribution (a few roots with `c` in the thousands)
is where the current CPU code already spends most of its time and where its
pivoting/pruning is strongest. Those roots do not fit on a GPU well (`c^2/8`
bytes of local bitsets alone). So the realistic design is **hybrid**: CPU keeps
the heavy roots, GPU takes the tail. That also means the payoff depends entirely
on the cost histogram — hence section 1 first.

### Kernel shapes that are plausible

**A. Bitset intersection kernels (`k=3`, and level-1 of any root).**
Pack each local row into `u32`/`u64` masks. One thread handles one candidate
pair; counting triangles is `popcount(row_u & row_v)`. For `c <= 64` a whole row
is one register, so no shared memory is needed and occupancy is excellent. This
is the best first prototype: simple, exact, and directly replaces the `k=3`
work for tail roots.

**B. Batched per-root wedge enumeration (`k=4..6`).**
One block per root (or per (root, first-level pivot)). Load the root's local
bitmask rows into shared memory, expand level by level, and accumulate counts per
`k` in block-local `u64` counters. Frontier arrays live in shared memory for
`c <= ~256`; larger roots stay on CPU. Level-synchronous expansion avoids the
recursive stack entirely.

**C. Dense local subgraphs via batched linear algebra.**
For roots where the local subgraph is dense (high core, small `c`), the adjacency
matrix is small and dense. Counting `k`-cliques can be expressed through
repeated sparse/dense products or `A^k` traces, which GPUs do well. Exactness is
the catch: integer counts overflow quickly, so this is only viable with
`u64`/`u128` accumulation and explicit bounds checks, or as a denser variant of
kernel B. Lower priority than A/B.

Sketch of the offload policy:

```
for each root v:
    if c(v) <= GPU_MAX_C and root_work(v) <= GPU_MAX_WORK:
        enqueue for GPU batch
    else:
        run on CPU (Rayon, unchanged)
batch GPU roots in groups of >= a few ms of work
sum per-root u64 partials on CPU into the BigUint accumulator
```

### Exactness and accumulation

Per-root counts for tail roots are small: with `c <= 64` and `k <= 8`,
`sum_i C(c, i) < 2^53`, comfortably inside `u64`; even `C(64,8) ~ 4.4e9`. So the
GPU can accumulate in `u64` per block/root with **no big integers on device**.
The CPU sums per-root `u64`s and only falls back to `BigUint` if the running
total would overflow (or simply always sums into `BigUint`, which is cheap once
per root rather than per leaf). Enforce the bound with a saturating check when
building the batch and reject roots that do not satisfy it.

### Data movement and launch overhead

- Upload the CSR once (orkut ~1.4 GB → tens to ~150 ms over PCIe at 10-25 GB/s);
  keep it resident across roots for the whole run.
- Tail-root bitmask rows can be generated on the fly from the CSR in a small
  kernel per batch, or uploaded compactly.
- Batch enough roots per launch to amortize ~5-10 µs launch latency; sub-ms
  batches will be dominated by overhead.
- Per-root counts come back as a `u64` vector; the reduce is O(roots) and tiny.

### Risks and engineering constraints

- `src/gpu_backend.rs` is a stub (`run_cuda_dfs_stub`) and the `cuda` Cargo
  feature is unused; `count_global_cuda()` is bound but commented out in
  `src/lib.rs`. There is no real backend to extend yet.
- The Python module is built with `abi3-py38`; use runtime kernel compilation
  (`cudarc`/NVRTC) or `wgpu` rather than a build-time `nvcc` dependency, or CI and
  most users break.
- `wgpu` is portable (Vulkan/Metal/DX12) but slower and more restrictive than
  CUDA for atomics and warp intrinsics; decide the target audience first.
- Divergence and occupancy for tiny roots; warp-level work distribution matters
  more than raw FLOPs.
- BigUint is unavailable on device by design; keep the exactness plan above.
- Rayon already parallelizes across roots on CPU, so the GPU only wins if it
  beats the CPU *on the tail's throughput* — measure before building.

### Experiment sequence

1. Emit the root-cost histogram and per-root timings from section 1 on
   `as-skitter`, `com-lj`, `com-orkut`.
2. Answer: what fraction of wall time is in roots with `c <= 64`? If it is under
   ~10-20%, a GPU backend cannot matter much; if it is 50%+, it is promising.
3. Prototype kernel A (`k=3` only) behind an opt-in feature. Compare per-root
   throughput against one CPU thread on the same tail.
4. If that wins clearly, generalize to kernel B for `k=4..6` and add the hybrid
   scheduler (CPU head, GPU tail).
5. Keep `resolution="v"/"e"` on CPU; their output size makes GPU accumulation
   pointless at scale.

### Cheaper alternatives to try first

Before a GPU backend, the same insight ("short and wide") points at cheap CPU
wins:

- **Batch tiny roots into one Rayon task** so the per-root `FixedBitSet`
  allocations and task overhead are amortized (today each root allocates
  `c` bitsets plus a stack).
- **Use sorted `Vec<u32>` local rows for sparse roots** and bitsets only when the
  local density crosses a threshold, avoiding `c^2/8` allocations for the tail.
- **Precompute per-root `u64` masks** when `c <= 64` and run a specialized
  intersection loop that avoids `FixedBitSet` entirely.

Each is a contained change, benchmarkable on the same histogram, and they can be
combined with a GPU later (the GPU bitmask layout is identical).

---

## 3. Remaining CPU and memory work

Ordered by expected impact given the current 2.76 GB peak on orkut.

### P1 — Remove the second adjacency copy with degeneracy-rank relabeling

`setup_graph` currently returns two flat CSRs: full neighborhoods and forward
(degeneracy) neighborhoods, both resident for the search (~0.9 GB + ~0.4 GB at
orkut). If survivors are relabeled in **degeneracy-rank order** and each CSR row
is sorted ascending, then:

- full neighborhood = the whole row;
- forward neighborhood = the suffix where `neighbor_id > v` (a
  `partition_point` on a sorted row).

This removes one adjacency copy and the separate sort pass, keeps all pruning,
and keeps `valid_roots` for output mapping. It also shrinks the per-root `cands`
slice plumbing.

### P1 — Root batching with a memory budget

- Process roots in batches and merge each batch into the accumulator, then drop
  batch state. Peak then scales with the largest batch, not with all roots.
- A single huge root still needs `c^2/8` bytes of local bitsets (10k candidates
  ~12.5 MB; 100k ~1.25 GB), so a memory-aware scheduler should keep `procs` high
  for small roots and throttle the giants.
- For `vertex`/`edge`, Rayon currently keeps one `HashMap<_, Vec<BigUint>>`
  accumulator **per thread** (`core.rs:290-312, 521-543`), so nearly-final result
  memory is multiplied by `procs` during reduction. Batch merging avoids that.
- Optional `components=True` for multi-component graphs: exact (`global_counts`
  is additive, and vertex/edge key sets are disjoint), but it does not help a
  giant component like orkut's. Root batching is the general answer.

### P1 — Local-resolution output memory

Independent of the search, and it can dominate for `edge` resolution:

- `solver._cleanup` (around `solver.py:250`) creates an empty `list` for **every**
  edge that has no counts: 117M lists at orkut. Only create entries for nonzero
  counts.
- `solver._remapping` (around `solver.py:268-290`) builds a second full dict while
  the first is alive, roughly doubling peak.
- `counts[:tmp_max+1]` allocates a new list per row; truncate in place.
- At orkut scale, `dict[(u, v) -> list[int]]` for edge resolution is
  fundamentally infeasible. Offer a compact mode (flat key array + offsets) or a
  streaming callback for `edge` resolution.

### P2 — Search-loop refinements

- Reuse scratch bitsets instead of `label.clone()` per candidate
  (`core.rs:174, 185, 191, 199` and the matching spots in the vertex/edge
  branches).
- Replace `pv.clone()` / `hv.clone()` per child (`core.rs:420-440`, and its
  vertex/edge twins) with a parent-linked path structure; on dense graphs this is
  a large transient cost.
- Hybrid local adjacency: sorted `Vec<u32>` rows for sparse local subgraphs,
  bitsets only when dense (overlaps with the "cheaper alternatives" above).
- `precompute_ncr` allocates `(max_p+1) x (max_k+1)` `BigUint`s
  (`utils.rs:48`) and flattens poorly (`Vec<Vec<_>>`). Flatten the table, and use
  `u64`/`u128` cells below a bound with `BigUint` only above it.

### P2 — Width-adaptive counting (BigUint fast path)

`BigUint` is used for clique **counts**, not node IDs. Counts can genuinely
exceed `u128` (`K_128` has `C(128,64) ~ 2.4e37`), so a blanket `u64` switch is
wrong for exactly the dense graphs used to stress a clique counter.

Exact fast path:

1. Per root with `c` candidates, bound the contribution by
   `sum_{i=0}^{min(c, max_k-1)} C(c, i)` using saturating `u128`, early-exiting
   once it passes `u64::MAX`. O(`max_k`) per root, negligible.
2. Dispatch per root: `u64` counters when the bound fits, `BigUint` otherwise.
   Factor the branch code over a small count trait (or macro) so the three
   `branch_*` functions are not triplicated.
3. Simpler variant: accumulate in `u64` with `checked_add` plus a per-root
   overflow flag; recompute only overflowing roots with `BigUint`.

This is also what makes a future GPU tail possible without device-side big ints.

### Leave alone

The three ID mappings are fine and none forces `BigUint`:

1. original labels → `0..n-1` (Python, `Graph.from_edge_list` / `from_edge_file`);
2. internal IDs → compressed valid roots (Rust `setup_graph`, a residency
   optimization for dense bitsets);
3. valid roots → original labels on output (`valid_roots` + `solver._remapping`).

---

## Suggested order

1. **`verbose` flag + stage timings + root-cost histogram.** Cheap, unblocks
   everything else, and directly addresses the "40 minutes with no output"
   problem.
2. **Root batching for the tail + degeneracy-rank relabeling.** Cuts both time
   overhead and the remaining adjacency memory.
3. **Fix `_cleanup`/`_remapping` and add a compact `edge` output.** Only if
   local resolutions matter at SNAP scale.
4. **GPU prototype for `k=3` tail roots**, then decide with the histogram
   whether kernel B is worth it.
5. Width-adaptive `u64`/`BigUint` if profiling shows big-int cost is real
   (profile first; do not assume).
