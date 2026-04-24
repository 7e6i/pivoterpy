from collections.abc import Sequence

class Graph:
    """
    The Graph class represents the graph data structure and provides several
    constructors for initializing from common formats. It automatically translates
    node IDs into an internal contiguous space, calculates node degrees, and
    tracks total edges and vertices.
    """
    # Add 'nodes' to store the original IDs
    __slots__ = ('edges', 'n', 'm', 'degrees', 'nodes', 'experimental')

    def __init__(self, edges: list[tuple[int, int]], n: int, nodes: list[int] = None):
        """
        Initializes a Graph object.

        Args:
            edges (list[tuple[int, int]]): A list of edge tuples (u, v) where u and v are
                                           internal contiguous node IDs.
            n (int): The number of unique nodes in the graph.
            nodes (list[int], optional): A mapping of internal node IDs (index) back to
                                         their original IDs (value). If None, it's assumed
                                         internal IDs are already 0 to n-1. Defaults to None.
        """
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
        """
        Creates a Graph from the upper triangle of a square adjacency matrix.
        Edges are inferred from entries greater than 0.

        Args:
            array (Sequence[Sequence[int | float | bool]]): A square adjacency matrix.

        Returns:
            Graph: A new Graph instance.
        """

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
        Creates a Graph from a list of (u, v) edge tuples.
        Compresses non-contiguous vertex IDs into a contiguous 0 to N-1 internal space,
        ignoring self-loops and duplicate edges.

        Args:
            array (list[tuple[int, int]]): A list of edge tuples, where u and v are
                                           the original node IDs.

        Returns:
            Graph: A new Graph instance with internal contiguous IDs and a mapping
                   back to original IDs.
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
    def from_networkx(cls, G: 'object') -> 'Graph':
        """
        Creates a Graph from an existing NetworkX graph object.
        Note: This constructor assumes NetworkX node IDs are already contiguous
        or will be handled by the `Graph` constructor's default `nodes` mapping.

        Args:
            G (object): A NetworkX graph object.

        Returns:
            Graph: A new Graph instance.
        """
        edges = [(u, v) for u, v in G.edges]
        return cls(edges=edges, n=G.number_of_nodes())
