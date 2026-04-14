import pytest
import networkx as nx
from pivoterpy import Pivoter

@pytest.fixture
def karate_data():
    """Generates the Karate Club graph in multiple formats."""
    G = nx.karate_club_graph()
    n = G.number_of_nodes()
    m = G.number_of_edges()
    
    adj_matrix = nx.to_numpy_array(G)

    edge_list = list(G.edges())
    
    return n, m, adj_matrix, edge_list

def test_adj(karate_data):
    n, m, adj_matrix, edge_list = karate_data
    
    G1 = Pivoter.from_adj_matrix(adj_matrix)

    assert G1.n == n

    assert G1.m == m

    assert G1.edges == set(edge_list)


def test_edges(karate_data):
    n, m, adj_matrix, edge_list = karate_data
    
    G2 = Pivoter.from_edge_list(edge_list, n)
    
    assert G2.n == n

    assert G2.m == m
    
    assert G2.edges == set(edge_list)