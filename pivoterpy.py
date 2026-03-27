from math import comb
from multiprocessing import Pool
import copy

import sys
sys.setrecursionlimit(10000) # just in case

class SCTnode:
    def __init__(self, label, ph_cnt, ph_v, v, call_type="h"):
        self.label = label
        p,h = ph_cnt
        self.ph_v = copy.deepcopy(ph_v)
        self.v = v
        if call_type == "p":
          self.ph_cnt = (p+1, h)
          self.ph_v[0] += [v]
        elif call_type == "h":
          self.ph_cnt = (p, h+1)
          self.ph_v[1] += [v]

    def __repr__(self):
        return f"SCT{[int(i) for i in self.label]} {str(self.ph_cnt)}"


class Pivoter:
    '''
    Initialize pivoter object
    - mode=adj: n x n adjacency matrix, only reads upper triangle
    - mode=edge: m x 2 array of edges (u,v) where u<v, u in {0,...,n-1}
    - mode=file: read edge array from file
    '''
    def __init__(self, mode, array=None, n=None, file_name=None, sep=" "):
        # n x n array, will only check upper triangle
        if mode == "adj":
            self._from_adj_arr(array)

        # m x 2 array, (u,v) where u<v
        elif mode == "edge":
            assert isinstance(n, int) and n > 0
            self._from_edge_arr(array, n)

        elif mode == "file":
            assert isinstance(n, int) and n > 0
            assert file_name is not None
            self._from_edge_file(file_name, sep)

    def _from_adj_arr(self, arr):
        assert len(arr) == len(arr[0]), "Adjacency matrix must be square"
        n, m, edges = len(arr), 0, []
        for i in range(n):
            for j in range(i+1, n):
                if arr[i][j] == 1:
                    edges.append((i,j))
                    m+=1
        self.n, self.m, self.edges = n, m, edges

    def _from_edge_arr(self, arr, n):
        edges = []
        for edge in arr:
            u, v = edge[0], edge[1]
            assert 0 <= u < n and 0 <= v < n and u < v, "Invalid edge"
            edges.append((u,v))
        self.n, self.m, self.edges = n, len(edges), edges 

    def _from_edge_file(self, file_name, sep, n):
        edges = []
        with open(file_name, 'r') as f:
            for line in f:
                u, v = map(int, line.strip().split(sep))
                assert 0 <= u < n and 0 <= v < n and u < v, "Invalid edge"
                edges.append((u,v))
        self.n, self.m, self.edges = n, len(edges), edges 


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

        if self.get_curv:
            max_idx = 0
            for v in range(self.n):
                for i in range(self.n, -1, -1):
                    if self.vertex_clique_counts[v][i] > 0: break
              
                max_idx = max(max_idx, i)
            self.vertex_clique_counts = [self.vertex_clique_counts[v][1:max_idx+1] for v in range(self.n)]

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
    def count_cliques(self, get_curv = False):
        self._count_clique_setup()
        self.get_curv = get_curv

        self.ec = 0
        self.clique_counts = [0 for _ in range(self.n+1)]
        if self.get_curv:
          self.vertex_clique_counts = [[0 for _ in range(self.n+1)] for _ in range(self.n)]
          self.curvatures = [0 for _ in range(self.n)]

        # loop through nodes
        for v in range(self.n):
            node = SCTnode(label=self.degen_order_nbhds[v], ph_cnt = (0,0), ph_v = [[], []], v = v)
            self._count_cliques_rec(node)

        self._trim_counts()

    def _count_cliques_rec(self, parent):
        # if parent.label is empty, update self.clique_counts, return
        if not parent.label:
            p,h = parent.ph_cnt
            pv,hv = parent.ph_v
            for i in range(0, p+1):
                ncr = comb(p, i)

                self.clique_counts[h+i] += ncr
                self.ec += pow(-1, h+i+1) * ncr

                if self.get_curv:
                    for v in hv:
                        self.vertex_clique_counts[v][h+i] += ncr
                        self.curvatures[v] += pow(-1, h+i+1) * ncr / (h+i)
            if self.get_curv:
                for v in pv:
                    for i in range(0, p):
                        ncr = comb(p-1, i)
                        self.vertex_clique_counts[v][h+i+1] += ncr
                        self.curvatures[v] += pow(-1, h+i+2) * ncr / (h+i+1)
            return

        # find pivot and recurse
        pivot = self._choose_pivot(parent.label)
        label = parent.label & self.neighborhoods[pivot]
        pNode = SCTnode(label, parent.ph_cnt, parent.ph_v, pivot, call_type="p")
        self._count_cliques_rec(pNode)

        # loop through hold nodes and recurse
        hNodes = list(parent.label - (self.neighborhoods[pivot] | {pivot}))
        for i in range(len(hNodes)):
            label = (parent.label & self.neighborhoods[hNodes[i]]) - set(hNodes[:i])
            hNode = SCTnode(label, parent.ph_cnt, parent.ph_v, hNodes[i])
            self._count_cliques_rec(hNode)


    '''
    parallelized implementation of count_cliques
    '''
    def count_cliques_mp(self, get_curv = False, procs = 1):
        self._count_clique_setup()
        self.get_curv = get_curv

        self.ec = 0
        self.clique_counts = [0 for _ in range(self.n+1)]
        if self.get_curv:
          self.vertex_clique_counts = [[0 for _ in range(self.n+1)] for _ in range(self.n)]
          self.curvatures = [0 for _ in range(self.n)]
        nodes = [SCTnode(self.degen_order_nbhds[v], (0,0), [[], []], v) for v in range(self.n)]

        with Pool(processes=procs) as pool:
            results = pool.map(self._cnt_clq_mp_wrap, nodes)

        for r in results:
            if self.get_curv:
                ec, counts, curv, v_counts = r
            else:
                ec, counts = r
            self.ec += ec

            for i in range(self.n+1):
                self.clique_counts[i] += counts[i]

            if self.get_curv:
                for v in range(self.n):
                    self.curvatures[v] += curv[v]
                    for i in range(self.n+1):
                        self.vertex_clique_counts[v][i] += v_counts[v][i]

        self._trim_counts()

    # needed to keep track of clique frequencies
    # takes advantage of multiproc copy on write rule when spawning subprocesses
    def _cnt_clq_mp_wrap(self, parent):
        self.clique_counts = [0 for _ in range(self.n+1)]
        self.ec = 0
        if self.get_curv:
            self.vertex_clique_counts = [[0 for _ in range(self.n+1)] for _ in range(self.n)]
            self.curvatures = [0 for _ in range(self.n)]

        self._cnt_clq_mp_rec(parent)
        if self.get_curv:
            return self.ec, self.clique_counts, self.curvatures, self.vertex_clique_counts
        
        return self.ec, self.clique_counts

    def _cnt_clq_mp_rec(self, parent):
        # if parent.label is empty, update self.clique_counts, return
        if not parent.label:
            p,h = parent.ph_cnt
            pv,hv = parent.ph_v
            for i in range(0, p+1):
                ncr = comb(p, i)

                self.clique_counts[h+i] += ncr
                self.ec += pow(-1, h+i+1) * ncr

                if self.get_curv:
                    for v in hv:
                        self.vertex_clique_counts[v][h+i] += ncr
                        self.curvatures[v] += pow(-1, h+i+1) * ncr / (h+i)
            
            if self.get_curv:
                for v in pv:
                    for i in range(0, p):
                        ncr = comb(p-1, i)
                        self.vertex_clique_counts[v][h+i+1] += ncr
                        self.curvatures[v] += pow(-1, h+i+2) * ncr / (h+i+1)
            return

        # find pivot and recurse
        pivot = self._choose_pivot(parent.label)
        label = parent.label & self.neighborhoods[pivot]
        pNode = SCTnode(label, parent.ph_cnt, parent.ph_v, pivot, call_type="p")
        self._cnt_clq_mp_rec(pNode)

        # loop through hold nodes and recurse
        hNodes = list(parent.label - (self.neighborhoods[pivot] | {pivot}))
        for i in range(len(hNodes)):
            label = (parent.label & self.neighborhoods[hNodes[i]]) - set(hNodes[:i])
            hNode = SCTnode(label, parent.ph_cnt, parent.ph_v, hNodes[i])
            self._cnt_clq_mp_rec(hNode)


'''
example usage
'''
def main():
    n, rr = 10, 1
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
    p.count_cliques_mp(procs=2, get_curv=True)
    print(p.ec, p.clique_counts)
    print(p.curvatures)
    print(p.vertex_clique_counts)
    print(f'{time()-t0:.2f} seconds')

if __name__ == "__main__":
    from random import random, seed
    from time import time
    seed(42)
    main()