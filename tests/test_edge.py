# tests/test_edge.py

import pytest
import networkx as nx
import pivoterpy as pvt

BACKENDS = ["python", "rust"]


@pytest.fixture
def complete_graph():
    """Generates K_5 complete graph."""
    n = 5
    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    
    # In K_5, every edge e has:
    # k=0: 0, k=1: 0, k=2: 1, k=3: 3 (triangles), k=4: 3, k=5: 1
    expected_e_counts = [0, 0, 1, 3, 3, 1]
    
    # The derived vertex counts should perfectly match the direct vertex engine
    expected_v_counts = [1, 1, 4, 6, 4, 1] 
    
    return edges, expected_e_counts, expected_v_counts


@pytest.fixture
def asymmetric_sparse_graph():
    """
    Original topology: Node 0 is a hub connected to 1, 2, and 3. Edge (1, 2) forms a triangle.
    Node 3 is a tail (degree 1) and participates in NO cliques k>=3.
    """
    edges = [(0, 1), (0, 2), (0, 3), (1, 2)]
    
    # Scramble the IDs to prove the translation layer correctly normalizes tuples (u, v)
    messy_edges = [(u * 10, v * 10) for u, v in edges]
    
    # We also flip one of the tuples to ensure (v, u) gets normalized to (u, v)
    messy_edges[0] = (10, 0) 
    
    return messy_edges


@pytest.fixture
def karate_graph():
    return list(nx.karate_club_graph().edges())


# --- THE TESTS ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_edge_symmetry(complete_graph, backend):
    """Proves that a mathematically perfect dense graph returns identical arrays for all edges."""
    edges, expected_e_counts, expected_v_counts = complete_graph
    G = pvt.Graph.from_edge_list(edges)

    P = pvt.pivoter(G, resolution="e", backend=backend)
    
    # 1. Did it return exactly 10 edges (10 choose 2)?
    assert len(P.edge_counts) == 10