// src/lib.rs
use pyo3::prelude::*;

// 1. Declare your modules
mod cpu_backend;
mod gpu_backend;

// 2. Bring the specific functions into this file's scope so PyO3 can see them
use cpu_backend::{count_global, count_vertex, count_edge, count_global_exp};
use gpu_backend::count_global_cuda;

// 3. The Python Module Manifest
#[pymodule]
fn pivoter_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    
    // CPU functions
    m.add_function(wrap_pyfunction!(count_global, m)?)?;
    m.add_function(wrap_pyfunction!(count_vertex, m)?)?;
    m.add_function(wrap_pyfunction!(count_edge, m)?)?;
    m.add_function(wrap_pyfunction!(count_global_exp, m)?)?;
    
    // GPU functions
    m.add_function(wrap_pyfunction!(count_global_cuda, m)?)?;
    
    Ok(())
}