use pyo3::prelude::*;
use std::collections::HashMap;

// --- Expose functions to Python ---

#[pyfunction]
fn count_global(n: usize, edges: Vec<(usize, usize)>, procs: usize, min_k: usize, max_k: usize) -> PyResult<Vec<usize>> {
    // 1. Build adjacency list in Rust
    // 2. Compute degeneracy ordering in Rust
    // 3. Run Rayon parallel DFS
    // 4. Return Vec<usize> (PyO3 turns it into a Python list!)
    Ok(vec![])
}

#[pymodule]
fn pivoter_rust(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(count_global, m)?)?;
    // add vertex and edge functions...
    Ok(())
}