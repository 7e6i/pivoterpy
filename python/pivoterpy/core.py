# python/pivoterpy/core.py

from math import comb
from multiprocessing import Pool
from collections import defaultdict

import warnings
from collections.abc import Sequence
type Numeric = int | float | bool

class SCTnode:
    # notify the interpreter of all variables
    __slots__ = ('label', 'ph_cnt', 'ph_chn')

    def __init__(self, label, ph_cnt, ph_chn):
        self.label = label

        self.ph_cnt = ph_cnt # (pivot nodes, hold nodes)

        self.ph_chn = ph_chn # ((node, edge), parent_chain)


class Pivoter:

# ██ ███    ██ ██ ████████ 
# ██ ████   ██ ██    ██    
# ██ ██ ██  ██ ██    ██    
# ██ ██  ██ ██ ██    ██    
# ██ ██   ████ ██    ██    
                         

    """
    The main API interface. Routes computations to the optimal backend.
    """
    def __init__(
        self, 
        edges: list[tuple[int, int]], 
        n: int,
    ):

        self.edges = edges
        self.n = n
        self.m = len(edges)

        self._neighborhoods()
        self._degeneracy_ordering()
        self._degeneracy_nbhds()


    @classmethod
    def from_adj_matrix(
        cls, 
        array:  Sequence[Sequence[Numeric]], 
    ) -> 'Pivoter':

        """
        Creates a Pivoter instance from the upper triangle of a square adjacency matrix.

        Args:
            arr: A 2D list representing an n x n square adjacency matrix 
                 where values > 0 indicate an edge.

        Returns:
            A populated Pivoter object containing the node count, 
            edge count, and a list of edge tuples.

        Raises:
            AssertionError: If the provided matrix is not square.
        """

        assert len(array) == len(array[0]), "Adjacency matrix must be square"

        n = len(array)
        edges = set()
        for i in range(n):
            for j in range(i+1, n):
                if array[i][j] > 0:
                    edges.add((i,j))

        return cls(edges=edges, n=n)

    @classmethod
    def from_edge_list(
        cls, 
        array: list[tuple[int, int]], 
        n: int = None, 
    ) -> 'Pivoter':
        
        """
        Creates a Pivoter instance from a list of (u, v) tuples representing edges.
        Ignores self-loops (u, u). Flips (v, u) with u < v to (u, v).

        Args:
            arr: A 2D list representing an m x 2 list of (u, v) edges.
            n: The number of nodes in the graph (defaults to largest u + 1).

        Returns:
            Pivoter: A populated Pivoter object.

        Raises:
            AssertionError: If the provided list is not a list of tuples.
            AssertionError: If 0 <= u, v < n is not met.
        """

        assert n is None or (isinstance(n, int) and n>=1), "n must be None or positive integer"

        largest_u = -1
        edges = set()
        for u, v in array:
            assert isinstance(u, int) and isinstance(v, int), "Node indices must be integers"

            if n is None:
                assert 0 <= u and 0 <= v,  "Invalid edge"
            else:
                assert 0 <= u < n and 0 <= v < n, "Invalid edge"

            norm = (u, v) if u < v else (v, u)
            edges.add(norm)
            largest_u = max(largest_u, u, v)
        
        if n is None:
            n = largest_u + 1

        # check if no edges and n is None
        assert len(edges) > 0 or n is not None, "No edges and no n provided"

        return cls(edges=edges, n=n)


# ███████ ███████ ████████ ██    ██ ██████  
# ██      ██         ██    ██    ██ ██   ██ 
# ███████ █████      ██    ██    ██ ██████  
#      ██ ██         ██    ██    ██ ██      
# ███████ ███████    ██     ██████  ██      
                                                                            

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
        L1, L2 = [], [None] * self.n

        # temporary duplicate copies to avoid mutation
        by_degrees = [s.copy() for s in self.by_degrees]
        degrees = self.degrees[:]

        rank, k, min_deg = 0, 0, 0  

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


# ██   ██ ███████ ██      ██████  ███████ ██████  ███████ 
# ██   ██ ██      ██      ██   ██ ██      ██   ██ ██      
# ███████ █████   ██      ██████  █████   ██████  ███████ 
# ██   ██ ██      ██      ██      ██      ██   ██      ██ 
# ██   ██ ███████ ███████ ██      ███████ ██   ██ ███████ 
                                                        
                                                        


    def _trim_trailing_zeros(self) -> None:
        """Removes trailing zeros from the counts arrays."""
        global_counts = self.global_counts

        # Find the index of the largest clique size
        self.max_k = sum([c > 0 for c in global_counts])
        self.global_counts = self.global_counts[:self.max_k + 1]

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
    
    
    def _edge(self, u: int, v: int):
        """
        Returns normalized edge such that u < v
        """

        return (u, v) if u < v else (v, u)



#  ██████  ██████  ██    ██ ███    ██ ████████ 
# ██      ██    ██ ██    ██ ████   ██    ██    
# ██      ██    ██ ██    ██ ██ ██  ██    ██    
# ██      ██    ██ ██    ██ ██  ██ ██    ██    
#  ██████  ██████   ██████  ██   ████    ██    
                                                                                

    def count(
            self, 
            vertex: bool = False, 
            edge: bool = False,
            procs: int = None, 
            rust: bool = False
        ):

        assert vertex in [True, False], "vertex must be a boolean"
        assert edge in [True, False], "edge must be a boolean"
        assert procs is None or (isinstance(procs, int) and procs >= 1), "procs must be None or an integer >= 1"
        assert rust in [True, False], "rust must be a boolean"

        self.count_vertex = vertex
        self.count_edge = edge
        self.use_rust = rust
        self.procs = procs

        self.global_counts = None
        self.vertex_counts = None
        self.edge_counts = None

        # guard for actual implementations
        if self.use_rust and self.count_edge:
            warnings.warn("Edge counts are not available with Rust - defaulting to Python")
            self.use_rust = False


        if self.use_rust:
            n_procs = 1 if self.procs is None else self.procs   # can't not use rayon

            try:
                from . import _rust_engine

                degen_order_nbhds = [list(nbhd) for nbhd in self.degen_order_nbhds]
                rust_worker = _rust_engine.RustPivoter(self.n, list(self.edges), self.node_by_degen_order, degen_order_nbhds)

                self.global_counts, self.vertex_counts = rust_worker.count(n_procs, self.count_vertex)


            except ImportError:
                warnings.warn("Rust backend not found - defaulting to Python")
                self.use_rust = False

        # check if had to use fallback 
        if not self.use_rust:
            self._py_count()


        
    def _py_count(self):
        self.global_counts  = [0] * (self.n+1)
        self.vertex_counts = [[] for _ in range(self.n)] if self.count_vertex else None
        self.edge_counts = {e: [] for e in self.edges} if self.count_edge else None

        roots = range(self.n)

        if self.procs is None:
            # Sequential execution
            for v in roots:
                g_counts, v_counts, e_counts = self._count_from_root(v)
                self._aggregate(g_counts, v_counts, e_counts)
        else:
            # Parallel execution
            with Pool(processes=self.procs) as pool:
                chunk = max(1, len(roots)// (self.procs * 4))
           
                for g_counts, v_counts, e_counts in pool.imap_unordered(self._count_from_root, roots, chunksize=chunk):
                    self._aggregate(g_counts, v_counts, e_counts)

        self._trim_trailing_zeros()



    def _count_from_root(self, v: int) -> tuple[int, list[int]]:
        g_counts = [0] * (self.n+1)
        v_counts = defaultdict(lambda: defaultdict(int)) if self.count_vertex else None
        e_counts = defaultdict(lambda: defaultdict(int)) if self.count_edge else None

        track_chain = self.count_vertex or self.count_edge

        def child_generator(ego):
            """Identical generator, but updates local state."""
            p, h = ego.ph_cnt
            
            # reached a leaf node
            if not ego.label:
                if track_chain:
                    pv, hv = self._unpack_chain(ego.ph_chn)

                for i in range(0, p + 1):
                    k = h + i

                    ncr = comb(p, i)
                    g_counts[k] += ncr

                    # TODO mostly tested
                    if self.count_vertex: 
                        for v in hv:
                            v_counts[v][k] += ncr

                        if i > 0 and p > 0:
                            ncr_p = (ncr * i) // p  # = comb(p-1, i-1)
                            for v in pv:
                                v_counts[v][k] += ncr_p

                    # TODO very much NOT tested
                    if self.count_edge and k >= 2:
                        # Combinatorics for how many times edges appear based on their sets
                        ncr_0 = ncr
                        ncr_1 = (ncr * i) // p if (i > 0 and p > 0) else 0
                        ncr_2 = (ncr_1 * (i - 1)) // (p - 1) if (i > 1 and p > 1) else 0

                        # Case A: Both vertices are Holds (Always present)
                        if ncr_0 > 0 and len(hv) >= 2:
                            for x in range(len(hv)):
                                for y in range(x + 1, len(hv)):
                                    e_counts[self._edge(pv[x], pv[y])][k] += ncr_0

                        # Case B: One Hold, One Pivot
                        if ncr_1 > 0 and hv and pv:
                            for n1 in hv:
                                for n2 in pv:
                                    e_counts[self._edge(n1,n2)][k] += ncr_1
                                    
                        # Case C: Both vertices are Pivots
                        if ncr_2 > 0 and len(pv) >= 2:
                            for x in range(len(pv)):
                                for y in range(x + 1, len(pv)):
                                    e_counts[self._edge(pv[x], pv[y])][k] += ncr_2

                return

            # find the best pivot
            pivot = self._choose_pivot(ego.label) 
            p_label = ego.label & self.neighborhoods[pivot]
            p_chain = ((pivot, 1), ego.ph_chn) if track_chain else None
            yield SCTnode(p_label, (p + 1, h), p_chain)


            h_labels = ego.label.difference(self.neighborhoods[pivot], {pivot})
            excluded_holds = set()
            for v in h_labels:
                h_label = ego.label.intersection(self.neighborhoods[v]).difference(excluded_holds)                
                h_chain = ((v, 0), ego.ph_chn) if track_chain else None
                yield SCTnode(h_label, (p, h + 1), h_chain)
                excluded_holds.add(v)


        # initialize generator stack with "root" hold node
        root_chain = ((v, 0), None) if track_chain else None
        root_node = SCTnode(self.degen_order_nbhds[v], (0, 1), root_chain)
        stack = [child_generator(root_node)]


        # classic DFS - but with generators
        while stack:
            active_gen = stack[-1]

            try:
                next_node = next(active_gen)
                stack.append(child_generator(next_node))
            except StopIteration:
                stack.pop()


        # convert dict{dict} to dict{list}
        v_counts_clean = {
            v: [counts.get(k, 0) for k in range(max(counts) + 1)]
            for v, counts in v_counts.items()
        } if self.count_vertex and v_counts else {}

        e_counts_clean = {
            e: [counts.get(k, 0) for k in range(max(counts) + 1)]
            for e, counts in e_counts.items()
        } if self.count_edge and e_counts else {}

        return g_counts, v_counts_clean, e_counts_clean


    def _aggregate(self, g_counts, v_counts, e_counts) -> None:
        """Merges worker results back into the global state."""

        for k, count in enumerate(g_counts):
            self.global_counts[k] += count

        # v_counts defaults to {}
        for v, incoming_list in v_counts.items():
                target_list = self.vertex_counts[v]
                
                while len(target_list) < len(incoming_list):
                    target_list.append(0)
                    
                for k in range(len(incoming_list)):
                    target_list[k] += incoming_list[k]

        # e_counts defaults to {}
        for e, incoming_list in e_counts.items():
            target_list = self.edge_counts[e]
    
            while len(target_list) < len(incoming_list):
                target_list.append(0)
                
            for k, count in enumerate(incoming_list):
                target_list[k] += count



# ██████  ███████ ███████ ██    ██ ██      ████████ ███████ 
# ██   ██ ██      ██      ██    ██ ██         ██    ██      
# ██████  █████   ███████ ██    ██ ██         ██    ███████ 
# ██   ██ ██           ██ ██    ██ ██         ██         ██ 
# ██   ██ ███████ ███████  ██████  ███████    ██    ███████ 
                                                                                                           
    
    @property
    def global_ec(self) -> int:
        """
        Computes the global Euler Characteristic.
        Formula: sum of (-1)^(k-1) * count_k
        """
        ec = 0
        for k, count in enumerate(self.global_counts):
            if k == 0 or count == 0:
                continue
            ec += ((-1) ** (k + 1)) * count
            
        return ec

    @property
    def vertex_ec(self) -> list[float] | None:
        """
        Computes vertex curvatures from vertex_counts.
        Formula: sum of (-1)^(k+1) * (count_k / k)
        """
        if not self.vertex_counts:
            return None
            
        curvatures = []
        for counts in self.vertex_counts:
            curv = 0.0
            for k, count in enumerate(counts):
                if k > 0 and count > 0:
                    curv += ((-1) ** (k + 1)) * (count / k)
            curvatures.append(curv)
            
        return curvatures
    

    @property
    def curvatures(self) -> list[int]:
        """Alias for vertex_ec."""
        return self.vertex_ec