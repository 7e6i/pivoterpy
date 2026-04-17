import pytest
import networkx as nx
import pivoterpy as pvt


@pytest.fixture
def karate_graph():
    """Generates the Karate Club graph in multiple formats."""

    return nx.karate_club_graph()

def test_adj(karate_graph):
    K = karate_graph
    
    G = pvt.from_adj_matrix(nx.to_numpy_array(K))
    
    assert G.n == K.number_of_nodes()

    assert G.m == K.number_of_edges()

    assert set(G.edges) == K.edges()


def test_edges(karate_graph):
    K = karate_graph
    
    # technically not a list but whatever
    G = pvt.from_edge_list(K.edges())
 
    assert G.n == K.number_of_nodes()

    assert G.m == K.number_of_edges()

    assert set(G.edges) == K.edges()



def test_networkx(karate_graph):
    K = karate_graph

    G = pvt.from_networkx(K)

    assert G.n == K.number_of_nodes()

    assert G.m == K.number_of_edges()

    assert set(G.edges) == K.edges()
