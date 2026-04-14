import pytest
import networkx as nx
from pivoterpy import Pivoter

COUNTS = [0, 34, 78, 45, 11, 2]
EC = -8

@pytest.fixture
def karate_data():
    """Generates the Karate Club graph in multiple formats."""
    G = nx.karate_club_graph()
    
    return list(G.edges())


def test_python(karate_data):
  
    # single threaded
    G = Pivoter.from_edge_list(karate_data)
    G.count()

    assert G.global_ec == EC
    assert G.global_counts == COUNTS
    assert G.vertex_counts == G.curvatures == G.edge_counts == None


    # multi-threaded
    G = Pivoter.from_edge_list(karate_data)
    G.count(procs=2)

    assert G.global_ec == EC
    assert G.global_counts == COUNTS
    assert G.vertex_counts == G.curvatures == G.edge_counts == None


def test_rust(karate_data):

    # single threaded (not really though)
    G = Pivoter.from_edge_list(karate_data)
    G.count(rust=True)

    assert G.global_ec == EC
    assert G.global_counts == COUNTS
    assert G.vertex_counts == G.curvatures == G.edge_counts == None


    # multi-threaded
    G = Pivoter.from_edge_list(karate_data)
    G.count(procs=2, rust=True)

    assert G.global_ec == EC
    assert G.global_counts == COUNTS
    assert G.vertex_counts == G.curvatures == G.edge_counts == None
