from collections.abc import Sequence

class Graph:
    """
    A unified, immutable graph representation optimized for clique counting.
    Calculates structural metadata (neighborhoods, k-core numbers) upon instantiation.
    """
    
    __slots__ = ('edges', 'n', 'm', 'degrees', 'experimental')

    def __init__(self, edges: set[tuple[int, int]], n: int):
        self.edges = edges
        self.n = n
        self.m = len(edges)

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
    def from_edge_list(cls, array: list[tuple[int, int]], n: int = None) -> 'Graph':
        """
        Creates a Graph from a list of (u, v) tuples. 
        Ignores self-loops. Flips (v, u) with u < v to (u, v).
        """
        assert n is None or (isinstance(n, int) and n >= 1), "n must be None or a positive integer"

        largest_u = -1
        edges = set()
        
        for u, v in array:
            assert isinstance(u, int) and isinstance(v, int), "Node indices must be integers"

            if n is None:
                assert 0 <= u and 0 <= v,  "Invalid edge"
            else:
                assert 0 <= u < n and 0 <= v < n, "Invalid edge"

            if u != v:  # Ignore self-loops
                norm = (u, v) if u < v else (v, u)
                edges.add(norm)
                largest_u = max(largest_u, u, v)
        
        if n is None:
            n = largest_u + 1

        assert len(edges) > 0 or n is not None, "No edges and no n provided"

        return cls(edges=list(edges), n=n)


    @classmethod
    def from_networkx(cls, G: object) -> 'Graph':
        """Creates a Graph from a NetworkX graph."""
        edges = [(u, v) for u, v in G.edges]

        return cls(edges=edges, n=G.number_of_nodes())
