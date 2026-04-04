# tests/test_pivoter.py
from pivoterpy import Pivoter

from time import time
from random import random
from math import comb

def complete_graph(n):
    return [[1 for _ in range(n)] for _ in range(n)]

def erodos_reyni(n, p):
    return [[random() < p for _ in range(n)] for _ in range(n)]
    
def timer():

    inits = []
    times = []

    for _ in range(10):

        #G = complete_graph(200)
        G = erodos_reyni(1000, .1)

        t0 = time()
        H = Pivoter.from_adj_matrix(G)
        t = time() - t0
        inits.append(t)
        print(f'{t:.4f}s,', end=' ')

        t0 = time()
        H.count(get_curv=True)
        t = time() - t0
        times.append(t)
        print(f'{_+1}: {t:.4f}s')


    print(f'Inits {sum(inits)/len(inits):.2f}s')
    print(f'Counts {sum(times)/len(times):.2f}s')
    print(H.ec, H.max_k)
    print(H.clique_counts)


def test_complete_graph():
    n = 10
    G = complete_graph(n)
    H = Pivoter.from_adj_matrix(G)
    assert H.n == n
    assert H.m == n*(n-1) // 2

    H.count(get_curv=True)

    assert H.ec == H.global_ec == 1

    counts = [0]+[comb(n, i) for i in range(1, n+1)]
    assert H.clique_counts == H.global_counts == counts

    counts = [0] + [comb(n-1, i) for i in range(n)]
    for i in range(n):
        assert H.vertex_counts[i] == H.vertex_clique_counts[i] == counts
    
    tol = 1e-6
    assert abs(H.ec - sum(H.curvatures)) < tol and abs(H.ec - sum(H.vertex_curv)) < tol

if __name__ == '__main__':
    test_complete_graph()

    timer()