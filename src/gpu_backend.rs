use pyo3::prelude::*;

extern "C" {
    // Links to the function in pivoter.cu
    fn run_cuda_dfs_stub(results: *mut u64);
}

// --- The Python Wrapper ---
#[pyfunction]
pub fn count_global_cuda() -> PyResult<u64> {
    let mut result: u64 = 0;
    
    // Using `unsafe` because we are crossing the C boundary
    unsafe {
        // Pass a mutable pointer to the GPU
        run_cuda_dfs_stub(&mut result as *mut u64);
    }
    
    Ok(result)
}