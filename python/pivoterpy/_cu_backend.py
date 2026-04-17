# pivoterpy/_cu_backend.py

import sys

try:
    import pivoter_cuda
except ImportError:
    raise ImportError(
        "CUDA backend not found. Ensure the pivoter_cuda extension "
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
        try:
            if self.resolution == "g":
                return pivoter_cuda.count_global(
                    self.edges, self.n, self.procs, self.min_k, self.max_k
                )
            
            elif self.resolution == "v":
                return pivoter_cuda.count_vertex(
                    self.edges, self.n, self.procs, self.min_k, self.max_k
                )
            
            elif self.resolution == "e":
                return pivoter_cuda.count_edge(
                    self.edges, self.n, self.procs, self.min_k, self.max_k
                )
            
            else:
                raise ValueError(f"Invalid resolution flag: '{self.resolution}'. Use 'g', 'v', or 'e'.")
                
        except KeyboardInterrupt:
            # \r overwrites the ugly '^C' that echoes to the terminal
            print("\r🛑 CUDA execution cancelled by user. Tearing down GPU streams...")
            sys.exit(0)
            
        except Exception as e:
            print(f"\r❌ A CUDA runtime error occurred: {e}")
            sys.exit(1)