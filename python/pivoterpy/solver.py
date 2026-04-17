# pivoterpy/solver.py

from .graph import Graph
import sys


class pivoter:
    """The main stateful solver for clique counting."""
    
    def __init__(
            self, 
            graph, 
            resolution = "global", 
            backend = "python",
            procs = 1,
            min_k=None, 
            max_k=None
        ):

        assert isinstance(graph, Graph), "graph must be a Graph object"

        assert isinstance(resolution, str)
        assert isinstance(resolution, str) and resolution.lower() in ("global", "g", "vertex", "v", "edge", "e"), "resolution must be one of 'g[lobal]', 'v[ertex]', or 'e[dge]'"
        assert isinstance(resolution, str) and backend.lower() in ("python", "p", "rust", "r", "cuda", "c"), "backend must be one of 'p[ython]', 'r[ust]', 'c[uda]'"
        assert isinstance(procs, int) and procs >= 1, "procs must be a positive integer"
        assert min_k is None or (isinstance(min_k, int) and (0 <= min_k <= graph.n)), "ensure 0 <= min_k <= n"
        assert max_k is None or (isinstance(max_k, int) and (0 <= max_k <= graph.n)), "ensure 0 <= max_k <= n"
 
        if min_k and max_k:
            assert min_k <= max_k, "ensure min_k <= max_k"


        self.graph = graph
        
        self.resolution = resolution.lower()[0]
        self.backend = backend.lower()[0]
        self.procs = procs
        self.min_k = min_k
        self.max_k = max_k
  
        # Internal state to hold results after .run()
        self._global_counts = None
        self._vertex_counts = None
        self._edge_counts = None

        try:
            self._run()
        except KeyboardInterrupt:
            # make sure KeyboardInterrupt isn't caught in any of the backends
            print("\rExecution cancelled by user.")
            sys.exit(0) 
        except Exception as e:
            print(f"\rAn unexpected error occurred: {e}")
            sys.exit(1)
           

  
    def _run(self):
        self._bumped_min = max(self.min_k or 3, 3)

        # cant use "var or default" in case var=0 (evaluates as falsy)
        tmp = self.graph.n if self.max_k is None else self.max_k
        self._bumped_max = min(tmp, max(self.graph.degrees)+1)

        # ensures _bumped_min <= _bumped_max
        if self._bumped_max <= 2:
            raw_data = None
 
        elif self.backend == "p":
            from ._py_backend import PythonKernel
            raw_data = PythonKernel(
                self.graph,
                self.resolution,
                self.procs,
                self._bumped_min, 
                self._bumped_max, 
            ).execute()

        elif self.backend == "r":
            from ._rs_backend import RustKernel
            raw_data = RustKernel(
                self.graph, 
                self.resolution, 
                self.procs, 
                self._bumped_min, 
                self._bumped_max
            ).execute()

        elif self.backend == "c":
            from ._cu_backend import CUDAKernel
            raw_data = CUDAKernel(
                self.graph, 
                self.resolution, 
                self.procs, 
                self._bumped_min, 
                self._bumped_max
            ).execute()

        
        # assign data to correct variable
        if self.resolution == "g": self._global_counts = raw_data
        elif self.resolution == "v": self._vertex_counts = raw_data
        elif self.resolution == "e": self._edge_counts = raw_data

        self._coarser_counts()
        self._cleanup()
  
        return self
    

# ██████  ███████ ██████  ██ ██    ██ ███████ 
# ██   ██ ██      ██   ██ ██ ██    ██ ██      
# ██   ██ █████   ██████  ██ ██    ██ █████   
# ██   ██ ██      ██   ██ ██  ██  ██  ██      
# ██████  ███████ ██   ██ ██   ████   ███████ 


    def _coarser_counts(self):
        """Derives coarser raw counts from finer raw counts (indices 3+ only)."""

        # 1. Edges to Vertices
        if self.resolution == "e" and self._edge_counts:
            self._vertex_counts = [[] for _ in range(self.graph.n)]

            for (u, v), e_list in self._edge_counts.items():
                while len(self._vertex_counts[u]) < len(e_list): self._vertex_counts[u].append(0)
                while len(self._vertex_counts[v]) < len(e_list): self._vertex_counts[v].append(0)

                # Only aggregate k >= 3
                for k in range(3, len(e_list)):
                    self._vertex_counts[u][k] += e_list[k]
                    self._vertex_counts[v][k] += e_list[k]

            # Correct overlap: divide by (k-1)
            for v_list in self._vertex_counts:
                for k in range(3, len(v_list)):
                    v_list[k] //= (k - 1)

        # 2. Vertices to Global
        if self.resolution in ("e", "v") and self._vertex_counts:
            max_k = max((len(v_list) for v_list in self._vertex_counts), default=0)
            self._global_counts = [0] * max_k

            for v_list in self._vertex_counts:
                for k in range(3, len(v_list)):
                    self._global_counts[k] += v_list[k]

            # Correct overlap: divide by k
            for k in range(3, len(self._global_counts)):
                self._global_counts[k] //= k


    def _cleanup(self):
        """Injects trivials, enforces min_k, and truncates to max_k for ALL generated resolutions."""
        
        tmp_min = self.min_k or 0
        tmp_max = self.max_k if self.max_k is not None else self.graph.n

        # ---------------------------------------------------------
        # ALWAYS clean Global counts (every resolution derives this)
        # ---------------------------------------------------------
        self._global_counts = self._global_counts or []
        self._global_counts[0:3] = [1, self.graph.n, self.graph.m]
        
        self._global_counts[:tmp_min] = [0] * tmp_min
        self._global_counts = self._global_counts[:tmp_max + 1] # only needed when max_k < 3

        # ---------------------------------------------------------
        # Clean Vertex counts if resolution is 'v' or 'e'
        # ---------------------------------------------------------
        if self.resolution in ('v', 'e'):
            self._vertex_counts = self._vertex_counts or [[] for _ in range(self.graph.n)]
            
            for v, counts in enumerate(self._vertex_counts):
                counts[0:3] = [1, 1, self.graph.degrees[v]]
                counts[:tmp_min] = [0] * tmp_min
                counts[:] = counts[:tmp_max + 1]

        # ---------------------------------------------------------
        # Clean Edge counts ONLY if resolution is 'e'
        # ---------------------------------------------------------
        if self.resolution == 'e':
            self._edge_counts = self._edge_counts or {}
            
            for e in self.graph.edges:
                if e not in self._edge_counts:
                    self._edge_counts[e] = []
                
                counts = self._edge_counts[e]
                counts[0:3] = [0, 0, 1]
                counts[:tmp_min] = [0] * tmp_min
                counts[:] = counts[:tmp_max + 1]


#  ██████  ██       ██████  ██████   █████  ██      
# ██       ██      ██    ██ ██   ██ ██   ██ ██      
# ██   ███ ██      ██    ██ ██████  ███████ ██      
# ██    ██ ██      ██    ██ ██   ██ ██   ██ ██      
#  ██████  ███████  ██████  ██████  ██   ██ ███████ 


    @property
    def global_counts(self):
        return self._global_counts
    

    @property
    def global_ec(self) -> int:
        """Assuming you were using the Vietoris-Rips complex of the graph"""

        ec = None
        if self._global_counts:
            ec = 0
            for k, count in enumerate(self._global_counts):
                if k == 0 or count == 0:
                    continue
                ec += ((-1) ** (k + 1)) * count
            
        return ec


# ██    ██ ███████ ██████  ████████ ███████ ██   ██ 
# ██    ██ ██      ██   ██    ██    ██       ██ ██  
# ██    ██ █████   ██████     ██    █████     ███   
#  ██  ██  ██      ██   ██    ██    ██       ██ ██  
#   ████   ███████ ██   ██    ██    ███████ ██   ██ 


    @property
    def vertex_counts(self):
        return self._vertex_counts
        

    @property
    def vertex_ec(self) -> list[int]:
        """Computes the local Euler Characteristic for every vertex in the graph."""

        v_ec = None
        if self._vertex_counts:
            v_ec = [0] * self.graph.n
            
            for v, counts in enumerate(self._vertex_counts):
                ec = 0
                for k, count in enumerate(counts):
                    if k == 0 or count == 0:
                        continue
                    ec += ((-1) ** (k + 1)) * count
                v_ec[v] = ec
    
        return v_ec

    @property
    def vertex_curvatures(self) -> list[float]:
        """Fractional Curvature, Discrete Gauss-Bonnet, Levitt Curvature, Combinatorial Curvature"""

        v_curv = None
        if self._vertex_counts:
            v_curv = [0.0] * self.graph.n

            for v, counts in enumerate(self.vertex_counts):
                curv = 0.0
                for k, count in enumerate(counts):
                    if k == 0 or count == 0:
                        continue
                    curv += ((-1) ** (k + 1)) * (count / k)
                v_curv[v] = curv
            
        return v_curv


# ███████ ██████   ██████  ███████ 
# ██      ██   ██ ██       ██      
# █████   ██   ██ ██   ███ █████   
# ██      ██   ██ ██    ██ ██      
# ███████ ██████   ██████  ███████ 


    @property
    def edge_counts(self):
        return self._edge_counts
    

    # @property
    # def edge_ec(self) -> list[int]:
    #     """Computes the local Euler Characteristic for every vertex in the graph."""

    #     # idk what this actually is, or what it would be useful for

    #     return None
    
    # @property
    # def edge_curvatures(self) -> list[float]:
    #     """Edge curvatures?"""

    #     # idk what this actually is, or what it would be useful for
    #     return None