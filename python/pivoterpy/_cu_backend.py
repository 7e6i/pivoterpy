# pivoterpy/_cu_backend.py

try:
    from . import pivoter_rust
except ImportError:
    raise ImportError(
        "CUDA (Rust) backend not found. Ensure the pivoter_cuda extension "
        "is compiled and accessible in your environment."
    )

class CUDAKernel:
    """
    The Python wrapper for the experimental CUDA backend.
    
    NOTE: This backend is still a work in progress and is not yet fully functional.
    """

    def __init__(self, G, resolution: str, procs: int, min_k: int, max_k: int) -> None:
        """
        Initializes the CUDA backend wrapper.
        
        Args:
            G (Graph): The pre-processed graph object.
            resolution (str): The desired output resolution ('g', 'v', or 'e').
            procs (int): Configures SM usage, grid sizing, or max concurrent streams.
            min_k (int): The minimum clique size to compute.
            max_k (int): The maximum clique size to compute.
        """
        self.edges = G.edges
        self.n = G.n
        
        self.resolution = resolution
        self.min_k = min_k
        self.max_k = max_k
        
        # In CUDA, 'procs' usually translates to SM usage, 
        # grid sizing, or max concurrent streams rather than CPU cores.
        self.procs = procs 

    def execute(self) -> list[int] | dict[int, list[int]] | dict[tuple[int, int], list[int]] | None:
        """
        Routes the execution to the compiled CUDA binaries.
        
        Returns:
            list[int] | dict[int, list[int]] | dict[tuple[int, int], list[int]] | None: 
                The computed clique counts corresponding to the specified resolution 
                (currently returns None or partial results as it is a WIP).
        """
        
        if self.resolution == "g":
            test = pivoter_rust.count_global_cuda()
            print(test)
            return
        
            return pivoter_rust.count_global_cuda(
                self.edges, self.n, self.procs, self.min_k, self.max_k
            )
        
        elif self.resolution == "v":
            pass
        
        elif self.resolution == "e":
            pass