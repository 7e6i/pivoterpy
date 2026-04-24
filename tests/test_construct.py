# tests/test_construct.py

import pytest
import networkx as nx
import pivoterpy as pvt


@pytest.fixture
def karate_graph():
    """Generates the Karate Club graph and its normalized components."""
    K = nx.karate_club_graph()
    
    # Normalize edges so (u, v) always has u < v for strict equality checking
    norm_edges = { (u, v) if u < v else (v, u) for u, v in K.edges() }
    
    # Extract degrees ordered by node ID (0 to 33)
    degrees = [deg for node, deg in sorted(K.degree())]
    
    return K, norm_edges, degrees


def test_networkx(karate_graph):
    K, expected_edges, expected_degrees = karate_graph

    G = pvt.from_networkx(K)

    assert G.n == K.number_of_nodes()
    assert G.m == K.number_of_edges()
    
    # 1. Check exact topology
    assert set(G.edges) == expected_edges
    
    # 2. Check metadata
    assert G.degrees == expected_degrees


def test_adj_matrix(karate_graph):
    K, expected_edges, expected_degrees = karate_graph
    
    # Convert to dense matrix
    adj_matrix = nx.to_numpy_array(K).tolist()
    
    G = pvt.from_adj_matrix(adj_matrix)
    
    assert G.n == K.number_of_nodes()
    assert G.m == K.number_of_edges()
    assert set(G.edges) == expected_edges
    assert G.degrees == expected_degrees


def test_edge_list_standard(karate_graph):
    K, expected_edges, expected_degrees = karate_graph
    
    G = pvt.from_edge_list(list(K.edges()))
 
    assert G.n == K.number_of_nodes()
    assert G.m == K.number_of_edges()
    
    # --- TRANSLATE INTERNAL EDGES BACK TO ORIGINAL IDs ---
    unmapped_edges = set()
    for internal_u, internal_v in G.edges:
        orig_u = G.nodes[internal_u]
        orig_v = G.nodes[internal_v]
        
        # Re-normalize just to be safe
        norm = (orig_u, orig_v) if orig_u < orig_v else (orig_v, orig_u)
        unmapped_edges.add(norm)
        
    assert unmapped_edges == expected_edges
    
    # --- TRANSLATE INTERNAL DEGREES BACK TO ORIGINAL IDs ---
    unmapped_degrees = [0] * G.n
    for internal_id, deg in enumerate(G.degrees):
        orig_id = G.nodes[internal_id]
        unmapped_degrees[orig_id] = deg
        
    assert unmapped_degrees == expected_degrees 


def test_edge_list_mapping(karate_graph):
    """Proves that non-contiguous vertex IDs are correctly compressed."""
    K, _, _ = karate_graph
    
    # Corrupt the node IDs by multiplying them by 100 (e.g., node 1 becomes 100)
    messy_edges = [(u * 100, v * 100) for u, v in K.edges()]
    
    G = pvt.from_edge_list(messy_edges)
    
    # 1. Did it correctly compress back down to exactly 34 internal nodes?
    assert G.n == 34
    
    # 2. Did it store the original messy IDs in the translation array?
    expected_original_ids = sorted([n * 100 for n in K.nodes()])
    assert sorted(G.nodes) == expected_original_ids


def test_edge_list_self_loops():
    """Proves that the constructor correctly drops self-loops."""
    # Node 2 has a self-loop (2, 2)
    raw_edges = [(0, 1), (1, 2), (2, 2)]
    
    G = pvt.Graph.from_edge_list(raw_edges)
    
    assert G.n == 3
    assert G.m == 2  # The self-loop should be ignored!
    assert set(G.edges) == {(0, 1), (1, 2)}