import pytest
import networkx as nx
from pivoterpy import Pivoter

COUNTS = [[0, 1, 16, 18, 7, 2], [0, 1, 9, 12, 7, 2], [0, 1, 10, 11, 7, 2], [0, 1, 6, 10, 7, 2], [0, 1, 3, 2], [0, 1, 4, 3], [0, 1, 4, 3], [0, 1, 4, 6, 4, 1], [0, 1, 5, 5, 1], [0, 1, 2], [0, 1, 3, 2], [0, 1, 1], [0, 1, 2, 1], [0, 1, 5, 6, 4, 1], [0, 1, 2, 1], [0, 1, 2, 1], [0, 1, 2, 1], [0, 1, 2, 1], [0, 1, 2, 1], [0, 1, 3, 1], [0, 1, 2, 1], [0, 1, 2, 1], [0, 1, 2, 1], [0, 1, 5, 4, 1], [0, 1, 3, 1], [0, 1, 3, 1], [0, 1, 2, 1], [0, 1, 4, 1], [0, 1, 3, 1], [0, 1, 4, 4, 1], [0, 1, 4, 3, 1], [0, 1, 6, 3], [0, 1, 12, 13, 2], [0, 1, 17, 15, 2]]

EC = [-2.35, -0.85, -1.6833333333333336, -0.016666666666666496, 0.16666666666666663, 0.0, 0.0, 0.2, -0.08333333333333326, 0.0, 0.16666666666666663, 0.5, 0.3333333333333333, -0.3, 0.3333333333333333, 0.3333333333333333, 0.3333333333333333, 0.3333333333333333, 0.3333333333333333, -0.16666666666666669, 0.3333333333333333, 0.3333333333333333, 0.3333333333333333, -0.41666666666666674, -0.16666666666666669, -0.16666666666666669, 0.3333333333333333, -0.6666666666666667, -0.16666666666666669, 0.08333333333333326, -0.25, -1.0, -1.166666666666667, -3.0]


@pytest.fixture
def karate_data():
    """Generates the Karate Club graph in multiple formats."""
    G = nx.karate_club_graph()
    
    return list(G.edges())


def test_python(karate_data):

    # single threaded
    G = Pivoter.from_edge_list(karate_data)
    G.count(vertex=True)

    for u, v in zip(G.vertex_counts, COUNTS):
        assert u == v

    for c1, c2 in zip(G.curvatures, EC):
        assert c1 == pytest.approx(c2)

    assert G.global_ec == pytest.approx(sum(G.curvatures))
    assert G.edge_counts == None


    # multi-threaded
    G = Pivoter.from_edge_list(karate_data)
    G.count(vertex=True, procs=2)

    for u,v in zip(G.vertex_counts, COUNTS):
        assert u == v

    for c1, c2 in zip(G.curvatures, EC):
        assert c1 == pytest.approx(c2)

    assert G.global_ec == sum(G.curvatures)
    assert G.edge_counts == None


def test_rust(karate_data):

    # single threaded
    G = Pivoter.from_edge_list(karate_data)
    G.count(vertex=True, rust=True)

    for u, v in zip(G.vertex_counts, COUNTS):
        assert u == v

    for c1, c2 in zip(G.curvatures, EC):
        assert c1 == pytest.approx(c2)

    assert G.global_ec == pytest.approx(sum(G.curvatures))
    assert G.edge_counts == None


    # multi-threaded
    G = Pivoter.from_edge_list(karate_data)
    G.count(vertex=True, procs=2)

    for u,v in zip(G.vertex_counts, COUNTS):
        assert u == v

    for c1, c2 in zip(G.curvatures, EC):
        assert c1 == pytest.approx(c2)

    assert G.global_ec == sum(G.curvatures)
    assert G.edge_counts == None