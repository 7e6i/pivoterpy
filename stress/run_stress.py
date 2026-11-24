#!/usr/bin/env python3
"""Standardized global-count stress tests for pivoterpy.

Runs the Rust backend at ``procs`` 1, 2, and 4, and the pure-Python reference
backend single-process, against the SNAP graphs described in
``stress/stress.md``. Only ``resolution="global"`` is covered for now.

Each (graph, backend, procs) configuration runs in its own subprocess so that
peak RSS and failures are isolated. The driver records wall time, load time,
solve time, peak RSS, the returned counts, and correctness checks.

Examples
--------
    python stress/run_stress.py --graphs com-dblp
    python stress/run_stress.py --graphs as-skitter com-lj --backends rust
    python stress/run_stress.py --graphs com-dblp --min-k 3 --max-k 3

Results are written as indented JSON to ``stress/results/`` (gitignored) and a
summary table is printed to stdout.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
DATA = ROOT / "data"
DEFAULT_RESULTS = ROOT / "results"

# name -> (filename, nodes, edges, triangles) from SNAP
GRAPHS = {
    "com-dblp": ("com-dblp.ungraph.txt.gz", 317_080, 1_049_866, 2_224_385),
    "as-skitter": ("as-skitter.txt.gz", 1_696_415, 11_095_298, 28_769_868),
    "com-orkut": ("com-orkut.ungraph.txt.gz", 3_072_441, 117_185_083, 627_584_181),
    "com-lj": ("com-lj.ungraph.txt.gz", 3_997_962, 34_681_189, 177_820_130),
    
    # "com-friendster": (
    #     "com-friendster.ungraph.txt.gz",
    #     65_608_366,
    #     1_806_067_135,
    #     4_173_724_142,
    # ),
}

DEFAULT_PROCS = (1, 2, 4)
DEFAULT_BACKENDS = ("python", "rust")
RESULT_PREFIX = "RESULT_JSON:"


# ---------------------------------------------------------------------------
# worker
# ---------------------------------------------------------------------------


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt")
    return open(path, "rt")


def read_edges(path: Path) -> list[tuple[int, int]]:
    """Read a SNAP edge list, skipping comments, normalizing order."""
    edges: list[tuple[int, int]] = []
    with _open_text(path) as f:
        for line in f:
            if not line or line[0] == "#":
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            u, v = int(parts[0]), int(parts[1])
            if u == v:
                continue
            if u > v:
                u, v = v, u
            edges.append((u, v))
    return edges


def _mb(kb: int) -> float:
    return round(kb / 1024.0, 1)


def run_worker(args: argparse.Namespace) -> int:
    """Load a graph, run one configuration, print a JSON result."""
    python_dir = REPO / "python"
    if str(python_dir) not in sys.path:
        sys.path.insert(0, str(python_dir))

    if args.mem_limit_gb:
        limit = int(args.mem_limit_gb * 1024**3)
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

    name = args.graph
    filename, expected_n, expected_m, expected_triangles = GRAPHS[name]
    path = DATA / filename

    try:
        import pivoterpy as pvt
    except Exception as exc:  # pragma: no cover - environment failure
        print(f"failed to import pivoterpy: {exc!r}", file=sys.stderr)
        return 2

    record: dict = {
        "graph": name,
        "backend": args.backend,
        "procs": args.procs,
        "resolution": "global",
        "min_k": args.min_k,
        "max_k": args.max_k,
        "status": "error",
    }

    try:
        t0 = time.perf_counter()
        edges = read_edges(path)
        record["read_s"] = round(time.perf_counter() - t0, 3)

        t0 = time.perf_counter()
        G = pvt.from_edge_list(edges)
        record["graph_s"] = round(time.perf_counter() - t0, 3)
        del edges

        record["n"] = G.n
        record["m"] = G.m

        t0 = time.perf_counter()
        P = pvt.pivoter(
            G,
            resolution="global",
            backend=args.backend,
            procs=args.procs,
            min_k=args.min_k,
            max_k=args.max_k,
        )
        record["solve_s"] = round(time.perf_counter() - t0, 3)

        counts = P.global_counts
        record["counts"] = counts
        record["max_k"] = len(counts) - 1

        checks: dict[str, bool] = {
            "n": G.n == expected_n,
            "m": G.m == expected_m,
        }

        # `_cleanup` injects trivial counts and then zeros everything below
        # min_k, so only check k=0,1,2 when they survive the requested range.
        lo = 0 if args.min_k is None else args.min_k
        hi = float("inf") if args.max_k is None else args.max_k
        trivial = {0: 1, 1: G.n, 2: G.m}
        for k, want in trivial.items():
            if lo <= k <= hi:
                checks[f"global_{k}"] = (
                    counts is not None and len(counts) > k and counts[k] == want
                )

        # The solver injects trivial k=0,1,2 counts before applying min_k, so
        # only compare k=3 when it was actually part of the requested range.
        k_min = 3 if args.min_k is None else args.min_k
        k_max = float("inf") if args.max_k is None else args.max_k
        if k_min <= 3 <= k_max and counts is not None and len(counts) > 3:
            checks["global_3"] = counts[3] == expected_triangles

        record["checks"] = checks
        record["status"] = "ok" if all(checks.values()) else "invariant-fail"
        record["ok"] = all(checks.values())

    except MemoryError:
        record["error"] = "MemoryError"
    except Exception as exc:  # solver calls sys.exit on some failures
        record["error"] = f"{type(exc).__name__}: {exc}"

    usage = resource.getrusage(resource.RUSAGE_SELF)
    record["peak_rss_mb"] = _mb(usage.ru_maxrss)
    print(RESULT_PREFIX + json.dumps(record))
    return 0 if record.get("ok") else 1


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="mode")

    w = sub.add_parser("worker", help=argparse.SUPPRESS)
    w.add_argument("--graph", required=True, choices=sorted(GRAPHS))
    w.add_argument("--backend", required=True, choices=DEFAULT_BACKENDS, default="rust")
    w.add_argument("--procs", required=True, type=int, default=4)
    w.add_argument("--min-k", type=int, default=None)
    w.add_argument("--max-k", type=int, default=None)
    w.add_argument("--mem-limit-gb", type=float, default=0.0)

    d = sub.add_parser("run", help="run the stress matrix")
    d.add_argument(
        "--graphs",
        nargs="+",
        default=["all"],
        metavar="GRAPH",
        help="graph names, or 'all' (default)",
    )
    d.add_argument(
        "--backends",
        nargs="+",
        default=list(DEFAULT_BACKENDS),
        choices=DEFAULT_BACKENDS,
    )
    d.add_argument(
        "--procs",
        nargs="+",
        type=int,
        default=list(DEFAULT_PROCS),
    )
    d.add_argument("--min-k", type=int, default=None)
    d.add_argument("--max-k", type=int, default=None)
    d.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="per-run timeout in seconds; 0 disables (default: 3600)",
    )
    d.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="repetitions per configuration (default: 1)",
    )
    d.add_argument(
        "--mem-limit-gb",
        type=float,
        default=0.0,
        help="worker RLIMIT_AS in GiB; 0 disables (default: 0)",
    )
    d.add_argument(
        "--results",
        type=Path,
        default=DEFAULT_RESULTS,
        help=f"output directory (default: {DEFAULT_RESULTS})",
    )
    d.add_argument(
        "--fail-on-timeout",
        action="store_true",
        help="treat timeouts as failures",
    )
    return p.parse_args(argv)


def resolve_graphs(names: list[str]) -> list[str]:
    if "all" in names:
        return [name for name in GRAPHS if (DATA / GRAPHS[name][0]).exists()]
    unknown = [name for name in names if name not in GRAPHS]
    if unknown:
        raise SystemExit(f"unknown graph(s): {', '.join(unknown)}")
    return names


def parse_gnu_time(path: Path) -> float | None:
    try:
        text = path.read_text()
    except OSError:
        return None
    for line in text.splitlines():
        if "Maximum resident set size" in line:
            try:
                return _mb(int(line.rsplit(":", 1)[1].strip()))
            except ValueError:
                return None
    return None


def run_one(
    graph: str,
    backend: str,
    procs: int,
    args: argparse.Namespace,
) -> dict:
    filename = GRAPHS[graph][0]
    path = DATA / filename
    base = {
        "graph": graph,
        "backend": backend,
        "procs": procs,
        "resolution": "global",
        "min_k": args.min_k,
        "max_k": args.max_k,
    }

    if not path.exists():
        return {**base, "status": "missing", "error": f"missing {path}"}

    worker_cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "worker",
        "--graph",
        graph,
        "--backend",
        backend,
        "--procs",
        str(procs),
    ]
    if args.min_k is not None:
        worker_cmd += ["--min-k", str(args.min_k)]
    if args.max_k is not None:
        worker_cmd += ["--max-k", str(args.max_k)]
    if args.mem_limit_gb:
        worker_cmd += ["--mem-limit-gb", str(args.mem_limit_gb)]

    gnu_time = Path("/usr/bin/time")
    time_file: Path | None = None
    if gnu_time.exists():
        fd, name = tempfile.mkstemp(prefix="pivoterpy-stress-", suffix=".time")
        os.close(fd)
        time_file = Path(name)
        cmd = [str(gnu_time), "-v", "-o", str(time_file)] + worker_cmd
    else:
        cmd = worker_cmd

    print(
        f"running graph={graph} backend={backend} procs={procs} ...",
        file=sys.stderr,
        flush=True,
    )

    record: dict | None = None
    t0 = time.perf_counter()
    try:
        cp = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=args.timeout or None,
            check=False,
        )
        elapsed = time.perf_counter() - t0
        for line in cp.stdout.splitlines():
            if line.startswith(RESULT_PREFIX):
                try:
                    record = json.loads(line[len(RESULT_PREFIX) :])
                except json.JSONDecodeError:
                    pass
        if record is None:
            record = {
                **base,
                "status": "error",
                "elapsed_s": round(elapsed, 3),
                "returncode": cp.returncode,
                "stdout_tail": cp.stdout[-2000:],
                "stderr_tail": cp.stderr[-2000:],
            }
        else:
            record["elapsed_s"] = round(elapsed, 3)
            record["returncode"] = cp.returncode
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - t0
        record = {
            **base,
            "status": "timeout",
            "elapsed_s": round(elapsed, 3),
            "error": f"timeout after {args.timeout}s",
            "stdout_tail": (exc.stdout or "")[-2000:]
            if isinstance(exc.stdout, str)
            else "",
            "stderr_tail": (exc.stderr or "")[-2000:]
            if isinstance(exc.stderr, str)
            else "",
        }
    except OSError as exc:
        elapsed = time.perf_counter() - t0
        record = {
            **base,
            "status": "error",
            "elapsed_s": round(elapsed, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        if time_file is not None:
            timed_peak = parse_gnu_time(time_file)
            if record is None:
                record = {**base}
            if timed_peak is not None:
                record["peak_rss_mb"] = timed_peak
            time_file.unlink(missing_ok=True)

    return record


def summarise(record: dict) -> str:
    status = record.get("status", "?")
    counts = record.get("counts") or []
    cmax = max((i for i, c in enumerate(counts) if c), default=None)
    return " ".join(
        [
            f"{status:14}",
            f"{record.get('graph', '?'):14}",
            f"{record.get('backend', '?'):6}",
            f"{record.get('procs', '?'):>2}",
            f"load={record.get('read_s', '-'):>8}",
            f"graph={record.get('graph_s', '-'):>8}",
            f"solve={record.get('solve_s', '-'):>9}",
            f"peak={record.get('peak_rss_mb', '-'):>9}MB",
            f"maxk={cmax}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if not raw or raw[0] in ("-h", "--help"):
        parse_args(["run", "--help"])
        return 0
    # Preserve simple ``python stress/run_stress.py --graphs ...`` usage.
    if raw[0] not in ("run", "worker"):
        raw = ["run", *raw]
    args = parse_args(raw)

    if args.mode == "worker":
        return run_worker(args)

    args.results.mkdir(parents=True, exist_ok=True)
    graphs = resolve_graphs(args.graphs)
    if not graphs:
        raise SystemExit(
            f"no graph data found in {DATA}; see stress/stress.md for downloads"
        )

    print(f"graphs:   {', '.join(graphs)}")
    print(f"backends: {', '.join(args.backends)}")
    print(f"procs:    {', '.join(map(str, args.procs))}")
    print(f"resolution: global  min_k={args.min_k}  max_k={args.max_k}")
    print(f"repeat:   {args.repeat}  timeout: {args.timeout or 'none'}")
    print()

    results: list[dict] = []
    failures = 0
    for graph in graphs:
        for backend in args.backends:
            # The Python backend is single-process; procs only affects Rust.
            backend_procs = [1] if backend == "python" else args.procs
            if backend == "python" and args.procs != [1]:
                print(
                    "note: python backend is single-process; running procs=1 only",
                    file=sys.stderr,
                )
            for procs in backend_procs:
                for _ in range(args.repeat):
                    record = run_one(graph, backend, procs, args)
                    results.append(record)
                    print(summarise(record))
                    if record.get("status") == "invariant-fail":
                        failures += 1
                    elif record.get("status") == "error":
                        failures += 1
                    elif record.get("status") == "timeout" and args.fail_on_timeout:
                        failures += 1

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = args.results / f"run-{stamp}-{os.getpid()}.json"
    with open(out, "w") as fh:
        json.dump(results, fh, indent=4)
        fh.write("\n")
    print(f"\nwrote {out}")

    print("\nsummary")
    for record in results:
        print(summarise(record))

    if failures:
        print(f"\n{failures} failure(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
