from math import comb
from multiprocessing import Pool

class SCTnode:
    def __init__(self, label, ph_cnt, call_type="h"):
        self.label = label
        p,h = ph_cnt
        if call_type == "p": self.ph_cnt = (p+1, h)
        elif call_type == "h": self.ph_cnt = (p, h+1)

    def __repr__(self):
        return f"SCT{str(self.label)} {str(self.ph_cnt)}"


class Pivoter:
    '''
    Initialize pivoter object
    - mode=adj: n x n adjacency matrix, only reads upper triangle
    - mode=edge: m x 2 array of edges (u,v) where u<v, u in {0,...,n-1}
    - mode=file: read edge array from file
    '''
    def __init__(self, mode, array=None, file_name=None, sep=" "):
        # n x n array, will only check upper triangle
        if mode == "adj":
            self._from_adj_arr(array)

        # m x 2 array, (u,v) where u<v
        elif mode == "edge":
            self._from_edge_arr(array)

        elif mode == "file":
            self._from_edge_file(file_name, sep)

    def _from_adj_arr(self, arr):
        assert len(arr) == len(arr[0])
        edges, n, m = [], len(arr), 0
        for i in range(n):
            for j in range(i+1, n):
                if arr[i][j] == 1:
                    edges.append((i,j))
                    m+=1
        self.n, self.m, self.edges = n, m, edges

    def _from_edge_arr(self, arr):
        nodes, m = set(), len(arr)
        for i in range(m):
            u, v = arr[i][0], arr[i][1]
            assert u < v
            nodes.update([u,v])
        self.edges, self.n, self.m = arr, len(nodes), m

    def _from_edge_file(self, file_name, sep):
        edges, nodes = [], set()
        with open(file_name, 'r') as f:
            for line in f:
                u, v = map(int, line.strip().split(sep))
                assert u < v
                edges.append((u,v))
                nodes.update([u,v])
        self.edges, self.n, self.m = edges, len(nodes), len(edges)


    # calculate neighborhoods, degrees, and nodes by degree
    def _setup(self):
        self.neighborhoods = [set() for _ in range(self.n)]
        self.degrees = [0 for _ in range(self.n)]

        for edge in self.edges:
            # neighborhood of nodes
            self.neighborhoods[edge[0]].add(edge[1])
            self.neighborhoods[edge[1]].add(edge[0])

            # degrees of nodes
            self.degrees[edge[0]] += 1
            self.degrees[edge[1]] += 1

        # list of vertices by degree
        self.by_degrees = [set() for _ in range(self.n)]
        for i in range(self.n):
            self.by_degrees[self.degrees[i]].add(i)
        
    def _degeneracy_ordering(self):
        # node v is at the rth position in the ordering: L1[r]=v, L2[v]=r 
        L1, L2 = [], [None for _ in range(self.n)]
        by_degrees = self.by_degrees[:]
        degrees = self.degrees[:]

        rank, k = 0, 0
        # loop through nodes
        for _ in range(self.n):
            # find the node with lowest degree
            for i in range(self.n):
                if by_degrees[i]: break
                
            # update k, update v, change L1/L2 accordingly
            k = max(k, i)
            v = by_degrees[i].pop()
            L1.append(v); L2[v] = rank; rank += 1
            degrees[v] = -1

            # update w in N(v)\L
            for w in self.neighborhoods[v]:
                if degrees[w] == -1:
                    continue

                by_degrees[degrees[w]].remove(w)
                degrees[w] -= 1
                by_degrees[degrees[w]].add(w)

        self.degeneracy = k
        self.node_by_degen_order = L1
        self.degen_order_by_node = L2


    def _degeneracy_neighborhoods(self):
        degen_order_nbhds = [] # arr[v] = N^+(v)
        for v in range(self.n):
            rank = self.degen_order_by_node[v]
            later_nodes = set([u for u in self.node_by_degen_order[rank+1:]])
            v_nbhd = self.neighborhoods[v]

            degen_order_nbhds.append(later_nodes & v_nbhd) # set intersection

        self.degen_order_nbhds = degen_order_nbhds

    '''
    helper functions
    '''
    def _count_clique_setup(self):
        self._setup()
        self._degeneracy_ordering()
        self._degeneracy_neighborhoods()

    def _trim_counts(self):
        for i in range(self.n, -1, -1): 
            if self.clique_counts[i] > 0: break
        self.clique_counts = self.clique_counts[1:i+1]

    def _choose_pivot(self, S):
        pivot, max_nbdh = None, -1
        for v in S:
            nbhd = self.neighborhoods[v]
            size = len(nbhd & S)
            if size > max_nbdh: max_nbdh, pivot = size, v
        return pivot


    '''
    serial implementation
    - helpful to learn how the algorithm works
    - good starting point to implement node/edge specific counts
    '''
    def count_cliques(self):
        self._count_clique_setup()

        self.ec = 0
        self.clique_counts = [0 for _ in range(self.n+1)]

        # loop through nodes
        for v in range(self.n):
            node = SCTnode(label=self.degen_order_nbhds[v], ph_cnt = (0,0))
            self._count_cliques_rec(node)

        self._trim_counts()
        return self.ec, self.clique_counts

    def _count_cliques_rec(self, parent):
        # if parent.label is empty, update self.clique_counts, return
        if not parent.label:
            p,h = parent.ph_cnt
            for i in range(0, p+1):
                self.clique_counts[h+i] += comb(p, i)
                self.ec += pow(-1, h+i+1)* comb(p, i)
            return

        # find pivot and recurse
        pivot = self._choose_pivot(parent.label)
        label = parent.label & self.neighborhoods[pivot]
        pNode = SCTnode(label, parent.ph_cnt, call_type="p")
        self._count_cliques_rec(pNode)

        # loop through hold nodes and recurse
        hNodes = list(parent.label - (self.neighborhoods[pivot] | {pivot}))
        for i in range(len(hNodes)):
            label = (parent.label & self.neighborhoods[hNodes[i]]) - set(hNodes[:i])
            hNode = SCTnode(label, parent.ph_cnt)
            self._count_cliques_rec(hNode)

    
    '''
    parallelized implementation of count_cliques
    '''
    def count_cliques_mp(self, procs=1):
        self._count_clique_setup()

        self.ec = 0
        self.clique_counts = [0 for _ in range(self.n+1)]
        nodes = [SCTnode(self.degen_order_nbhds[v], (0,0)) for v in range(self.n)]
        
        with Pool(processes=procs) as pool:
            results = pool.map(self._cnt_clq_mp_wrap, nodes)

        for r in results:
            ec, counts = r
            self.ec += ec
            for i in range(self.n+1):
                self.clique_counts[i] += counts[i]

        self._trim_counts()
    
    # needed to keep track of clique frequencies
    # takes advantage of multiproc copy on write rule when spawning subprocesses
    def _cnt_clq_mp_wrap(self, parent):
        self.clique_counts = [0 for _ in range(self.n+1)]
        self.ec = 0
        self._cnt_clq_mp_rec(parent)
        return self.ec, self.clique_counts

    def _cnt_clq_mp_rec(self, parent):
        # if parent.label is empty, update self.clique_counts, return
        if not parent.label:
            p,h = parent.ph_cnt
            for i in range(0, p+1):
                ncr = comb(p, i)
                self.ec += pow(-1, h+i+1)* ncr
                self.clique_counts[h+i] += ncr
            return

        # find pivot and recurse
        pivot = self._choose_pivot(parent.label)
        label = parent.label & self.neighborhoods[pivot]
        pNode = SCTnode(label, parent.ph_cnt, call_type="p")
        self._cnt_clq_mp_rec(pNode)

        # loop through hold nodes and recurse
        hNodes = list(parent.label - (self.neighborhoods[pivot] | {pivot}))
        for i in range(len(hNodes)):
            label = (parent.label & self.neighborhoods[hNodes[i]]) - set(hNodes[:i])
            hNode = SCTnode(label, parent.ph_cnt)     
            self._cnt_clq_mp_rec(hNode)


    

'''
example usage
'''
def main():
    n, rr = 100, .15
    # takes a few seconds depending on cpu

    # construct adjacency matrix (only care about upper triangle)
    arr = [[0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i+1,n):
                arr[i][j] = 1 if random() < rr else 0
                arr[j][i] = arr[i][j]

    # serial implementation
    t0 = time()
    p = Pivoter("adj", arr)
    p.count_cliques()
    print(p.ec, p.clique_counts)
    print(f'{time()-t0:.2f} seconds')

    # parallelized implementation
    # (will take longer for smaller/sparse graphs)
    t0 = time()
    p = Pivoter("adj", arr)
    p.count_cliques_mp(procs=2)
    print(p.ec, p.clique_counts)
    print(f'{time()-t0:.2f} seconds')

if __name__ == "__main__":
    from random import random, seed
    from time import time
    seed(42)
    main()
