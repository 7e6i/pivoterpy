# Memory ideas: reducing peak RSS on real-world networks

Context: OOMs on `com-orkut` (`n = 3,072,441`, `m = 117,185,083`, per
`tests/speedtest.py`) most likely happen **before the clique search starts** —
in Python graph construction and Rust's duplicated adjacency — not in the search
itself. Connected-component chunking helps, but does not fix the main problem on
a graph with one giant component.

## Where the memory goes on `com-orkut`

### Python side, current path

| Structure | Approx. size |
|---|---|
| `read_file` list of 117M `(int, int)` tuples | ~14 GB |
| `from_edge_list` dedupe set of 117M tuples | ~9-10 GB |
| `list(internal_edges)` copy | ~0.9 GB |
| `Graph.edges` retained list of tuples | ~7.5 GB |

`speedtest.py` keeps `edges` alive after `pvt.from_edge_list(edges)`, so peak
during construction can approach **30 GB**, and the input list (~14 GB) plus
`G.edges` (~7.5 GB) are still alive when Rust starts.

### Rust side, current path

| Structure | Approx. size |
|---|---|
| PyO3 `Vec<(usize, usize)>` (input copy) | 1.9 GB |
| `nbhds: Vec<Vec<usize>>` in `setup_graph` | 1.9 GB + n Vec headers |
| `compressed_nbhds` | 1.9 GB |
| `compressed_degen_nbhds` | up to 1.9 GB |

Another ~6 GB. Also, `count_global` / `count_vertex` / `count_edge` keep the
input `Vec` alive for the whole search because `edges` is a by-value parameter
that is not dropped after `setup_graph` (`src/cpu/core.rs:22-32, 214-224, 451-461`).
Add `G.edges` and real-network runs hit 25-30 GB easily.

## Is component splitting possible?

Yes, and it is exact for global counts: a clique cannot span connected
components, so

`global_counts = sum(global_counts(C_i))`

and for vertex/edge resolution the per-component result dictionaries have
disjoint keys, so they can be merged. Implementation:

1. Compute component IDs in Rust (BFS/union-find over the CSR).
2. Iterate components, building/processing only one component's sub-CSR at a
   time.
3. For global: accumulate a single count vector.
4. For vertex/edge: merge results, or stream them to disk/caller.

**Caveat:** real networks like `com-orkut` are almost entirely one giant
component, so component splitting gives little peak reduction there. It helps
multi-component datasets and lets you free per-component search state, but it
does not solve the giant-component case. The better complement is **root
batching**, since every root's clique count is independent and roots are already
the unit of Rayon parallelism (`src/cpu/core.rs:48-80`).

## Recommended plan, by impact

### P0 — Compact the Python graph (biggest win)

- Store edges internally as a flat compact buffer (`array('I')`/`array('Q')` or
  NumPy `uint32`), not `list[tuple]`.
- Make `Graph.edges` a lazy `Sequence` that yields tuples on iteration and
  supports `len`, `__iter__`, `__getitem__`. Tests use `set(G.edges)` and
  iteration, so this is compatible; the docs' `list[tuple]` type would need
  updating.
- Rewrite `from_edge_list` to avoid the tuple set. Either:
  - pass duplicates through and dedupe in Rust's CSR builder, or
  - dedupe compactly with NumPy `unique` on encoded 64-bit keys (transient
    ~2 GB, still far below 9-10 GB).
- Add `pvt.from_edge_file(path)` that streams lines directly into compact
  arrays. This alone eliminates the 14 GB `read_file` spike and the `edges` list
  retained by callers.
- Compute `degrees` into a compact array at the same time.
- For global resolution, `Graph.edges` is otherwise never touched; it should not
  be materialized or retained at all.

Expected result: Python graph memory goes from **~20+ GB to ~1-2 GB**.

### P0 — Stop copying and duplicating in Rust

- Accept the compact edge buffers via `PyBuffer`/memoryview (or optionally
  NumPy) instead of accepting `Vec<(usize, usize)>`; zero tuple conversion.
- Build one **flat CSR** (`offsets: Vec<u64>` or `u32`, `neighbors: Vec<u32>`)
  with two passes over the edge buffers, then drop the input buffers.
- Remove `Vec<Vec<usize>>` entirely. Remove the unused `by_degrees` structure
  (`src/cpu/utils.rs:97-100`) — it is built but never used.
- `drop(edges)` immediately after `setup_graph` if the input is still owned,
  which is a trivial immediate saving.
- Use `u32` neighbors when `n <= u32::MAX` (~4.29B; `com-orkut` easily fits),
  halving adjacency bytes. Keep a `u64` fallback.

Expected result: Rust working set goes from **~6 GB to ~1 GB** for orkut.

### P1 — Eliminate the second adjacency copy

Currently `compressed_nbhds` and `compressed_degen_nbhds` are two full copies.
Relabel surviving vertices in **degeneracy-rank order** (`new_id = degen_rank`),
sort each CSR row ascending, and then:

- full neighborhood = the whole row
- forward/degen neighborhood = the suffix where `neighbor_id > v`

Use `partition_point`/binary search on the sorted row. This removes one full
adjacency copy and the separate sorting pass, with no loss of the
forward-neighborhood pruning. The output mapping still works through
`valid_roots`.

This is the step that makes the Rust representation genuinely lean rather than
just smaller.

### P1 — Chunk the search with a memory budget

- Process roots in batches; merge per-batch results into the output accumulator
  and drop batch state.
- Process the largest forward-degree roots first, optionally **serially**, since
  a single huge root's `local_nbhds` is `c^2/8` bytes (10k candidates ~12.5 MB;
  100k ~1.25 GB). A memory-aware scheduler can keep `procs` high for small roots
  and throttle giant ones.
- For vertex/edge resolution, this matters more: Rayon currently keeps one
  `HashMap<_, Vec<BigUint>>` accumulator **per thread**
  (`src/cpu/core.rs:280-303, 507-530`), so near-final result memory is
  multiplied by `procs` during reduction. Batch merging avoids that.
- Add optional `components=True` for multi-component graphs, but document that
  it does not help a giant component.

### P1 — Fix local-resolution output memory

Separate from the search, but can dominate:

- `solver._cleanup` currently creates an empty list for **every edge** before
  checking whether it has counts (`solver.py:249-256`): 117M lists is many GB.
  Only create entries for nonzero counts, or use flat arrays.
- `_remapping` builds a second full dictionary while the first is still alive
  (`solver.py:268-286`), roughly doubling peak for vertex/edge output. Remap in
  place.
- Consider a compact output mode for edges: a flat key array plus offsets/counts,
  or a streaming/callback API, rather than `dict[(u,v) -> list[int]]`. At orkut
  scale, edge resolution as a nested Python dict is fundamentally not feasible.
- `counts[:tmp_max+1]` currently allocates a new list per row; mutate/truncate
  instead.

### P2 — Search-loop and configuration refinements

- Reuse a scratch bitset in the pivot loop instead of `label.clone()` per
  candidate (`src/cpu/core.rs:168-178, 397-406, 641-650`).
- Replace `pv.clone()`/`hv.clone()` per child in vertex/edge search
  (`src/cpu/core.rs:411-431, 654-673`) with a parent-linked/path-append
  structure; this can be a large transient cost on dense graphs.
- Consider a hybrid local-adjacency representation: sorted `Vec<u32>` rows for
  sparse local subgraphs, bitsets only when dense. That cuts the `c^2/8` worst
  case and the stack label memory. Bigger change, but it is the real answer for
  pathological high-degeneracy/dense cases.
- `precompute_ncr` allocates `(max_p+1) x (effective_max_k+1)` `BigUint`s
  (`src/cpu/utils.rs:33-49`). For high-degeneracy graphs this can be surprisingly
  large (`d^2`); use `u64`/`u128` cells where possible or compute lazily.
  Usually minor for real networks, but worth bounding.
- Use `u32` for degree/rank/position arrays where safe (six `n`-sized `usize`
  arrays in `setup_graph` ~150 MB at orkut's n; halving that is easy).

## Proposed priority

If the goal is "stop OOMing on real networks," do it in this order:

1. **Compact Python graph storage + streaming file reader.**
2. **Buffer-based Rust input + single flat CSR + drop input after setup.**
3. **Degeneracy-rank relabeling to remove the duplicate adjacency.**
4. **Root batching with a memory budget + fix `_cleanup`/`_remapping` for local
   resolutions.**
5. **Optional component streaming, hybrid local adjacency, compact edge output.**

A realistic target for `com-orkut` after steps 1-3 is roughly **2-3 GB peak** for
global counts, versus the current ~25-30 GB.

## Compatibility question

The only meaningful API break is `Graph.edges`. Options:

- **Lazy sequence** (recommended): supports `len`, iteration, indexing,
  `set(...)`; no code changes for most users, docs updated.
- **Keep `list[tuple]` property but materialize on access**: preserves the exact
  type, but any code that reads `G.edges` on orkut pays the 7.5 GB. Internal code
  could use a private compact array, but user code would not.
- **New `Graph` representation + deprecation period**: more conservative, slower
  to deliver.
