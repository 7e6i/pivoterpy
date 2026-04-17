import pytest
import networkx as nx
import pivoterpy as pvt
from math import comb

BACKENDS = ["python", "rust"]


@pytest.fixture
def complete_graph():
    n = 7
    edges = [(i,j) for i in range(n) for j in range(i+1, n)]
    counts = [comb(n, i) for i in range(n+1)]
    return n, edges, counts


@pytest.fixture
def karate_graph():
    edges = nx.karate_club_graph().edges()
    counts = [1, 34, 78, 45, 11, 2]
    return 34, edges, counts


def test_singleton():
    n, edges, counts = 2, [(0,1)], [1,2,1]
    G = pvt.from_edge_list(edges, n=n)

    P = pvt.pivoter(G)
    assert P.global_counts == counts
    
    for i in range(n+1):
        P = pvt.pivoter(G, min_k=i)
        assert P.global_counts == [0]*i + counts[i:]

    for i in range(n+1):
        P = pvt.pivoter(G, max_k=i)
        assert P.global_counts == counts[:i+1]

    for i in range(n+1):
        for j in range(i, n+1):
            P = pvt.pivoter(G, min_k=i, max_k=j)
            assert P.global_counts == [0]*i + counts[i:j+1]


def test_complete(complete_graph):
    n, edges, counts = complete_graph
    G = pvt.from_edge_list(edges)

    for backend in BACKENDS:

        P = pvt.pivoter(G)
        assert P.global_counts == counts
        
        for i in range(n+1):
            P = pvt.pivoter(G, min_k=i, backend=backend)
            assert P.global_counts == [0]*i + counts[i:]

        for i in range(n+1):
            P = pvt.pivoter(G, max_k=i, backend=backend)
            assert P.global_counts == counts[:i+1]

        for i in range(n+1):
            for j in range(i, n+1):
                P = pvt.pivoter(G, min_k=i, max_k=j, backend=backend)
                assert P.global_counts == [0]*i + counts[i:j+1]


def test_python_karate(karate_graph):
    n, edges, counts = karate_graph
    G = pvt.from_edge_list(edges)

    for backend in BACKENDS:

        P = pvt.pivoter(G)
        assert P.global_counts == counts
        
        for i in range(n+1):
            P = pvt.pivoter(G, min_k=i, backend=backend)
            assert P.global_counts == [0]*i + counts[i:]

        for i in range(n+1):
            P = pvt.pivoter(G, max_k=i, backend=backend)
            assert P.global_counts == counts[:i+1]

        for i in range(n+1):
            for j in range(i, n+1):
                P = pvt.pivoter(G, min_k=i, max_k=j, backend=backend)
                assert P.global_counts == [0]*i + counts[i:j+1]

