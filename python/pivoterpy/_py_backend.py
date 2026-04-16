# pivoterpy/_py_backend.py

from math import comb
from multiprocessing import Pool
from collections import defaultdict

class SCTnode:
    __slots__ = ('label', 'ph_cnt', 'ph_chn')
    def __init__(self, label, ph_cnt):
        self.label = label # set of vertices
        self.ph_cnt = ph_cnt # (pivot nodes, hold nodes)

class SCTnode_chn:
    __slots__ = ('label', 'ph_cnt', 'ph_chn')
    def __init__(self, label, ph_cnt, ph_chn):
        self.label = label
        self.ph_cnt = ph_cnt
        self.ph_chn = ph_chn # ((node, edge), parent_chain)


class PythonKernel:

    def __init__(self, G, resolution, procs, min_k, max_k):
        self.edges = G.edges
        self.n = G.n

        self.resolution = resolution
        self.procs = procs
        self.min_k = min_k
        self.max_k = max_k

        self._setup_graph()


    def execute(self):
        if self.resolution == "g":
            self._count_global()
            return self.global_counts
        
        elif self.resolution == "v":
            self._count_vertex()
            return self.vertex_counts
        
        elif self.resolution == "e":
            self._count_edge()
            return self.edge_counts


# ███████ ███████ ████████ ██    ██ ██████  
# ██      ██         ██    ██    ██ ██   ██ 
# ███████ █████      ██    ██    ██ ██████  
#      ██ ██         ██    ██    ██ ██      
# ███████ ███████    ██     ██████  ██      


    def _setup_graph(self):
        """Builds neighborhoods, computes degeneracy ordering, and prunes roots."""
        
        # 1. Build initial neighborhoods and degree buckets
        self.nbhds = [set() for _ in range(self.n)]
        degrees = [0] * self.n
        
        for u, v in self.edges:
            self.nbhds[u].add(v)
            self.nbhds[v].add(u)
            degrees[u] += 1
            degrees[v] += 1
            
        by_degrees = [set() for _ in range(self.n)]
        for v, deg in enumerate(degrees):
            by_degrees[deg].add(v)
            
        # 2. Matula-Beck Degeneracy Ordering (O(m))
        degen_ranks = [0] * self.n  # degen_ranks[v] = rank of v
        core_numbers = [0] * self.n
        degeneracy = 0
        min_deg = 0
        processed = [False] * self.n
        
        for rank in range(self.n):
            while not by_degrees[min_deg]:
                min_deg += 1
                
            v = by_degrees[min_deg].pop()
            processed[v] = True
            degen_ranks[v] = rank
            
            degeneracy = max(degeneracy, min_deg)
            core_numbers[v] = degeneracy
            
            for w in self.nbhds[v]:
                if not processed[w]:
                    by_degrees[degrees[w]].remove(w)
                    degrees[w] -= 1
                    new_deg = degrees[w]
                    by_degrees[new_deg].add(w)
                    
                    if new_deg < min_deg:
                        min_deg = new_deg
                        

        self.max_k = min(self.max_k, degeneracy + 1)
        
        # 3. K-Core Pruned Degeneracy Neighborhoods & Valid Roots
        self.degen_nbhds = [set() for _ in range(self.n)]
        self.valid_roots = []
        
        # A k-clique requires participating nodes to be in at least the (k-1)-core.
        core_threshold = self.min_k - 1 if self.min_k > 0 else 0
        
        for v in range(self.n):
            # If the vertex doesn't survive the core threshold, drop it completely
            if core_numbers[v] < core_threshold:
                self.nbhds[v] = set() # to save memory... in python
                continue
                
            # Keep track of the valid roots for the DFS loop
            self.valid_roots.append(v)
            v_rank = degen_ranks[v]
            
            # Keep forward neighbors that ALSO survive the core threshold
            self.degen_nbhds[v] = {
                u for u in self.nbhds[v]
                if degen_ranks[u] > v_rank and core_numbers[u] >= core_threshold
            }


# ██   ██ ███████ ██      ██████  ███████ ██████  ███████ 
# ██   ██ ██      ██      ██   ██ ██      ██   ██ ██      
# ███████ █████   ██      ██████  █████   ██████  ███████ 
# ██   ██ ██      ██      ██      ██      ██   ██      ██ 
# ██   ██ ███████ ███████ ██      ███████ ██   ██ ███████ 


    def _choose_pivot(self, S):
        """Finds the optimal pivot"""
        pivot = None
        max_nbhd = -1
        max_possible = len(S) -1

        for v in S:
            size = len(self.nbhds[v] & S)

            if size > max_nbhd: 
                max_nbhd = size
                pivot = v

                if max_nbhd == max_possible: # break early if possible
                    break
        return pivot
    

    def _unpack_chain(self, chain_tuple) -> tuple[list[int], list[int]]:
        """Flattens a single tuple chain into a list of vertices."""
        if chain_tuple is None:
            return [], []
            
        pivot_list, hold_list = [], []
        current = chain_tuple
        
        while current is not None:
            vertex, parent_chain = current
            v, edge = vertex
            pivot_list.append(v) if edge == 1 else hold_list.append(v)
            current = parent_chain
            
        return pivot_list, hold_list


    def _edge(self, u: int, v: int):
        """Returns normalized edges such that u < v"""
        return (u, v) if u < v else (v, u)


#  ██████  ██       ██████  ██████   █████  ██      
# ██       ██      ██    ██ ██   ██ ██   ██ ██      
# ██   ███ ██      ██    ██ ██████  ███████ ██      
# ██    ██ ██      ██    ██ ██   ██ ██   ██ ██      
#  ██████  ███████  ██████  ██████  ██   ██ ███████ 


    def _count_global(self):
        self.global_counts  = []

        if self.procs == 1:
            for v in self.valid_roots:
                g_counts = self._branch_global(v)
                self._aggregate_global(g_counts)
        else:
            with Pool(processes=self.procs) as pool:
                chunk = max(1, len(self.valid_roots) // (self.procs * 4))
                for g_counts in pool.imap_unordered(self._branch_global, self.valid_roots, chunksize=chunk):
                    self._aggregate_global(g_counts)

    def _branch_global(self, v: int) -> list[int]:
        g_counts = defaultdict(int) # could be a list

        def child_generator(ego):
            p, h = ego.ph_cnt
            
            # reached a leaf node
            if not ego.label:
                max_i = min(p, self.max_k - h)
                for i in range(0, max_i + 1):
                    g_counts[h + i] += comb(p, i)
                return
            
            # If the current holds + pivots + remaining possible candidates 
            # can't even reach our min_k, kill the branch immediately.
            if h + p + len(ego.label) < self.min_k:
                return

            # find the best pivot
            pivot = self._choose_pivot(ego.label) 
            p_label = ego.label & self.nbhds[pivot]
            yield SCTnode(p_label, (p + 1, h))

            if h + 1 <= self.max_k: # no point in recursing if max_k will be hit
                h_labels = ego.label.difference(self.nbhds[pivot], {pivot})
                excluded_holds = set()
                
                for w in h_labels:
                    h_label = ego.label.intersection(self.nbhds[w]).difference(excluded_holds)                
                    yield SCTnode(h_label, (p, h + 1))
                    excluded_holds.add(w)

        # initialize generator stack with "root" hold node
        root_node = SCTnode(self.degen_nbhds[v], (0, 1))
        stack = [child_generator(root_node)]

        # classic DFS - but with generators
        while stack:
            active_gen = stack[-1]
            try:
                next_node = next(active_gen)
                stack.append(child_generator(next_node))
            except StopIteration:
                stack.pop()

        # since g_counts is a dict (to prevent appends)
        return [g_counts.get(k, 0) for k in range(max(g_counts) + 1)] if g_counts else []


    def _aggregate_global(self, g_counts) -> None:
        """Merges worker results back into the global state."""

        target_list = self.global_counts
            
        while len(target_list) < len(g_counts):
            target_list.append(0)
            
        for k in range(len(g_counts)):
            target_list[k] += g_counts[k]


# ██    ██ ███████ ██████  ████████ ███████ ██   ██ 
# ██    ██ ██      ██   ██    ██    ██       ██ ██  
# ██    ██ █████   ██████     ██    █████     ███   
#  ██  ██  ██      ██   ██    ██    ██       ██ ██  
#   ████   ███████ ██   ██    ██    ███████ ██   ██ 


    def _count_vertex(self):
        self.vertex_counts = [[] for _ in range(self.n)]

        if self.procs == 1:
            for v in self.valid_roots:
                v_counts = self._branch_vertex(v)
                self._aggregate_vertex(v_counts)
        else:
            with Pool(processes=self.procs) as pool:
                chunk = max(1, len(self.valid_roots)// (self.procs * 4))
                for v_counts in pool.imap_unordered(self._branch_vertex, self.valid_roots, chunksize=chunk):
                    self._aggregate_vertex(v_counts)

    def _branch_vertex(self, v: int) -> dict[list]:
        v_counts = defaultdict(lambda: defaultdict(int))

        def child_generator(ego):
            p, h = ego.ph_cnt
            
            if not ego.label:
                max_i = min(p, self.max_k - h)
                
                if h + max_i >= self.min_k:
                    pv, hv = self._unpack_chain(ego.ph_chn)

                    for i in range(0, max_i + 1):
                        k = h + i
                        
                        if k < self.min_k:
                            continue
                            
                        ncr = comb(p, i)
                        for v_hold in hv:
                            v_counts[v_hold][k] += ncr
                        if i > 0 and p > 0:
                            ncr_p = (ncr * i) // p  # = comb(p-1, i-1)
                            for v_pivot in pv:
                                v_counts[v_pivot][k] += ncr_p

                return
            
            # If holds + pivots + remaining candidates can't reach min_k, kill the branch.
            if h + p + len(ego.label) < self.min_k:
                return
            
            # pivots
            pivot = self._choose_pivot(ego.label) 
            p_label = ego.label & self.nbhds[pivot]
            yield SCTnode_chn(p_label, (p + 1, h), ((pivot, 1), ego.ph_chn))

            # holds
            if h + 1 <= self.max_k:
                h_labels = ego.label.difference(self.nbhds[pivot], {pivot})
                excluded_holds = set()
                for w in h_labels:
                    h_label = ego.label.intersection(self.nbhds[w]).difference(excluded_holds)                
                    yield SCTnode_chn(h_label, (p, h + 1), ((w, 0), ego.ph_chn))
                    excluded_holds.add(w)

        root_node = SCTnode_chn(self.degen_nbhds[v], (0, 1), ((v, 0), None))
        stack = [child_generator(root_node)]

        # dfs
        while stack:
            active_gen = stack[-1]
            try:
                next_node = next(active_gen)
                stack.append(child_generator(next_node))
            except StopIteration:
                stack.pop()

        return {
            v: [counts.get(k, 0) for k in range(max(counts) + 1)]
            for v, counts in v_counts.items()
        } if v_counts else {}


    def _aggregate_vertex(self, v_counts) -> None:
        """Merges worker results back into the global state."""
        # v_counts defaults to {}
        for v, incoming_list in v_counts.items():
            target_list = self.vertex_counts[v]
            
            while len(target_list) < len(incoming_list):
                target_list.append(0)
                
            for k in range(len(incoming_list)):
                target_list[k] += incoming_list[k]


# ███████ ██████   ██████  ███████ 
# ██      ██   ██ ██       ██      
# █████   ██   ██ ██   ███ █████   
# ██      ██   ██ ██    ██ ██      
# ███████ ██████   ██████  ███████ 

# so much duplicate code, too bad

    def _count_edge(self):
        self.edge_counts = {e: [] for e in self.edges}

        if self.procs == 1:
            for v in self.valid_roots:
                e_counts = self._branch_edge(v)
                self._aggregate_edge(e_counts)
        else:
            with Pool(processes=self.procs) as pool:
                chunk = max(1, len(self.valid_roots)// (self.procs * 4))
                for e_counts in pool.imap_unordered(self._branch_edge, self.valid_roots, chunksize=chunk):
                    self._aggregate_edge(e_counts)


    def _branch_edge(self, v: int) -> dict[list]:
        e_counts = defaultdict(lambda: defaultdict(int))

        def child_generator(ego):
            p, h = ego.ph_cnt
            
            if not ego.label:
                max_i = min(p, self.max_k - h)
                
                # The Unpack Wall: Skip if we can't mathematically reach min_k
                if h + max_i >= self.min_k:
                    pv, hv = self._unpack_chain(ego.ph_chn)

                    for i in range(0, max_i + 1):
                        k = h + i
                        
                        # Prevent massive dictionary memory bloat for lower orders
                        # (Also mathematically, an edge requires at least k=2)
                        if k < self.min_k or k < 2:
                            continue

                        ncr = comb(p, i)

                        ncr_0 = ncr
                        ncr_1 = (ncr * i) // p if (i > 0 and p > 0) else 0
                        ncr_2 = (ncr_1 * (i - 1)) // (p - 1) if (i > 1 and p > 1) else 0

                        # Case A: Both vertices are Holds
                        if ncr_0 > 0 and len(hv) >= 2:
                            for x in range(len(hv)):
                                for y in range(x + 1, len(hv)):
                                    # FIXED: Was previously pv[x], pv[y]
                                    e_counts[self._edge(hv[x], hv[y])][k] += ncr_0

                        # Case B: One Hold, One Pivot
                        if ncr_1 > 0 and hv and pv:
                            for n1 in hv:
                                for n2 in pv:
                                    e_counts[self._edge(n1, n2)][k] += ncr_1
                                    
                        # Case C: Both vertices are Pivots
                        if ncr_2 > 0 and len(pv) >= 2:
                            for x in range(len(pv)):
                                for y in range(x + 1, len(pv)):
                                    e_counts[self._edge(pv[x], pv[y])][k] += ncr_2

                return
            
            if h + p + len(ego.label) < self.min_k:
                return
            
            # pivot
            pivot = self._choose_pivot(ego.label) 
            p_label = ego.label & self.nbhds[pivot]
            yield SCTnode_chn(p_label, (p + 1, h), ((pivot, 1), ego.ph_chn))

            # holds
            if h + 1 <= self.max_k:
                h_labels = ego.label.difference(self.nbhds[pivot], {pivot})
                excluded_holds = set()
                for w in h_labels:
                    h_label = ego.label.intersection(self.nbhds[w]).difference(excluded_holds)                
                    yield SCTnode_chn(h_label, (p, h + 1), ((w, 0), ego.ph_chn))
                    excluded_holds.add(w)

        root_node = SCTnode_chn(self.degen_nbhds[v], (0, 1), ((v, 0), None))
        stack = [child_generator(root_node)]

        while stack:
            active_gen = stack[-1]
            try:
                next_node = next(active_gen)
                stack.append(child_generator(next_node))
            except StopIteration:
                stack.pop()


        return {
            e: [counts.get(k, 0) for k in range(max(counts) + 1)]
            for e, counts in e_counts.items()
        } if e_counts else {}


    def _aggregate_edge(self, e_counts) -> None:
        for e, incoming_list in e_counts.items():
            target_list = self.edge_counts[e]
    
            while len(target_list) < len(incoming_list):
                target_list.append(0)
                
            for k, count in enumerate(incoming_list):
                target_list[k] += count

