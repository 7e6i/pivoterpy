
from time import time
from random import random
from pivoterpy import Pivoter

def complete_graph(n):
    return [[1 for _ in range(n)] for _ in range(n)]

def erodos_reyni(n, p):
    return [[random() < p for _ in range(n)] for _ in range(n)]


    
def timer():

    inits = []
    times = []

    for _ in range(10):

        #G = complete_graph(800)
        G = erodos_reyni(250, .5)

        t0 = time()
        H = Pivoter.from_adj_matrix(G)
        t = time() - t0
        inits.append(t)
        print(f'{t:.4f}s,', end=' ')

        t0 = time()
        H.count(procs=None, rust=False)
        t = time() - t0
        times.append(t)
        print(f'{_+1}: {t:.4f}s')


    print(f'Inits {sum(inits)/len(inits):.2f}s')
    print(f'Counts {sum(times)/len(times):.2f}s')
    print(H.ec)
    #print(H.clique_counts)


timer()