// build.rs
fn main() {
    println!("cargo:rerun-if-changed=src/cuda/pivoter.cu");

    cc::Build::new()
        .cuda(true)
        .file("src/cuda/pivoter.cu")
        .flag("-O3")
        .flag("-ccbin=gcc-13")
        //.compiler("g++-13")
        .compile("pivoter_cuda"); 
    
    println!("cargo:rustc-link-search=native=/usr/local/cuda/lib64");
    println!("cargo:rustc-link-lib=static=cudart_static"); 
    println!("cargo:rustc-link-lib=dylib=stdc++"); 
}