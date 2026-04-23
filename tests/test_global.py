# tests/test_global.py

import pytest
import networkx as nx
import pivoterpy as pvt
from math import comb

BACKENDS = ["python", "rust"]


@pytest.fixture
def complete_graph():
    """Generates K_7 complete graph."""
    n = 7
    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    counts = [comb(n, i) for i in range(n + 1)]
    return n, edges, counts


@pytest.fixture
def karate_graph():
    """Generates the Karate Club graph. Max clique size is 5."""
    edges = list(nx.karate_club_graph().edges())
    counts = [1, 34, 78, 45, 11, 2]
    return 34, edges, counts


# --- THE TESTS ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_singleton(backend):
    """Tests extreme contiguous ID compression and base trivial counts."""
    # Using 1e100 proves the Graph object successfully compresses massive ID gaps
    n, edges, counts = 2, [(0, int(1e100))], [1, 2, 1]
    G = pvt.from_edge_list(edges)

    P = pvt.pivoter(G, backend=backend)
    assert P.global_counts == counts
    
    # Since N=2, this nested loop only runs 6 times. Perfectly fine.
    for i in range(n + 1):
        for j in range(i, n + 1):
            P = pvt.pivoter(G, min_k=i, max_k=j, backend=backend)
            assert P.global_counts == [0] * i + counts[i : j + 1]


@pytest.mark.parametrize("backend", BACKENDS)
def test_complete(complete_graph, backend):
    """Tests a dense graph where every possible combination is a clique."""
    n, edges, counts = complete_graph
    G = pvt.from_edge_list(edges)

    # 1. Default Run
    P = pvt.pivoter(G, backend=backend)
    assert P.global_counts == counts
    
    # 2. Test Min K only
    for i in range(n + 1):
        P = pvt.pivoter(G, min_k=i, backend=backend)
        assert P.global_counts == [0] * i + counts[i:]

    # 3. Test Max K only
    for i in range(n + 1):
        P = pvt.pivoter(G, max_k=i, backend=backend)
        assert P.global_counts == counts[: i + 1]


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("min_k, max_k, expected", [
    # (min_k, max_k, expected_array)
    (None, None, [1, 34, 78, 45, 11, 2]),       # Default
    (4, None,    [0, 0, 0, 0, 11, 2]),          # Min prune
    (None, 3,    [1, 34, 78, 45]),              # Max prune
    (3, 4,       [0, 0, 0, 45, 11]),            # Targeted window
    (4, 4,       [0, 0, 0, 0, 11]),             # Exact order
    (6, 8,       [0, 0, 0, 0, 0, 0]),  # Above max clique (should zero-pad)
])
def test_karate_slices(karate_graph, backend, min_k, max_k, expected):
    """
    Tests specific combinatorial slicing boundaries on a real-world sparse graph
    without doing 600+ redundant DFS runs.
    """
    _, edges, _ = karate_graph
    G = pvt.from_edge_list(edges)

    P = pvt.pivoter(G, min_k=min_k, max_k=max_k, backend=backend)
    
    assert P.global_counts == expected