# tests/test_pivoter.py
from pivoterpy import Pivoter

from random import random
from math import comb

def complete_graph(n):
    return [[1 for _ in range(n)] for _ in range(n)]

def erodos_reyni(n, p):
    return [[random() < p for _ in range(n)] for _ in range(n)]


def test_complete_graph():
    n = 10
    G = complete_graph(n)
    H = Pivoter.from_adj_matrix(G)
    assert H.n == n
    assert H.m == n*(n-1) // 2

    H.count(vertex=True)

    assert H.ec == H.global_ec == 1

    counts = [0]+[comb(n, i) for i in range(1, n+1)]
    assert H.clique_counts == counts

    counts = [0] + [comb(n-1, i) for i in range(n)]
    for i in range(n):
        assert H.vertex_clique_counts[i] == counts
    
    tol = 1e-6
    assert abs(H.ec - sum(H.curvatures)) < tol


def test_gnp():
    n, p = 10, 0.1
    G = erodos_reyni(n, p)

    H = Pivoter.from_adj_matrix(G)
    assert H.n == n
    
    H.count(vertex=True)
    assert H.ec == H.global_ec

    # TODO idk, K-S test for binomial distribution?

    tol = 1e-6
    assert abs(H.ec - sum(H.curvatures)) < tol


def test_rust():
    n = 10
    G = complete_graph(n)
    H = Pivoter.from_adj_matrix(G)

    H.count(vertex=True, rust=True)




if __name__ == '__main__':
    test_complete_graph()

    test_gnp()

    test_rust()