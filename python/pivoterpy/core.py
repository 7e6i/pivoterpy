from math import comb
from multiprocessing import Pool
from collections import defaultdict


class SCTnode:
    # notify the interpreter of all variables
    __slots__ = ('label', 'ph_cnt', 'ph_chn')

    def __init__(self, label, ph_cnt, ph_chn):
        self.label = label

        self.ph_cnt = ph_cnt # (pivot nodes, hold nodes)

        self.ph_chn = ph_chn # ((node, edge), parent_chain)


class _PythonPivoter:

    def __init__(self, edges: list[tuple[int, int]], n: int):
        """Pivoter constructor"""

        self.edges = edges
        self.n = n

        self._neighborhoods()
        self._degeneracy_ordering()
        self._degeneracy_nbhds()


    '''
    setup functions
    '''

    def _neighborhoods(self):
        """calculate neighborhoods, degrees, and nodes by degree"""

        # neighborhood of nodes
        self.neighborhoods = [set() for _ in range(self.n)]
        for u, v in self.edges:
            self.neighborhoods[u].add(v)
            self.neighborhoods[v].add(u)

        # degrees of nodes
        self.degrees = [len(nbhd) for nbhd in self.neighborhoods]

        # list of vertices by degree
        self.by_degrees = [set() for _ in range(self.n)]
        for v, degree in enumerate(self.degrees):
            self.by_degrees[degree].add(v)

    def _degeneracy_ordering(self):
        """degeneracy ordering of the nodes to optimize SCT construction"""

        # node v is at the rth position in the ordering: L1[r]=v, L2[v]=r
        L1 = []
        L2 = [None] * self.n

        # temporary duplicate copies to avoid mutation
        by_degrees = [s.copy() for s in self.by_degrees]
        degrees = self.degrees[:]

        rank = 0
        k = 0
        min_deg = 0

        # loop through nodes
        for _ in range(self.n):
            # find the node with lowest degree
            while not by_degrees[min_deg]:
                min_deg += 1

            # update k, update v, change L1/L2 accordingly
            k = max(k, min_deg)
            v = by_degrees[min_deg].pop()

            L1.append(v)
            L2[v] = rank
            rank += 1
            degrees[v] = -1

            # update w in N(v)\L
            for w in self.neighborhoods[v]:
                dw = degrees[w]
                if dw == -1:
                    continue

                by_degrees[dw].remove(w)
                degrees[w] -= 1
                by_degrees[dw - 1].add(w)

                if degrees[w] < min_deg:
                    min_deg = degrees[w]

        self.degeneracy = k
        self.node_by_degen_order = L1
        self.degen_order_by_node = L2


    def _degeneracy_nbhds(self):
        degen_order_nbhds = [None] * self.n # arr[v] = N^+(v)
        ranks = self.degen_order_by_node

        for v in range(self.n):
            v_rank = ranks[v]

            forward_neighbors = {
                u for u in self.neighborhoods[v]
                if ranks[u] > v_rank
            }

            degen_order_nbhds[v] = forward_neighbors

        self.degen_order_nbhds = degen_order_nbhds

    '''
    helper functions
    '''

    def _trim_trailing_zeros(self) -> None:
        """Removes trailing zeros from the counts arrays."""
        global_counts = self.global_counts
        vertex_counts = self.vertex_counts

        if not global_counts:
            return
        
        # Find the index of the largest clique size
        max_k = 0
        for k in range(1, len(global_counts)):
            if global_counts[k] == 0:
                max_k = k - 1
                break
        else:
            max_k = len(global_counts) - 1 # if graph is complete
        
        self.max_k = max_k
        self.global_counts = self.global_counts[:max_k + 1]
        if vertex_counts:
            self.vertex_counts = [row[:max_k + 1] for row in vertex_counts]

    def _choose_pivot(self, S):
        pivot = None
        max_nbhd = -1
        max_possible = len(S) -1

        for v in S:
            size = len(self.neighborhoods[v] & S)

            if size > max_nbhd: 
                max_nbhd = size
                pivot = v

                if max_nbhd == max_possible: # break early if possible
                    break
        return pivot
    
    def _unpack_chain(self, chain_tuple) -> tuple[list[int], list[int]]:
        """
        Flattens a single tuple chain into a list of vertices.
        """
        if chain_tuple is None:
            return [], []
            
        pivot_list = []
        hold_list = []
        current = chain_tuple
        
        while current is not None:
            vertex, parent_chain = current
            v, edge = vertex

            if edge == 1:
                pivot_list.append(v)
            elif edge == 0:
                hold_list.append(v)

            current = parent_chain
            
        return pivot_list, hold_list

    """
    Main entry point. 
    Handles both parallel and sequential logic with zero code duplication.
    """
    def count(
            self, 
            vertex: bool,
            procs: int, 
        ):

        self.procs = procs
        self.get_curv = vertex

        self.global_counts = [0] * (self.n+1)
        self.vertex_counts = [[0] * (self.n+1) for _ in range(self.n)] if self.get_curv else None

        ### begin counting
        roots = range(self.n)

        if procs is None:
            # Sequential execution
            for v in roots:
                g_counts, v_counts = self._count_from_root(v)
                self._aggregate(g_counts, v_counts)
        else:
            # Parallel execution
            with Pool(processes=self.procs) as pool:
                chunk = max(1, len(roots)// (self.procs * 4))
           
                for g_counts, v_counts in pool.imap_unordered(self._count_from_root, roots, chunksize=chunk):
                    self._aggregate(g_counts, v_counts)

        self._trim_trailing_zeros()



    def _count_from_root(self, v: int) -> tuple[int, list[int]]:
        global_counts = [0] * (self.n+1)
        vertex_counts = defaultdict(lambda: defaultdict(int)) if self.get_curv else None

        def child_generator(ego):
            """Identical generator, but updates local state."""
            p, h = ego.ph_cnt
            
            # reached a leaf node
            if not ego.label:
                for i in range(0, p + 1):
                    ncr = comb(p, i)
                    global_counts[h+i] += ncr

                    # vertex counts
                    if self.get_curv: 
                        pv, hv = self._unpack_chain(ego.ph_chn)

                        for v in hv:
                            vertex_counts[v][h+i] += ncr

                        if i > 0 and p > 0:
                            ncr_p = (ncr * i) // p  # = comb(p-1, i-1)
                            for v in pv:
                                vertex_counts[v][h+i] += ncr_p

                return 

            # find the best pivot
            pivot = self._choose_pivot(ego.label) 
            p_label = ego.label & self.neighborhoods[pivot]
            p_chain = ((pivot, 1), ego.ph_chn) if self.get_curv else None
            yield SCTnode(p_label, (p + 1, h), p_chain)

            # loop through the holds
            # hNodes = list(ego.label - (self.neighborhoods[pivot] | {pivot}))
            # for i in range(len(hNodes)):
            #     h_label = (ego.label & self.neighborhoods[hNodes[i]]) - set(hNodes[:i])
            #     yield SCTnode(h_label, hNodes[i], (p, h + 1), ((hNodes[i],0), ego.ph_chn))

            h_labels = ego.label.difference(self.neighborhoods[pivot], {pivot})
            excluded_holds = set()
            for v in h_labels:
                h_label = ego.label.intersection(self.neighborhoods[h]).difference(excluded_holds)                
                h_chain = ((h, 0), ego.ph_chn) if self.get_curv else None
                yield SCTnode(h_label, (p, h + 1), h_chain)
                excluded_holds.add(v)


        # initialize generator stack with "root" hold node
        root_chain = ((v, 0), None) if self.get_curv else None
        root_node = SCTnode(self.degen_order_nbhds[v], (0, 1), root_chain)
        stack = [child_generator(root_node)]

        # classic DFS
        while stack:
            # peek at top generator in stack
            active_gen = stack[-1]

            # try to get the next item from the generator
            # if successful, append generator of children
            # if out of items, pop the genny
            try:
                next_node = next(active_gen)
                stack.append(child_generator(next_node))
            except StopIteration:
                stack.pop()

        # Return the "process" results
        clean_v_counts = {k: dict(v) for k, v in vertex_counts.items()} if vertex_counts else None
        return global_counts, clean_v_counts

    def _aggregate(self, global_counts, vertex_counts) -> None:
        """Merges worker results back into the global state."""

        for k, count in enumerate(global_counts):
            self.global_counts[k] += count

        if self.get_curv and vertex_counts:
            for v, k_counts in vertex_counts.items():
                for k, count in k_counts.items():
                    self.vertex_counts[v][k] += count



    @property
    def global_ec(self) -> int:
        """
        Computes the global Euler Characteristic on the fly.
        Formula: sum of (-1)^(k-1) * count_k
        """
        if not self.global_counts:
            return None
            
        ec = 0
        for k, count in enumerate(self.global_counts):
            if k == 0 or count == 0:
                continue
            ec += ((-1) ** (k - 1)) * count
            
        return ec

    @property
    def vertex_ec(self) -> list[float] | None:
        """
        Computes vertex curvatures on the fly from vertex_counts.
        Formula: sum of (-1)^(k-1) * (count_k / k)
        """
        if not self.vertex_counts:
            return None
            
        curvatures = []
        for v_counts in self.vertex_counts:
            curv = 0.0
            for k, count in enumerate(v_counts):
                if k == 0 or count == 0:
                    continue
                curv += ((-1) ** (k - 1)) * (count / k)
            curvatures.append(curv)
            
        return curvatures
    

    @property
    def ec(self) -> list[int]:
        """Alias for global_ec."""
        return self.global_ec

    @property
    def clique_counts(self) -> list[int]:
        """Alias for global_counts."""
        return self.global_counts
    
    @property
    def curvatures(self) -> list[int]:
        """Alias for vertex_ec."""
        return self.vertex_ec
    
    @property
    def vertex_clique_counts(self) -> list[int]:
        """Alias for vertex_counts."""
        return self.vertex_counts