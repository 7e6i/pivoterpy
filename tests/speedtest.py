import random
from time import time
import pivoterpy as pvt



def read_file(filename):
    edges = []
    with open(filename) as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if line.startswith('#'):
            continue
        else:
            edges.append(tuple(map(int, line.split())))
    return edges


def main():
    files = ['com-dblp', 'as-skitter']
    edges = read_file(f'tests/{files[0]}.edges')


    G = pvt.from_edge_list(edges)
    print("loaded graph")

    t0 = time()
    P = pvt.pivoter(G, procs=10, backend='rust')#, min_k=11, max_k=11)
    print(f'{time() - t0:.3f} seconds')

    print(P.global_counts)



if __name__ == "__main__":
    main()

