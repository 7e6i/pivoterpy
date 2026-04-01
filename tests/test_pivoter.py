# tests/test_pivoter.py
from time import time

from pivoterpy import Pivoter
from statistics import stdev, mean



def complete_graph(n):

    return [[1 for _ in range(n)] for _ in range(n)]
    
def timer():

    times = []

    for _ in range(1):

        t0 = time()
        G = complete_graph(1000)
        
        pivoter = Pivoter('adj', G)
        #pivoter.count_cliques()
        pivoter.count_cliques_mp(procs=8)

        t = time() - t0
        times.append(t)
        print(f'Trial {_+1} took {t:.4f} seconds')

    print(f'Mean {sum(times)/len(times):.4f}')

if __name__ == '__main__':
    timer()