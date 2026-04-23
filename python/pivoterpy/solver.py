# pivoterpy/solver.py

from .graph import Graph
import sys


class pivoter:
    """
    The main stateful solver for clique counting.

    It takes a pre-processed `Graph` object, dispatches the workload to the specified
    backend (Python or Rust), and stores the resulting topological data.
    """

    
    def __init__(
            self, 
            graph: Graph, 
            resolution: str = "global", 
            backend: str = "rust",
            procs: int = 1,
            min_k: None | int = None, 
            max_k: None | int = None
        ):

        """
        Initializes the pivoter solver.

        Args:
            graph (Graph): The pre-processed `Graph` object to analyze.
                Must be an instance of `pivoterpy.graph.Graph`.
            resolution (str, optional): The resolution of the clique counts to generate.
                Must be one of "global" ("g"), "vertex" ("v"), or "edge" ("e").
                Case-insensitive. Defaults to "global".
            backend (str, optional): The execution backend. Must be one of "python" ("p")
                or "rust" ("r"). Case-insensitive. Defaults to "rust".
            procs (int, optional): The number of processes for multiprocessing.
                Must be an integer greater than or equal to 1. Defaults to 1.
            min_k (int | None, optional): Minimum clique size to compute. If provided,
                must be an integer such that `0 <= min_k <= graph.n`. Cliques of size
                `k < min_k` are not computed. Defaults to None.
            max_k (int | None, optional): Maximum clique size to compute. If provided,
                must be an integer such that `0 <= max_k <= graph.n`. Cliques of size
                `k > max_k` are not computed. Defaults to None.

        Raises:
            AssertionError: If any input parameters fail validation checks.
        """

        assert isinstance(graph, Graph), "graph must be a Graph object"

        assert isinstance(resolution, str)
        assert isinstance(resolution, str) and resolution.lower() in ("global", "g", "vertex", "v", "edge", "e"), "resolution must be one of 'g[lobal]', 'v[ertex]', or 'e[dge]'"
        #assert isinstance(resolution, str) and backend.lower() in ("python", "p", "rust", "r", "cuda", "c"), "backend must be one of 'p[ython]', 'r[ust]', 'c[uda]'"
        assert isinstance(resolution, str) and backend.lower() in ("python", "p", "rust", "r"), "backend must be one of 'p[ython]', 'r[ust]'"
        assert isinstance(procs, int) and procs >= 1, "procs must be a positive integer"
        assert min_k is None or (isinstance(min_k, int) and (0 <= min_k <= graph.n)), "ensure 0 <= min_k <= n"
        assert max_k is None or (isinstance(max_k, int) and (0 <= max_k <= graph.n)), "ensure 0 <= max_k <= n"
 
        assert min_k is None or max_k is None or min_k <= max_k, "ensure min_k <= max_k"


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
        """
        Executes the clique counting algorithm using the configured backend.

        This method coordinates the execution of the pivoter algorithm by setting up
        the minimum and maximum clique sizes, initializing the appropriate backend
        kernel (Python, Rust, or CUDA), and retrieving the raw counts. Finally, it
        derives coarser resolution counts, cleans the data, and remaps vertices and edges.

        Returns:
            pivoter: Returns the current instance with populated clique counts.
        """
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
        self._remapping()
  
        return self
    

# ██████  ███████ ██████  ██ ██    ██ ███████ 
# ██   ██ ██      ██   ██ ██ ██    ██ ██      
# ██   ██ █████   ██████  ██ ██    ██ █████   
# ██   ██ ██      ██   ██ ██  ██  ██  ██      
# ██████  ███████ ██   ██ ██   ████   ███████ 


    def _coarser_counts(self):
        """
        Derives coarser raw counts from finer raw counts (indices 3+ only).

        If the resolution is 'edge', this method aggregates edge clique counts to 
        compute vertex counts, adjusting for overlaps by dividing by (k - 1). 
        If the resolution is 'edge' or 'vertex', it aggregates vertex clique counts 
        to compute global counts, adjusting for overlaps by dividing by k.
        
        This avoids redundant calculations by exploiting the mathematical relationship
        between clique counts at different topological resolutions.
        """

        # 1. Edges to Vertices
        if self.resolution == "e" and self._edge_counts:
            self._vertex_counts = {} # <-- Change to dict

            for (u, v), e_list in self._edge_counts.items():
                u_list = self._vertex_counts.setdefault(u, [])
                v_list = self._vertex_counts.setdefault(v, [])
                
                while len(u_list) < len(e_list): u_list.append(0)
                while len(v_list) < len(e_list): v_list.append(0)

                # Only aggregate k >= 3
                for k in range(3, len(e_list)):
                    u_list[k] += e_list[k]
                    v_list[k] += e_list[k]

            # Correct overlap: use .values()
            for v_list in self._vertex_counts.values():
                for k in range(3, len(v_list)):
                    v_list[k] //= (k - 1)

        # 2. Vertices to Global
        if self.resolution in ("e", "v") and self._vertex_counts:
            # Add .values() here
            max_k = max((len(v_list) for v_list in self._vertex_counts.values()), default=0)
            self._global_counts = [0] * max_k

            # Add .values() here too
            for v_list in self._vertex_counts.values():
                for k in range(3, len(v_list)):
                    self._global_counts[k] += v_list[k]

            for k in range(3, len(self._global_counts)):
                self._global_counts[k] //= k


    def _cleanup(self):
        """
        Injects trivial counts, enforces min_k, and truncates to max_k for all generated resolutions.

        This method ensures that the final count arrays or dictionaries include correct 
        values for k=0, 1, and 2 (such as total vertices and edges) where applicable. 
        It also zeros out any counts below the requested `min_k` and truncates the lists 
        to `max_k` to strictly adhere to the user's configured bounds.
        """
        
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
            self._vertex_counts = self._vertex_counts or {}
            
            # Change enumerate to .items()
            for v, counts in self._vertex_counts.items():
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


    def _remapping(self):
        """
        Translates internal contiguous node IDs back to their original IDs.

        This method updates the `_vertex_counts` and `_edge_counts` dictionaries 
        so that their keys correspond to the original node IDs (as provided to 
        the `Graph` constructor) rather than the internal 0-indexed IDs used 
        during the algorithm's execution. It also normalizes edge tuples.
        """
        # Translate Vertex Counts
        if self.resolution in ('v', 'e') and isinstance(self._vertex_counts, dict):
            mapped_v_counts = {}
            for internal_id, counts in self._vertex_counts.items():
                original_id = self.graph.nodes[internal_id]
                mapped_v_counts[original_id] = counts
            self._vertex_counts = mapped_v_counts

        # Translate Edge Counts
        if self.resolution == 'e' and isinstance(self._edge_counts, dict):
            mapped_e_counts = {}
            for (internal_u, internal_v), counts in self._edge_counts.items():
                original_u = self.graph.nodes[internal_u]
                original_v = self.graph.nodes[internal_v]
                
                # Ensure the original edge is properly ordered
                norm_e = (original_u, original_v) if original_u < original_v else (original_v, original_u)
                mapped_e_counts[norm_e] = counts
            self._edge_counts = mapped_e_counts


#  ██████  ██       ██████  ██████   █████  ██      
# ██       ██      ██    ██ ██   ██ ██   ██ ██      
# ██   ███ ██      ██    ██ ██████  ███████ ██      
# ██    ██ ██      ██    ██ ██   ██ ██   ██ ██      
#  ██████  ███████  ██████  ██████  ██   ██ ███████ 


    @property
    def global_counts(self):
        """
        Retrieves the global clique counts for the entire graph.

        Returns a list where the value at index `k` represents the total number of
        cliques of size `k` in the graph. 

        Returns:
            list[int] | None: The list of global clique counts, or None if unavailable.
        """
        return self._global_counts
    

    @property
    def global_ec(self) -> int:
        """
        Computes the global Euler Characteristic of the graph's clique complex.

        Assuming the graph represents a Vietoris-Rips complex (or clique complex), 
        this computes the Euler Characteristic by taking the alternating sum of the 
        number of k-cliques (simplices) for k >= 1.

        Returns:
            int | None: The calculated Euler Characteristic, or None if global counts are unavailable.
        """

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
    def vertex_counts(self) -> dict[int, list[int]] | None:
        """
        Retrieves the local clique counts for every vertex in the graph.

        Returns a dictionary where each key is a vertex ID and the value is a list
        of integer counts. The value at index `k` in a vertex's list represents the 
        total number of cliques of size `k` that contain that vertex.

        Returns:
            dict[int, list[int]] | None: A mapping of vertices to their clique counts, 
                                         or None if unavailable.
        """
        return self._vertex_counts
        

    @property
    def vertex_ec(self) -> dict[int, int] | None:
        """
        Computes the local Euler Characteristic for every vertex in the graph.

        The local Euler Characteristic of a vertex is computed by taking the alternating
        sum of the number of k-cliques (simplices) containing that vertex for k >= 1.

        Returns:
            dict[int, int] | None: A mapping of vertices to their calculated local 
                                   Euler Characteristic, or None if vertex counts 
                                   are unavailable.
        """

        v_ec = None
        if self._vertex_counts:
            v_ec = {}
            
            for v, counts in self._vertex_counts.items():
                ec = 0
                for k, count in enumerate(counts):
                    if k == 0 or count == 0:
                        continue
                    ec += ((-1) ** (k + 1)) * count
                v_ec[v] = ec
    
        return v_ec

    @property
    def curvatures(self) -> dict[int, float] | None:
        """
        Computes the combinatorial curvature for every vertex in the graph.

        Also known as Fractional Curvature, Discrete Gauss-Bonnet Curvature, or Levitt 
        Curvature. It is computed for a vertex by taking the alternating sum of the 
        number of k-cliques containing the vertex divided by k, for k >= 1.

        Returns:
            dict[int, float] | None: A mapping of vertices to their calculated curvature, 
                                     or None if vertex counts are unavailable.
        """

        v_curv = None
        if self._vertex_counts:
            v_curv = {}

            for v, counts in self._vertex_counts.items():
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
    def edge_counts(self) -> dict[tuple[int, int], list[int]] | None:
        """
        Retrieves the local clique counts for every edge in the graph.

        Returns a dictionary where each key is an edge tuple `(u, v)` and the value 
        is a list of integer counts. The value at index `k` in an edge's list represents 
        the total number of cliques of size `k` that contain that edge.

        Returns:
            dict[tuple[int, int], list[int]] | None: A mapping of edges to their clique counts, 
                                                     or None if unavailable.
        """
        return self._edge_counts
    