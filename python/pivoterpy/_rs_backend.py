# pivoterpy/_rs_backend.py

try:
    from . import pivoter_rust
except ImportError:
    raise ImportError(
        "The Rust backend could not be imported. Please ensure 'pivoter_rust' "
        "is compiled and installed in your environment."
    )


class RustKernel:
    """
    The Python wrapper for the compiled Rust backend.
    """

    def __init__(self, G, resolution, procs, min_k, max_k):
        self.edges = G.edges
        self.n = G.n
        self.experimental = G.experimental
        
        self.resolution = resolution
        self.procs = procs
        self.min_k = min_k
        self.max_k = max_k


    def execute(self):
        """
        Passes the raw graph topology and configuration to Rust.
        Rust will handle the degeneracy ordering internally to avoid FFI serialization overhead.
        """

        if self.experimental:
            return pivoter_rust.count_global_exp(
                self.edges, self.n,  self.procs, self.min_k, self.max_k
            )


        if self.resolution == "g":
            return pivoter_rust.count_global(
                self.edges, self.n,  self.procs, self.min_k, self.max_k
            )
            
        elif self.resolution == "v":
            return pivoter_rust.count_vertex(
                self.edges, self.n, self.procs, self.min_k, self.max_k
            )
            
        elif self.resolution == "e":
            return pivoter_rust.count_edge(
                self.edges, self.n, self.procs, self.min_k, self.max_k
            )