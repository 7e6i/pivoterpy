from random import random
from time import time
import pivoterpy as pvt

def graph(n, p):

    edges = []
    
    for i in range(n):
        for j in range(i+1, n):
            if random() < p:
                edges.append((i,j))

    return edges


def tests():
    n, p = 1000, .3
    procs = 4

    edges = graph(n, p)
    G = pvt.from_edge_list(edges, n)

    t0 = time()
    P = pvt.pivoter(G, backend="python", procs=procs)
    print(f"python: {time() - t0:.4f}")

    t0 = time()
    P = pvt.pivoter(G, backend="rust", procs=procs)
    print(f"rust: {time() - t0:.4f}")

    G.experimental = True
    t0 = time()
    P = pvt.pivoter(G, backend="rust", procs=procs)
    print(f"rust (exp): {time() - t0:.4f}")


if __name__ == "__main__":
    tests()