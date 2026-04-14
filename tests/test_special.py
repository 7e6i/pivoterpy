import pytest
from pivoterpy import Pivoter
from math import comb

@pytest.fixture
def complete_graph(request):
    """
    Generates a complete graph dynamically. 
    The number of nodes is passed via request.param.
    """
    nodes = request.param
    edges = [(i, j) for i in range(nodes) for j in range(i+1, nodes)]
    return nodes, edges


# Use parametrize with indirect=True to pass 300 into the fixture
@pytest.mark.parametrize("complete_graph", [300], indirect=True)
def test_rust_limit(complete_graph):
    """comb(300,150) is 88 bits, checks if rust actually works"""
    nodes, edges = complete_graph
    
    G = Pivoter.from_edge_list(edges)
    G.count(rust=True, procs=4)

    # Theoretical global counts: comb(N, k)
    result = [0] + [comb(nodes, i) for i in range(1, nodes+1)]

    assert G.global_counts == result


# Use parametrize with indirect=True to pass 10 into the fixture
@pytest.mark.parametrize("complete_graph", [5], indirect=True)
def test_python_edges(complete_graph):
    """Checks if the python implementation works for edge counts."""
    nodes, edges = complete_graph
    
    G = Pivoter.from_edge_list(edges)
    G.count(edge=True) 


    # 1. Theoretical Edge Counts
    # In a complete graph, an edge (size 2) needs (k - 2) more nodes to form a k-clique.
    # It draws these from the remaining (N - 2) nodes.
    # Therefore, every edge is in exactly comb(N - 2, k - 2) cliques of size k.
    expected_edge_counts = [0, 0] + [comb(nodes - 2, k - 2) for k in range(2, nodes + 1)]

    # 2. Check that the correct number of edges was tracked
    # For a complete graph, there are exactly comb(N, 2) edges.
    assert len(G.edge_counts) == comb(nodes, 2)

    # 3. Check that every single edge perfectly matches the theoretical array
    for e, counts in G.edge_counts.items():
        assert counts == expected_edge_counts