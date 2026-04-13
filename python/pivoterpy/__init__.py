
from .core import _PythonPivoter

from typing import Literal
from collections.abc import Sequence
import warnings

type Numeric = int | float | bool
type Backend = Literal["python", "py", "rust", "rs"]

class Pivoter:
    """
    The main API interface. Routes computations to the optimal backend.
    """
    def __init__(
        self, 
        edges: list[tuple[int, int]], 
        n: int,
        backend: Backend
    ):
        
        assert backend in ["python", "py", "rust", "rs"], "backend must be one of ['python', 'py', 'rust', 'rs']"
        
        if backend == "py":
            backend = "python"
        elif backend == "rs":
            backend = "rust"


        self.edges = edges
        self.n = n
        self.backend = backend
        
        # always init Python backend to init the nbhds and degeneracy stuff
        self._python_engine = _PythonPivoter(edges, n)
        self._rust_engine = None

        if self.backend in ["rust", "rs"]:
            try:
                # Try to load the compiled binary built by Maturin
                from . import _rust_engine

                degen_order_nbhds = [list(nbhd) for nbhd in self._python_engine.degen_order_nbhds]
                
                self._rust_engine = _rust_engine.RustPivoter(
                    self.n, 
                    self.edges,
                    self._python_engine.node_by_degen_order,
                    degen_order_nbhds
                )

            except ImportError:
                warnings.warn("Rust backend not found. Using Python as fallback.")
                self.backend = "python"


    @classmethod
    def from_adj_matrix(
        cls, 
        array:  Sequence[Sequence[Numeric]], 
        backend: Backend = "python"
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
        edges = []
        for i in range(n):
            for j in range(i+1, n):
                if array[i][j] > 0:
                    edges.append((i,j))

        return cls(edges=edges, n=n, backend=backend)

    @classmethod
    def from_edge_list(
        cls, 
        array: list[tuple[int, int]], 
        n: int, 
        backend: Backend = "python"
    ) -> 'Pivoter':
        
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
        
        return cls(edges=edges, n=n, backend=backend)


    def count(self, vertex: bool = False, procs: int = None):

        assert procs is None or (isinstance(procs, int) and procs >= 1), "procs must be None (sequential) or an integer >= 1 (parallel)"

        assert vertex in [True, False], "vertex must be a boolean"
        
        if self.backend == "python":
            self._python_engine.count(vertex, procs)

            self.global_counts = self._python_engine.global_counts
            self.vertex_counts = self._python_engine.vertex_counts
            self.max_k = self._python_engine.max_k

        elif self.backend == "rust":
            procs = 1 if procs is None else procs   
            self.global_counts = self._rust_engine.count(procs)
            


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