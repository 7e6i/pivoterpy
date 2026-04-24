//! The main PyO3 entry point for the Rust backend.
//!
//! This module exposes the high-performance clique counting functions
//! (global, vertex, and edge resolutions) to Python.

use pyo3::prelude::*;

mod cpu;
//mod gpu_backend;

use cpu::{count_global, count_vertex, count_edge};
//use gpu_backend::count_global_cuda;


/// Initializes the `pivoter_rust` Python module.
///
/// This function binds the exported Rust functions `count_global`,
/// `count_vertex`, and `count_edge` so they can be called directly
/// from the Python backend wrapper.
#[pymodule]
fn pivoter_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    
    // CPU functions
    m.add_function(wrap_pyfunction!(count_global, m)?)?;
    m.add_function(wrap_pyfunction!(count_vertex, m)?)?;
    m.add_function(wrap_pyfunction!(count_edge, m)?)?;


    // GPU functions
    //m.add_function(wrap_pyfunction!(count_global_cuda, m)?)?;
    
    Ok(())
}