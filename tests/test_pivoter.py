# tests/test_pivoter.py
from pivoterpy import Pivoter

from time import time
from random import random


def complete_graph(n):
    return [[1 for _ in range(n)] for _ in range(n)]

def erodos_reyni(n, p):
    return [[random() < p for _ in range(n)] for _ in range(n)]
    
def timer():

    times = []

    for _ in range(1):

        
        G = complete_graph(30)
        #G = erodos_reyni(100, .05)
        
        
        pivoter = Pivoter.from_adj_matrix(G)
        t0 = time()
        pivoter.count()
        

        t = time() - t0
        times.append(t)
        print(f'Trial {_+1} took {t:.4f} seconds')

        print(pivoter.global_ec)
        print(pivoter.global_counts)
        #rint(pivoter.vertex_curv)
        #print(pivoter.vertex_counts)


    print(f'Mean {sum(times)/len(times):.4f}')

if __name__ == '__main__':
    timer()