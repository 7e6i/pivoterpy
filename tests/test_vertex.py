# tests/test_vertex.py

import pytest
import networkx as nx
import pivoterpy as pvt
from math import comb

BACKENDS = ["python", "rust"]


@pytest.fixture
def complete_graph():
    """Generates K_5 complete graph."""
    n = 5
    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    
    # In K_5, every vertex v has:
    # k=0: 1, k=1: 1, k=2: deg(4), k=3: 6, k=4: 4, k=5: 1
    expected_v_counts = [1, 1, 4, 6, 4, 1]
    expected_global = [1, 5, 10, 10, 5, 1]
    
    return edges, expected_v_counts, expected_global


@pytest.fixture
def asymmetric_sparse_graph():
    """
    A specific graph to test sparsity and ID translation.
    Original topology: Node 0 is a hub connected to 1, 2, and 3. Edge (1, 2) forms a triangle.
    Node 3 is a tail (degree 1) and participates in NO cliques k>=3.
    """
    edges = [(0, 1), (0, 2), (0, 3), (1, 2)]
    
    # Scramble the IDs to prove the translation layer works for vertex dictionaries
    messy_edges = [(u * 10, v * 10) for u, v in edges]
    return messy_edges


@pytest.fixture
def karate_graph():
    return list(nx.karate_club_graph().edges())


# --- THE TESTS ---

@pytest.mark.parametrize("backend", BACKENDS)
def test_complete_symmetry(complete_graph, backend):
    """Proves that a mathematically perfect dense graph returns identical arrays for all nodes."""
    edges, expected_v_counts, expected_global = complete_graph
    G = pvt.Graph.from_edge_list(edges)

    P = pvt.pivoter(G, resolution="v", backend=backend)
    
    # 1. Did it return exactly 5 keys?
    assert len(P.vertex_counts) == 5
    
    # 2. Are all arrays identical and correct?
    for v in range(5):
        assert P.vertex_counts[v] == expected_v_counts
        
    # 3. Did it properly derive the global counts?
    assert P.global_counts == expected_global


@pytest.mark.parametrize("backend", BACKENDS)
def test_sparse_dictionary(asymmetric_sparse_graph, backend):
    """
    Proves three things:
    1. The dictionary maps correctly back to original user IDs.
    2. Nodes with NO cliques are completely omitted from the dictionary (Memory Saver).
    3. Trailing zeros are stripped accurately per-vertex.
    """
    G = pvt.Graph.from_edge_list(asymmetric_sparse_graph)
    P = pvt.pivoter(G, resolution="v", backend=backend)

    # Node 30 (originally 3) has degree 1 and 0 triangles. 
    # It MUST be excluded from the sparse dictionary entirely.
    assert 30 not in P.vertex_counts
    
    # The dictionary should only contain the 3 nodes in the triangle
    assert len(P.vertex_counts) == 3

    # Node 0 (0) has degree 3, and 1 triangle
    assert P.vertex_counts[0] == [1, 1, 3, 1]
    
    # Nodes 10 and 20 have degree 2, and 1 triangle
    assert P.vertex_counts[10] == [1, 1, 2, 1]
    assert P.vertex_counts[20] == [1, 1, 2, 1]


@pytest.mark.parametrize("backend", BACKENDS)
def test_karate_global_derivation(karate_graph, backend):
    """
    Cross-validates the engine against itself. Proves that summing the 
    vertex counts dynamically derives the exact same array as the `global` resolution.
    """
    G = pvt.Graph.from_edge_list(karate_graph)

    # Run the ultra-fast global engine
    P_global = pvt.pivoter(G, resolution="g", backend=backend)
    
    # Run the vertex engine (which derives the global array via _coarser_counts)
    P_vertex = pvt.pivoter(G, resolution="v", backend=backend)

    # Assert the mathematically derived global matches the direct global
    assert P_vertex.global_counts == P_global.global_counts


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("min_k, max_k, expected", [
    (None, None, [1, 1, 4, 6, 4, 1]),       # Default
    (4, None,    [0, 0, 0, 0, 4, 1]),       # Min prune (zero pads 0-3)
    (None, 3,    [1, 1, 4, 6]),             # Max prune (truncates)
    (3, 4,       [0, 0, 0, 6, 4]),          # Targeted window
    (4, 4,       [0, 0, 0, 0, 4]),          # Exact order
    (4, 5,       [0, 0, 0, 0, 4, 1]),       # Above max clique (strips trailing zeros)
])
def test_vertex_slices(complete_graph, backend, min_k, max_k, expected):
    """Tests combinatorial slicing boundaries specifically applied to vertex dictionaries."""
    edges, _, _ = complete_graph
    G = pvt.Graph.from_edge_list(edges)

    P = pvt.pivoter(G, resolution="v", min_k=min_k, max_k=max_k, backend=backend)
    
    # Verify the bounds logic was correctly mapped to the inner dictionary values
    # (Checking node 0 is sufficient due to K_5 symmetry)
    if min_k == 6:
        # If min_k is mathematically higher than the max clique, the dict should be empty!
        assert len(P.vertex_counts) == 0
    else:
        assert P.vertex_counts[0] == expected