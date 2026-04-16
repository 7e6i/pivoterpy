import pytest
import networkx as nx
import pivoterpy as pvt
from math import comb
from time import time
from random import random

@pytest.fixture
def complete_graph():
    n = 200
    edges = [(i,j) for i in range(n) for j in range(i+1, n)]
    counts = [comb(n, i) for i in range(n+1)]
    return n, edges, counts


@pytest.fixture
def random_graph():
    n = 100
    p = 0.7

    edges = []
    for i in range(n):
        for j in range(i+1, n):
            if random() < p:
                edges.append((i,j))

    return n, edges, None




def test_rust_complete(complete_graph):
    n, edges, counts = complete_graph
    G = pvt.from_edge_list(edges)
    target = 10

    print("\nRust complete graph timings")

    t0 = time()
    P = pvt.pivoter(G)
    tc = f'{time() - t0:.4f}'
    print(tc)

    t0 = time()
    P = pvt.pivoter(G, min_k=target)
    tc = f'{time() - t0:.4f}'
    print(tc)

    t0 = time()
    P = pvt.pivoter(G, max_k=target)
    tc = f'{time() - t0:.4f}'
    print(tc)

    t0 = time()
    P = pvt.pivoter(G, min_k=target, max_k=target)
    tc = f'{time() - t0:.4f}'
    print(tc)



def test_rust_random(random_graph):
    n, edges, counts = random_graph
    G = pvt.from_edge_list(edges)
    target = 100

    print("\nRust random graph timings")

    t0 = time()
    P = pvt.pivoter(G)
    tc = f'{time() - t0:.4f}'
    print(tc)

    t0 = time()
    P = pvt.pivoter(G, min_k=target)
    tc = f'{time() - t0:.4f}'
    print(tc)

    t0 = time()
    P = pvt.pivoter(G, max_k=target)
    tc = f'{time() - t0:.4f}'
    print(tc)

    t0 = time()
    P = pvt.pivoter(G, min_k=target, max_k=target)
    tc = f'{time() - t0:.4f}'
    print(tc)



# def test_python_karate(karate_graph):
#     n, edges, counts = karate_graph
#     G = pvt.from_edge_list(edges)

#     P = pvt.pivoter(G)
#     assert P.global_counts == counts
    
#     for i in range(n+1):
#         P = pvt.pivoter(G, min_k=i)
#         assert P.global_counts == [0]*i + counts[i:]

#     for i in range(n+1):
#         P = pvt.pivoter(G, max_k=i)
#         assert P.global_counts == counts[:i+1]

#     for i in range(n+1):
#         for j in range(i, n+1):
#             P = pvt.pivoter(G, min_k=i, max_k=j)
#             assert P.global_counts == [0]*i + counts[i:j+1]



# def test_python_karate2(karate_graph):
#     n, edges, counts = karate_graph
#     G = pvt.from_edge_list(edges)

#     P = pvt.pivoter(G, min_k=5, max_k=5)
#     print(P.global_counts)
