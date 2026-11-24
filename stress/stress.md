# Stress tests

Standardized stress-test suite for **pivoterpy**. The goal is to make
performance and memory behavior comparable across commits, backends, machines,
and resolutions, and to catch out-of-memory regressions on real-world graphs.

## References

- **Dataset collection:** [SNAP: Stanford Network Analysis Project — Data](https://snap.stanford.edu/data/index.html)
- **Methodology reference:** Almasri, El Hajj, Nagi, Xiong, Hwu.
  *Parallel K-Clique Counting on GPUs.*
  [arXiv:2104.13209](https://arxiv.org/abs/2104.13209)
  (graph orientation + pivoting, vertex- and edge-centric parallelization,
  memory-constrained partitioning).

## Graphs to test

All graphs are undirected simple graphs from SNAP. Use the `*ungraph` files (or
the single graph file for `as-skitter`), and ignore `#` comment lines.

| Graph | SNAP page | Download | Nodes | Edges | Triangles |
|---|---|---:|---:|---:|---:|
| `com-dblp` | [com-DBLP](https://snap.stanford.edu/data/com-DBLP.html) | [com-dblp.ungraph.txt.gz](https://snap.stanford.edu/data/bigdata/communities/com-dblp.ungraph.txt.gz) | 317,080 | 1,049,866 | 2,224,385 |
| `as-skitter` | [as-Skitter](https://snap.stanford.edu/data/as-Skitter.html) | [as-skitter.txt.gz](https://snap.stanford.edu/data/as-skitter.txt.gz) | 1,696,415 | 11,095,298 | 28,769,868 |
| `com-lj` | [com-LiveJournal](https://snap.stanford.edu/data/com-LiveJournal.html) | [com-lj.ungraph.txt.gz](https://snap.stanford.edu/data/bigdata/communities/com-lj.ungraph.txt.gz) | 3,997,962 | 34,681,189 | 177,820,130 |
| `com-orkut` | [com-Orkut](https://snap.stanford.edu/data/com-Orkut.html) | [com-orkut.ungraph.txt.gz](https://snap.stanford.edu/data/bigdata/communities/com-orkut.ungraph.txt.gz) | 3,072,441 | 117,185,083 | 627,584,181 |
| `com-friendster` | [com-Friendster](https://snap.stanford.edu/data/com-Friendster.html) | [com-friendster.ungraph.txt.gz](https://snap.stanford.edu/data/bigdata/communities/com-friendster.ungraph.txt.gz) | 65,608,366 | 1,806,067,135 | 4,173,724,142 |

`com-friendster` is an extreme-scale case (tens of GB just for a compact
adjacency structure). Treat it as a separate out-of-core / high-memory tier.

### Download and unpack

```bash
mkdir -p stress/data
cd stress/data

base=https://snap.stanford.edu/data
curl -LO "$base/bigdata/communities/com-dblp.ungraph.txt.gz"
curl -LO "$base/bigdata/communities/com-lj.ungraph.txt.gz"
curl -LO "$base/bigdata/communities/com-orkut.ungraph.txt.gz"
curl -LO "$base/as-skitter.txt.gz"
curl -LO "$base/bigdata/communities/com-friendster.ungraph.txt.gz"

gunzip -k *.txt.gz
```

Add `stress/data/` to `.gitignore`; do not commit datasets.

## Test tiers

| Tier | Graphs | Purpose |
|---|---|---|
| **smoke** | `com-dblp` | Fast correctness and API checks; runs in CI |
| **medium** | `as-skitter`, `com-lj` | Realistic scale on a laptop/workstation |
| **large** | `com-orkut` | Primary memory-regression target |
| **extreme** | `com-friendster` | High-memory / out-of-core target; not a default run |

## Standard test matrix

For each graph in the active tier:

| Dimension | Values |
|---|---|
| Backend | `rust` (required); `python` only on `com-dblp`/small subgraphs |
| Resolution | `global`, `vertex`, `edge` |
| `k` range | `[3,3]` (triangles), `[4,4]`, `[4,8]`, `[3,None]` where feasible |
| `procs` | Rust: `1`, `2`, `4`; Python: `1` only (single-process) |
| Ordering | same graph object reused across runs where possible |
| Repetitions | 3; report median and max |

Record for every run:

- wall time (seconds)
- peak RSS (`/usr/bin/time -v` or `resource.getrusage(RUSAGE_SELF).ru_maxrss`)
- graph load time and solver time separately
- returned counts plus which invariants passed
- commit, Rust/Python versions, CPU, RAM, OS, `procs`, resolution, `min_k`, `max_k`

## Correctness oracles / invariants

Every run should automatically check:

1. `global_counts[0] == 1`
2. `global_counts[1] == n`
3. `global_counts[2] == m`
4. `global_counts[3] == triangles` from the SNAP table (where `min_k <= 3 <= max_k`)
5. For `vertex_counts`:
   `sum(vertex_counts[v][k] for v) == k * global_counts[k]`
6. For `edge_counts`:
   `sum(edge_counts[e][k] for e) == k*(k-1)/2 * global_counts[k]`
7. Coarser-resolution derivation is consistent:
   `pivoter(G, resolution="e").global_counts == pivoter(G, resolution="g").global_counts`
8. Euler characteristic / curvature totals match the counts they are derived from.

For `k >= 4`, there is no published ground truth for these graphs. Cross-check
by comparing `rust` against `python` on induced subgraphs, and by comparing
`global` against `vertex`/`edge` resolutions on smaller graphs.

## Dataset preparation

- Use the largest connected component as provided by SNAP (all five files are
  already WCC-only for the social graphs; `as-skitter` is 99.9% WCC).
- Ignore `#` comment lines.
- Node labels are 0-based integers for these files, so relabeling should be a
  no-op. Still verify `n` and `m` against the table above after construction.
- Canonicalize to undirected, simple, `u < v`, deduplicated edges.
- Prefer a compact on-disk format (flat `uint32`/`uint64` pairs) for repeated
  runs so parse time does not dominate and the loader itself does not mask
  memory regressions.

## Planned layout

```text
stress/
  stress.md          # this file
  data/              # downloaded datasets (gitignored)
  run_stress.py      # driver: matrix, timing, peak RSS, invariants
  results/           # JSON/CSV per commit (gitignored by default)
```

The driver should:

1. Take `--graphs`, `--tiers`, `--resolutions`, `--procs`, `--k`, `--repeat`.
2. Measure peak RSS from a child process so one run cannot contaminate another.
3. Emit one JSON record per run plus a compact Markdown/CSV summary.
4. Fail non-zero if an invariant fails or a configured memory/time budget is
   exceeded.
5. Never silently skip a graph: report `SKIP` with the reason (missing file,
   insufficient RAM, unimplemented resolution).

## Baseline targets

- `com-orkut`, global counts, `procs=1`: complete without OOM on a 16 GB
  machine, with peak RSS reported.
- `com-friendster`: complete global counts in a documented high-memory tier
  (or explicitly fail with a clear memory error rather than being killed by the
  OOM killer).
- No count regressions against the SNAP triangle totals.
- Every new optimization is evaluated on both wall time and peak RSS; a time win
  that increases peak memory is not automatically a win.

See [../tests/ideas.md](../tests/ideas.md) and
[../tests/ideas2.md](../tests/ideas2.md) for performance and memory work items
this suite is meant to validate.
