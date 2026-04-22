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
    edges = read_file('tests/com-dblp.ungraph.txt')


    G = pvt.from_edge_list(edges)


    t0 = time()
    P = pvt.pivoter(G, procs=8, backend='rust', max_k=10)
    print(f'{time() - t0:.3f} seconds')

    print(len(P.global_counts)-1)



if __name__ == "__main__":
    main()

