//! Build script for the experimental CUDA backend.
//!
//! This script uses the `cc` crate to compile the `.cu` files using `nvcc`
//! and instructs Cargo to link the resulting library along with the CUDA runtime.

// build.rs

/// Compiles `pivoter.cu` and configures the linker for CUDA and C++ standard libraries.
fn main() {
    println!("cargo:rerun-if-changed=src/cuda/pivoter.cu");

    cc::Build::new()
        .cuda(true)
        .file("src/cuda/pivoter.cu")
        .flag("-O3")
        .flag("-ccbin=gcc-13")
        .compile("pivoter_cuda"); 
    
    println!("cargo:rustc-link-search=native=/usr/local/cuda/lib64");
    println!("cargo:rustc-link-lib=static=cudart_static"); 
    println!("cargo:rustc-link-lib=dylib=stdc++"); 
}