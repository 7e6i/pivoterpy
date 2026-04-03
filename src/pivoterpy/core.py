from math import comb
from multiprocessing import Pool
from collections.abc import Sequence

type Numeric = int | float | bool
type AdjMatrix = Sequence[Sequence[Numeric]]


class SCTnode:
    def __init__(self, label, v, ph_cnt, ph_chn):
        self.label = label
        self.v = v

        self.ph_cnt = ph_cnt # (pivot nodes, hold nodes)

        self.ph_chn = ph_chn # ((node, edge), parent_chain)


class Pivoter:
    '''
    Initialize pivoter object
    - mode=adj: n x n adjacency matrix, only reads upper triangle
    - mode=edge: m x 2 array of edges (u,v) where u<v, u in {0,...,n-1}
    '''

    def __init__(self, n: int, m: int, edges: list[tuple[int, int]]):
        """Pivoter constructor"""

        self.n = n
        self.m = m
        self.edges = edges

        self._setup()
        self._degeneracy_ordering()
        self._degeneracy_neighborhoods()

    @classmethod
    def from_adj_matrix(cls, array: AdjMatrix) -> 'Pivoter':
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
        edges = []
        for i in range(n):
            for j in range(i+1, n):
                if array[i][j] > 0:
                    edges.append((i,j))

        return cls(n=n, m=len(edges), edges=edges)

    @classmethod
    def from_edge_list(cls, array: list[tuple[int, int]], n: int) -> 'Pivoter':
        """
        Creates a Pivoter instance from a list of (u, v) tuples representing edges.

        Args:
            arr: A 2D list representing an m x 2 list of (u, v) edges.
            n: The number of nodes in the graph.

        Returns:
            Pivoter: A populated Pivoter object.

        Raises:
            AssertionError: If the provided list is not a list of tuples.
            AssertionError: If 0 <= u < v < n is not met.
        """

        edges = set()
        for u, v in array:
            assert isinstance(u, int) and isinstance(v, int), "Node indices must be integers"
            assert 0 <= u < n and 0 <= v < n and u < v, "Invalid edge"
            edges.add((u,v))
        
        return cls(n=n, m=len(edges), edges=list(edges))


    def _setup(self):
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


    def _degeneracy_neighborhoods(self):
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
            procs: int = 0, 
            get_curv: bool = False,
        ):

        assert isinstance(procs, int) and procs >= -1, "Processes must be a non-negative integer"
        assert get_curv in [True, False], "get_curv must be a boolean"
  
        self.procs = procs
        self.get_curv = get_curv

        self.global_counts = [0] * (self.n+1)
        self.vertex_counts = [[0] * (self.n+1) for _ in range(self.n)] if get_curv else None


        ### begin counting
        roots = range(self.n)

        if procs <= 1:
            # Sequential execution
            for v in roots:
                g_counts, v_counts = self._count_from_root(v)
                self._aggregate(g_counts, v_counts)
        else:
            # Parallel execution
            with Pool(processes=procs) as pool:
                # imap_unordered is faster than map because it yields results 
                # immediately as processes finish, rather than waiting for them all to complete in order.
                for g_counts, v_counts in pool.imap_unordered(self._count_from_root, roots):
                    self._aggregate(g_counts, v_counts)

        self._trim_trailing_zeros()



    def _count_from_root(self, v: int) -> tuple[int, list[int]]:
        global_counts = [0] * (self.n+1)
        vertex_counts = [[0] * (self.n+1) for _ in range(self.n)] if self.get_curv else None

        def child_generator(ego):
            """Identical generator, but updates local state."""
            p, h = ego.ph_cnt
            
            # reached a leaf node
            if not ego.label:
                if self.get_curv:
                    pv, hv = self._unpack_chain(ego.ph_chn)

                # from the paper
                for i in range(0, p + 1):
                    ncr = comb(p, i)
                    global_counts[h+i] += ncr

                    if self.get_curv: # vertex counts 
                        for v in hv:
                            vertex_counts[v][h+i] += ncr

                if self.get_curv: # vertex counts
                    for i in range(0, p):
                        ncr = comb(p - 1, i)
                        for v in pv:
                            vertex_counts[v][h+i+1] += ncr

                return 

            # find the best pivot
            pivot = self._choose_pivot(ego.label) 
            p_label = ego.label & self.neighborhoods[pivot]
            yield SCTnode(p_label, pivot, (p + 1, h), ((pivot,1), ego.ph_chn))

            # loop through the holds
            hNodes = list(ego.label - (self.neighborhoods[pivot] | {pivot}))
            for i in range(len(hNodes)):
                h_label = (ego.label & self.neighborhoods[hNodes[i]]) - set(hNodes[:i])
                yield SCTnode(h_label, hNodes[i], (p, h + 1), ((hNodes[i],0), ego.ph_chn))


        # initialize generator stack with "root" hold node
        root_node = SCTnode(self.degen_order_nbhds[v], v, (0, 1), ((v,0), None))
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
        return global_counts, vertex_counts

    def _aggregate(self, global_counts, vertex_counts) -> None:
        """Merges worker results back into the global state."""

        for k, c in enumerate(global_counts):
            self.global_counts[k] += c

        if self.get_curv:
            for v, row in enumerate(vertex_counts):
                for k, c in enumerate(row):
                    self.vertex_counts[v][k] += c


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
    def vertex_curv(self) -> list[float] | None:
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
        """Alias for vertex_curv."""
        return self.vertex_curv
    
    @property
    def vertex_clique_counts(self) -> list[int]:
        """Alias for vertex_counts."""
        return self.vertex_counts