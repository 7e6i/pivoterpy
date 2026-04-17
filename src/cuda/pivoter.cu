#include <stdint.h>
#include <stdio.h>

__global__ void dummy_kernel(uint64_t* results) {
    int idx = threadIdx.x + blockIdx.x * blockDim.x;
    if (idx == 0) {
        results[0] = 999; 
    }
}

// THIS BLOCK IS CRITICAL FOR RUST TO SEE THE FUNCTION
extern "C" {
    void run_cuda_dfs_stub(uint64_t* results) {
        uint64_t* d_results;
        cudaMalloc((void**)&d_results, sizeof(uint64_t));
        dummy_kernel<<<1, 1>>>(d_results);
        cudaDeviceSynchronize();
        cudaMemcpy(results, d_results, sizeof(uint64_t), cudaMemcpyDeviceToHost);
        cudaFree(d_results);
    }
}