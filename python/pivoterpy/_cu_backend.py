# pivoterpy/_cu_backend.py

try:
    from . import pivoter_rust
except ImportError:
    raise ImportError(
        "CUDA (Rust) backend not found. Ensure the pivoter_cuda extension "
        "is compiled and accessible in your environment."
    )

class CUDAKernel:
    def __init__(self, G, resolution, procs, min_k, max_k):
        self.edges = G.edges
        self.n = G.n
        
        self.resolution = resolution
        self.min_k = min_k
        self.max_k = max_k
        
        # In CUDA, 'procs' usually translates to SM usage, 
        # grid sizing, or max concurrent streams rather than CPU cores.
        self.procs = procs 

    def execute(self):
        """Routes the execution to the compiled CUDA binaries."""
        
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