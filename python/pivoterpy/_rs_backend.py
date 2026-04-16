# pivoterpy/_rs_backend.py

import warnings

# We wrap the import in a try-except block so the library doesn't instantly crash 
# if the user hasn't compiled the Rust extension (e.g., they only want to use Python).
try:
    import pivoter_rust  # The compiled PyO3 module name (adjust if you name your crate differently)
    HAS_RUST_BACKEND = True
except ImportError:
    HAS_RUST_BACKEND = False


class RustKernel:
    """
    The Python wrapper for the compiled Rust backend.
    """

    def __init__(self, G, resolution, procs, min_k, max_k):
        if not HAS_RUST_BACKEND:
            raise ImportError(
                "The Rust backend could not be imported. Please ensure 'pivoter_rust' "
                "is compiled and installed in your environment."
            )

        self.n = G.n
        self.edges = G.edges # Assumes a list of tuples: [(u, v), ...]
        
        self.resolution = resolution
        self.procs = procs
        self.min_k = min_k
        self.max_k = max_k


    def execute(self):
        """
        Passes the raw graph topology and configuration to Rust.
        Rust will handle the degeneracy ordering internally to avoid FFI serialization overhead.
        """
        
        # PyO3 automatically translates:
        # Rust Vec<u64> -> Python List[int]
        # Rust Vec<Vec<u64>> -> Python List[List[int]]
        # Rust HashMap<(u64, u64), Vec<u64>> -> Python Dict[Tuple[int, int], List[int]]
        
        if self.resolution == "g":
            return pivoter_rust.count_global(
                self.n, self.edges, self.procs, self.min_k, self.max_k
            )
            
        elif self.resolution == "v":
            return pivoter_rust.count_vertex(
                self.n, self.edges, self.procs, self.min_k, self.max_k
            )
            
        elif self.resolution == "e":
            return pivoter_rust.count_edge(
                self.n, self.edges, self.procs, self.min_k, self.max_k
            )
        else:
            raise ValueError(f"Unknown resolution passed to Rust backend: {self.resolution}")