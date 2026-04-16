import pytest
import networkx as nx
import pivoterpy as pvt
from math import comb


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
    return edges, counts, len(counts)+1


def test_python_singleton():
    n, edges, counts = 1, [], [1,1]
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


def test_python_complete(complete_graph):
    n, edges, counts = complete_graph
    G = pvt.from_edge_list(edges)

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


def test_python_karate(karate_graph):
    edges, counts, n = karate_graph
    G = pvt.from_edge_list(edges)

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


# def test_rust(karate_graph):

#     # single threaded (not really though)
#     G = Pivoter.from_edge_list(karate_graph)
#     G.count(rust=True)

#     assert G.global_ec == EC
#     assert G.global_counts == COUNTS
#     assert G.vertex_counts == G.curvatures == G.edge_counts == None


#     # multi-threaded
#     G = Pivoter.from_edge_list(karate_graph)
#     G.count(procs=2, rust=True)

#     assert G.global_ec == EC
#     assert G.global_counts == COUNTS
#     assert G.vertex_counts == G.curvatures == G.edge_counts == None
