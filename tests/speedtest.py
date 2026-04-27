import random
from time import time
import pivoterpy as pvt



def read_file(filename):
    with open(filename, 'r') as f:
        # 1. Iterating directly over `f` avoids the memory spike of readlines()
        # 2. List comprehension avoids .append() overhead
        # 3. .split() automatically ignores trailing newlines/whitespace
        return [
            tuple(map(int, line.split()))
            for line in f 
            if not line.startswith('#')
        ]

def main():
    files = ['com-dblp', 'as-skitter', 'com-lj', 'com-orkut']
    # cant do com-orkut

    t0 = time()
    edges = read_file(f'tests/{files[2]}.edges')
    print(f"disk: {time() - t0:.3f}")

    t0 = time()
    G = pvt.from_edge_list(edges)
    print(f"graph: {time() - t0:.3f}")


    for k in range(6,1000000):
        t0 = time()
        P = pvt.pivoter(G, procs=8, min_k=k, max_k=k)
        tc = time() - t0
        num = P.global_counts[-1]
        if not num:
            break
        print(f'{k},{round(tc,3):.3f},{num}')



if __name__ == "__main__":
    main()


# disk: 52.938
# graph: 152.907
# 0,0.036,1
# 1,0.035,3072441
# 2,0.035,117185083
# 
# 