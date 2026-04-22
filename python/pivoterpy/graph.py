from collections.abc import Sequence

class Graph:
    # Add 'nodes' to store the original IDs
    __slots__ = ('edges', 'n', 'm', 'degrees', 'nodes', 'experimental')

    def __init__(self, edges: list[tuple[int, int]], n: int, nodes: list[int] = None):
        self.edges = edges
        self.n = n
        self.m = len(edges)
        
        # If no mapping is provided, assume it's already contiguous 0 to N-1
        self.nodes = nodes if nodes is not None else list(range(n))

        self.degrees = [0] * self.n
        for u, v in self.edges:
            self.degrees[u] += 1
            self.degrees[v] += 1

        self.experimental = None

    @classmethod
    def from_adj_matrix(cls, array: Sequence[Sequence[int | float | bool]]) -> 'Graph':
        """Creates a Graph from the upper triangle of a square adjacency matrix."""

        try:
            assert len(array) == len(array[0]), "Adjacency matrix must be square"
        except IndexError:
            assert 1==0, "go touch grass"

        n = len(array)
        edges = []
        for i in range(n):
            for j in range(i + 1, n):
                if array[i][j] > 0:
                    edges.append((i, j))

        return cls(edges=edges, n=n)


    @classmethod
    def from_edge_list(cls, array: list[tuple[int, int]]) -> 'Graph':
        """
        Creates a Graph from a list of (u, v) tuples. 
        Compresses non-contiguous vertex IDs into a contiguous 0-N internal space.
        """
        old_to_new = {}
        new_to_old = []
        internal_edges = set()
        
        for u, v in array:
            assert isinstance(u, int) and isinstance(v, int), "Node indices must be integers"
            
            if u == v:
                continue  # Ignore self-loops

            # Map U
            if u not in old_to_new:
                old_to_new[u] = len(new_to_old)
                new_to_old.append(u)
            
            # Map V
            if v not in old_to_new:
                old_to_new[v] = len(new_to_old)
                new_to_old.append(v)
            
            internal_u = old_to_new[u]
            internal_v = old_to_new[v]

            norm = (internal_u, internal_v) if internal_u < internal_v else (internal_v, internal_u)
            internal_edges.add(norm)
            
        assert len(internal_edges) > 0, "No valid edges provided"

        return cls(edges=list(internal_edges), n=len(new_to_old), nodes=new_to_old)
    

    @classmethod
    def from_networkx(cls, G: object) -> 'Graph':
        """Creates a Graph from a NetworkX graph."""
        edges = [(u, v) for u, v in G.edges]

        return cls(edges=edges, n=G.number_of_nodes())
