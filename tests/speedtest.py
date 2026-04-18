import random
from time import time
import pivoterpy as pvt

def graph(n, p):

    edges = []
    
    for i in range(n):
        for j in range(i+1, n):
            if random.random() < p:
                edges.append((i,j))

    return edges, n

import random
from itertools import combinations

def monster_core_graph(core_size=60, periphery_size=5000, p_edges=2):
    """
    Generates a graph with extreme load imbalance.
    - core_size: Number of nodes in the fully connected central core.
    - periphery_size: Number of nodes in the sparse outer halo.
    - p_edges: How many core nodes each peripheral node connects to.
    """
    edges = []
    
    # 1. The Monster Core (Fully connected)
    # This will cause a massive combinatorial explosion for a few specific roots
    core_nodes = list(range(core_size))
    edges.extend(combinations(core_nodes, 2))
    
    # 2. The Sparse Periphery
    # Thousands of nodes that will pass the k-core threshold but finish instantly
    for i in range(core_size, core_size + periphery_size):
        # Connect each peripheral node to a few random core nodes
        targets = random.sample(core_nodes, p_edges)
        for t in targets:
            edges.append((i, t))
            
    # Add a little noise so the core isn't mathematically perfect 
    # (Forces the DFS to do actual work instead of just jumping to the nCr leaf)
    edges = [e for e in edges if random.random() > 0.05]
            
    n = core_size + periphery_size
    return edges, n



def test():
    procs = 8

    times = []
    times2 = []
    for i in range(5):
        edges, n = graph(5000, 0.05)
        #edges, n = monster_core_graph(core_size=70, periphery_size=500, p_edges=2)
        G = pvt.from_edge_list(edges, n)

        t0 = time()
        #P = pvt.pivoter(G, backend="python", procs=procs)
        print(f"python: {time() - t0:.4f}")


        t0 = time()
        P = pvt.pivoter(G, backend="rust", procs=procs)
        print(f"rust: {time() - t0:.4f}"); times.append(time() - t0)

        G.experimental = True
        t0 = time()
        P = pvt.pivoter(G, backend="rust", procs=procs)
        print(f"rust (exp): {time() - t0:.4f}"); times2.append(time() - t0)

    print(sum(times)/len(times))
    print(sum(times2)/len(times2))


if __name__ == "__main__":
    test()


# results

# 8 procs, G(n=1000,p=0.35)
# level 0 compression, level 1 threading, 12.97 sec
# level 2 compression, level 2 threading, 6.05 sec

# experimental is slower for especially sparse graphs