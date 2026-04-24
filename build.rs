//! Build script for the optional CUDA backend (`--features cuda`).
//!
//! When the `cuda` feature is off (default for PyPI wheels and GitHub Actions), this script does
//! nothing so `cargo` / `maturin` do not require `nvcc` or a CUDA install.

fn main() {
    if std::env::var_os("CARGO_FEATURE_CUDA").is_none() {
        return;
    }

    println!("cargo:rerun-if-changed=build.rs");
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
