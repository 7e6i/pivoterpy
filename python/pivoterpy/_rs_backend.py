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

    def __init__(self, G, resolution: str, procs: int, min_k: int, max_k: int) -> None:
        """
        Initializes the Rust backend wrapper.
        
        Args:
            G (Graph): The pre-processed graph object.
            resolution (str): The desired output resolution ('g', 'v', or 'e').
            procs (int): The number of parallel Rayon threads to use in Rust.
            min_k (int): The minimum clique size to compute.
            max_k (int): The maximum clique size to compute.
        """
        self.edges = G.edges
        self.n = G.n
        self.experimental = G.experimental
        
        self.resolution = resolution
        self.procs = procs
        self.min_k = min_k
        self.max_k = max_k


    def execute(self) -> list[int] | dict[int, list[int]] | dict[tuple[int, int], list[int]]:
        """
        Passes the raw graph topology and configuration to Rust.
        Rust will handle the degeneracy ordering internally to avoid FFI serialization overhead.

        Returns:
            list[int] | dict[int, list[int]] | dict[tuple[int, int], list[int]]: 
                The computed clique counts corresponding to the specified resolution.
        """

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