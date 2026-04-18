import random
import pivoterpy as pvt


def graph(n, p):

    edges = []
    
    for i in range(n):
        for j in range(i+1, n):
            if random.random() < p:
                edges.append((i,j))

    return edges, n


def test():

    edges, n = graph(10, 1)
    G = pvt.from_edge_list(edges,n=n)

    P = pvt.pivoter(G, backend="cuda")
    #print(P.global_counts)
    

if __name__ == "__main__":
    test()