use pyo3::prelude::*;
use rayon::prelude::*;
use std::collections::HashMap;

use fixedbitset::FixedBitSet;
use num_bigint::{BigUint, ToBigUint};
use num_traits::{Zero, One};

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, mpsc};
use std::time::{Instant, Duration};


struct SCTnode {
    label: FixedBitSet,
    p: usize,
    h: usize,
}

struct SCTnodeChn {
    label: FixedBitSet,
    p: usize,
    h: usize,
    pv: Vec<usize>,
    hv: Vec<usize>,
}




// ███████ ███████ ████████ ██    ██ ██████  
// ██      ██         ██    ██    ██ ██   ██ 
// ███████ █████      ██    ██    ██ ██████  
//      ██ ██         ██    ██    ██ ██      
// ███████ ███████    ██     ██████  ██  


pub fn setup_graph(
    edges: &[(usize, usize)],
    n: usize,
    min_k: usize,
    max_k: usize,
) -> (Vec<Vec<usize>>, Vec<Vec<usize>>, Vec<usize>, usize) {
    let total_start = Instant::now();
    let phase1_start = Instant::now();
    
    // ---------------------------------------------------------
    // 1. Build initial neighborhoods and degree buckets
    // ---------------------------------------------------------
    let mut nbhds: Vec<Vec<usize>> = vec![vec![]; n];
    let mut degrees = vec![0; n];

    for &(u, v) in edges {
        nbhds[u].push(v);
        nbhds[v].push(u);
        degrees[u] += 1;
        degrees[v] += 1;
    }

    let mut by_degrees = vec![vec![]; n];
    for (v, &deg) in degrees.iter().enumerate() {
        by_degrees[deg].push(v);
    }

    println!("Adjacency Build: {:.3}s", phase1_start.elapsed().as_secs_f64());
    let phase2_start = Instant::now();

    // // ---------------------------------------------------------
    // // 2. Matula-Beck Degeneracy Ordering O(m)
    // // ---------------------------------------------------------
    // let mut degen_ranks = vec![0; n]; // degen_ranks[v] = rank of v
    // let mut core_numbers = vec![0; n];
    // let mut degeneracy = 0;
    // let mut min_deg = 0;
    // let mut processed = vec![false; n];

    // for rank in 0..n {
    //     while min_deg < n && by_degrees[min_deg].is_empty() {
    //         min_deg += 1;
    //     }

    //     let v = by_degrees[min_deg].pop().unwrap();
    //     processed[v] = true;
    //     degen_ranks[v] = rank;

    //     degeneracy = std::cmp::max(degeneracy, min_deg);
    //     core_numbers[v] = degeneracy;

    //     // Iterate over the dynamically sized list instead of a bitset
    //     for &w in &nbhds[v] {
    //         if !processed[w] {
    //             let old_deg = degrees[w];
    //             if let Some(pos) = by_degrees[old_deg].iter().position(|&x| x == w) {
    //                 by_degrees[old_deg].swap_remove(pos);
    //             }
    //             degrees[w] -= 1;
    //             let new_deg = degrees[w];
    //             by_degrees[new_deg].push(w);

    //             if new_deg < min_deg {
    //                 min_deg = new_deg;
    //             }
    //         }
    //     }
    // }

    // ---------------------------------------------------------
    // 2. Batagelj-Zaversnik Degeneracy Ordering O(V + E)
    // ---------------------------------------------------------
    
    let mut max_deg = 0;
    for &d in &degrees {
        if d > max_deg { max_deg = d; }
    }

    let mut bin = vec![0; max_deg + 1];
    for &d in &degrees {
        bin[d] += 1;
    }
    
    let mut start = 0;
    for d in 0..=max_deg {
        let num = bin[d];
        bin[d] = start;
        start += num;
    }

    let mut vert = vec![0; n];
    let mut pos = vec![0; n];
    for v in 0..n {
        let d = degrees[v];
        let p = bin[d];
        vert[p] = v;
        pos[v] = p;
        bin[d] += 1;
    }

    for d in (1..=max_deg).rev() {
        bin[d] = bin[d - 1];
    }
    bin[0] = 0;

    let mut degen_ranks = vec![0; n];
    let mut core_numbers = vec![0; n];
    let mut degeneracy = 0;

    // The peeling process
    for i in 0..n {
        let v = vert[i];
        let v_deg = degrees[v]; // BZ guarantees this is now exactly the core number!
        
        degeneracy = std::cmp::max(degeneracy, v_deg);
        core_numbers[v] = degeneracy;
        degen_ranks[v] = i;

        for &u in &nbhds[v] {
            // THE FIX: Strictly > prevents underflow and duplicate processing
            if degrees[u] > degrees[v] {
                let u_deg = degrees[u];
                let u_pos = pos[u];
                let bin_start = bin[u_deg];

                let w = vert[bin_start];
                
                if u != w {
                    vert[u_pos] = w;
                    pos[w] = u_pos;
                    vert[bin_start] = u;
                    pos[u] = bin_start;
                }

                bin[u_deg] += 1;
                degrees[u] -= 1;
            }
        }
    }

    println!("Degeneracy Order: {:.3}s", phase2_start.elapsed().as_secs_f64());
    let phase3_start = Instant::now();

    // ---------------------------------------------------------
    // Compute topological limits
    // ---------------------------------------------------------
    let effective_max_k = std::cmp::min(max_k, degeneracy + 1);
    let core_threshold = if min_k > 0 { min_k - 1 } else { 0 };


    // ---------------------------------------------------------
    // 4. Graph Compression (Vertex ID Remapping)
    // ---------------------------------------------------------
    
    let mut valid_roots = Vec::new();           
    let mut old_to_new = vec![usize::MAX; n];   

    for v in 0..n {
        if core_numbers[v] >= core_threshold {
            let new_id = valid_roots.len();
            old_to_new[v] = new_id;
            valid_roots.push(v); 
        }
    }

    let v_prime = valid_roots.len();

    // 4b. Use dynamically sized Vecs instead of massive BitSets
    let mut compressed_nbhds: Vec<Vec<usize>> = vec![vec![]; v_prime];
    let mut compressed_degen_nbhds: Vec<Vec<usize>> = vec![vec![]; v_prime];

    for new_v in 0..v_prime {
        let old_v = valid_roots[new_v];
        let v_rank = degen_ranks[old_v];

        for &old_u in &nbhds[old_v] {
            let new_u = old_to_new[old_u];

            if new_u != usize::MAX {
                compressed_nbhds[new_v].push(new_u);
                if degen_ranks[old_u] > v_rank {
                    compressed_degen_nbhds[new_v].push(new_u);
                }
            }
        }
    }

    // 4c. Sort the compressed lists
    for list in &mut compressed_nbhds { list.sort_unstable(); }
    for list in &mut compressed_degen_nbhds { list.sort_unstable(); }

    
    println!("Compression & Sorting: {:.3}s", phase3_start.elapsed().as_secs_f64());
    println!("Total Setup Time: {:.3}s", total_start.elapsed().as_secs_f64());

    (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k)
}


#[inline]
pub fn ncr(n: usize, k: usize) -> BigUint {
    if k > n { return BigUint::zero(); }
    if k == 0 || k == n { return BigUint::one(); }
    
    let k = std::cmp::min(k, n - k);
    let mut res = BigUint::one();
    
    for i in 1..=k {
        // Multiply first, then divide, using BigUint to prevent overflow
        res = res * (n - i + 1).to_biguint().unwrap();
        res = res / i.to_biguint().unwrap();
    }
    res
}


//  ██████  ██       ██████  ██████   █████  ██      
// ██       ██      ██    ██ ██   ██ ██   ██ ██      
// ██   ███ ██      ██    ██ ██████  ███████ ██      
// ██    ██ ██      ██    ██ ██   ██ ██   ██ ██      
//  ██████  ███████  ██████  ██████  ██   ██ ███████ 


/*
Peforms DFS on the level 1 nodes (found in the degen order).

The bitsets have been recalculated on the induced subgraph of the min_k-core (nodes in the degen order)
but have not been recalculated on the induced subgraphs of the level 1 nodes.
*/

#[pyfunction]
pub fn count_global(
    py: Python, // <-- PyO3 injects the GIL token here
    edges: Vec<(usize, usize)>, 
    n: usize, 
    procs: usize, 
    min_k: usize, 
    max_k: usize
) -> PyResult<Vec<BigUint>> {
    
    // 1. Build Compressed Neighborhoods
    let (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k) = 
        setup_graph(&edges, n, min_k, max_k);

    let v_prime = valid_roots.len();

    // 2. Setup the Cancellation Token & Channel
    let cancel = Arc::new(AtomicBool::new(false));
    let cancel_worker = Arc::clone(&cancel); 
    let (tx, rx) = mpsc::channel();

    // 3. Spawn Rayon in the Background Thread
    std::thread::spawn(move || {
        // We use unwrap() here because if thread creation fails, the worker panics 
        // and the main thread cleanly catches it as a Disconnect error below.
        let pool = rayon::ThreadPoolBuilder::new().num_threads(procs).build().unwrap();
        
        let parallel_counts = pool.install(|| {
            (0..v_prime)
                .into_par_iter()
                .map(|new_v| {
                    let cands = &compressed_degen_nbhds[new_v];
                    let num_cands = cands.len();

                    // 1. If we can't mathematically reach min_k, abort immediately
                    if 1 + num_cands < min_k {
                        return vec![BigUint::zero(); effective_max_k + 1];
                    }

                    // 2. Build the Micro-Bitsets (Induced Subgraph)
                    let mut local_nbhds = vec![FixedBitSet::with_capacity(num_cands); num_cands];

                    for (local_u, &global_u) in cands.iter().enumerate() {
                        for &global_w in &compressed_nbhds[global_u] {
                            // Fast O(log N) mapping from global to local 0..N space
                            if let Ok(local_w) = cands.binary_search(&global_w) {
                                local_nbhds[local_u].insert(local_w);
                            }
                        }
                    }

                    // 3. Initialize the tiny local label (All 1s, since everyone is a valid candidate)
                    let mut initial_label = FixedBitSet::with_capacity(num_cands);
                    initial_label.insert_range(..); 

                    // Pass the tiny local matrix instead of the global one
                    branch_global(
                        SCTnode {label: initial_label, p: 0, h: 1}, 
                        &local_nbhds, 
                        min_k, 
                        effective_max_k,
                        &cancel_worker 
                    )
                })
                .reduce(
                    // Explicit type hint to prevent E0282
                    || -> Vec<BigUint> { vec![BigUint::zero(); effective_max_k + 1] },
                    |mut acc: Vec<BigUint>, local: Vec<BigUint>| {
                        if !cancel_worker.load(Ordering::Relaxed) {
                            for i in 0..acc.len() {
                                acc[i] += &local[i];
                            }
                        }
                        acc
                    }
                )
        });

        // Send the result back to the main thread
        let _ = tx.send(parallel_counts);
    });

    // 4. The Main Thread Watchdog
    let mut global_counts = loop {
        // Ask Python if the user hit Ctrl+C
        if let Err(e) = py.check_signals() {
            // Instantly flip the atomic flag so Rayon threads commit suicide
            cancel.store(true, Ordering::Relaxed);
            return Err(e); 
        }

        // Check if Rayon finished its work 
        match rx.recv_timeout(Duration::from_millis(50)) {
            Ok(counts) => break counts, // Done! Exit loop with the data.
            Err(mpsc::RecvTimeoutError::Timeout) => continue, // Still working.
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                return Err(pyo3::exceptions::PyRuntimeError::new_err("Rust worker thread crashed."));
            }
        }
    };

    // 5. Chop Trailing Zeroes
    let mut actual_max = global_counts.len().saturating_sub(1);
    while actual_max > 0 && global_counts[actual_max].is_zero() { 
        actual_max -= 1;
    }
    
    global_counts.truncate(actual_max + 1);

    Ok(global_counts)
}


// --- 3. The Unified Hot Loop DFS Engine ---
fn branch_global(
    root_node: SCTnode, 
    local_nbhds: &[FixedBitSet],
    min_k: usize,
    max_k: usize,
    cancel_flag: &AtomicBool,
) -> Vec<BigUint> {

    let mut local_counts = vec![BigUint::zero(); max_k + 1];
    let mut stack = Vec::new();
    stack.push(root_node);

    let mut iteration = 0usize;

    while let Some(SCTnode { label, p, h }) = stack.pop() {
        
        // --- Cooperative Cancellation Check ---
        iteration = iteration.wrapping_add(1);
        if iteration & 1023 == 0 {
            if cancel_flag.load(Ordering::Relaxed) {
                return vec![]; 
            }
        }

        let size = label.count_ones(..);

        // --- Leaf Node Reached ---
        if size == 0 {
            let max_i = std::cmp::min(p, max_k.saturating_sub(h));
            if h + max_i >= min_k {
                for i in 0..=max_i {
                    let k = h + i;
                    if k >= min_k && k <= max_k {
                        local_counts[k] += ncr(p, i);
                    }
                }
            }
            continue;
        }

        // --- Pruning Wall ---
        if h + p + size < min_k {
            continue;
        }

        // --- Find the Pivot ---
        let mut pivot = 0;
        let mut max_degree = 0;
        
        for w in label.ones() {
            // Pure SIMD bitwise intersection on the micro-bitset!
            let mut isect = label.clone();
            isect.intersect_with(&local_nbhds[w]);
            
            let deg = isect.count_ones(..);
            if deg >= max_degree {
                max_degree = deg;
                pivot = w;
                if max_degree == size - 1 { break; } 
            }
        }

        // --- 1. Pivot Branch ---
        let mut p_label = label.clone();
        p_label.intersect_with(&local_nbhds[pivot]);
        
        stack.push(SCTnode { label: p_label, p: p + 1, h });

        // --- 2. Hold Branches ---
        if h + 1 <= max_k {
            let mut h_cands = label.clone();
            
            h_cands.difference_with(&local_nbhds[pivot]);
            h_cands.set(pivot, false);

            let mut excluded_holds = FixedBitSet::with_capacity(label.len());

            for w in h_cands.ones() {
                let mut h_label = label.clone();
                h_label.intersect_with(&local_nbhds[w]);
                h_label.difference_with(&excluded_holds);

                stack.push(SCTnode { label: h_label, p, h: h + 1 });
                excluded_holds.insert(w);
            }
        }
    }

    local_counts
}


// // ██    ██ ███████ ██████  ████████ ███████ ██   ██ 
// // ██    ██ ██      ██   ██    ██    ██       ██ ██  
// // ██    ██ █████   ██████     ██    █████     ███   
// //  ██  ██  ██      ██   ██    ██    ██       ██ ██  
// //   ████   ███████ ██   ██    ██    ███████ ██   ██ 


// #[pyfunction]
// pub fn count_vertex(
//     py: Python, // <-- PyO3 injects the GIL token here
//     edges: Vec<(usize, usize)>, 
//     n: usize, 
//     procs: usize, 
//     min_k: usize, 
//     max_k: usize
// ) -> PyResult<Vec<Vec<BigUint>>> {
    
//     // 1. Build Compressed Neighborhoods
//     let (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k) = 
//         setup_graph(&edges, n, min_k, max_k);

//     let v_prime = valid_roots.len();

//     // 2. Setup the Cancellation Token & Channel
//     let cancel = Arc::new(AtomicBool::new(false));
//     let cancel_worker = Arc::clone(&cancel); 
//     let (tx, rx) = mpsc::channel();

//     // 3. Spawn Rayon in the Background Thread
//     std::thread::spawn(move || {
//         let pool = rayon::ThreadPoolBuilder::new().num_threads(procs).build().unwrap();

//         let parallel_results = pool.install(|| {
//             (0..v_prime)
//                 .into_par_iter()
//                 .map(|new_v| {
//                     // Initialize the root task dynamically
//                     let mut initial_label = FixedBitSet::with_capacity(v_prime);
//                     for &u in &compressed_degen_nbhds[new_v] {
//                         initial_label.insert(u);
//                     }
//                     let root_node = SCTnodeChn {
//                         label: initial_label,
//                         p: 0,
//                         h: 1,
//                         pv: Vec::new(),
//                         hv: vec![new_v],
//                     };

//                     branch_vertex(
//                         root_node, 
//                         &compressed_nbhds, 
//                         min_k, 
//                         effective_max_k,
//                         &cancel_worker // Pass token to worker
//                     )
//                 })
//                 // Thread-Local Accumulator (v_prime matrix)
//                 .fold(
//                     || -> Vec<Vec<BigUint>> { vec![vec![]; v_prime] }, 
//                     |mut acc: Vec<Vec<BigUint>>, local_map: HashMap<usize, Vec<BigUint>>| {
//                         if !cancel_worker.load(Ordering::Relaxed) {
//                             for (v, counts) in local_map {
//                                 if acc[v].is_empty() { acc[v] = vec![BigUint::zero(); effective_max_k + 1]; }
//                                 for i in 0..counts.len() { acc[v][i] += &counts[i]; }
//                             }
//                         }
//                         acc
//                     }
//                 )
//                 // Global Merge
//                 .reduce(
//                     || -> Vec<Vec<BigUint>> { vec![vec![]; v_prime] },
//                     |mut acc1: Vec<Vec<BigUint>>, acc2: Vec<Vec<BigUint>>| {
//                         if !cancel_worker.load(Ordering::Relaxed) {
//                             for v in 0..v_prime {
//                                 if !acc2[v].is_empty() {
//                                     if acc1[v].is_empty() {
//                                         acc1[v] = acc2[v].clone();
//                                     } else {
//                                         for i in 0..acc2[v].len() { acc1[v][i] += &acc2[v][i]; }
//                                     }
//                                 }
//                             }
//                         }
//                         acc1
//                     }
//                 )
//         });

//         // Send the result back to the main thread
//         let _ = tx.send(parallel_results);
//     });

//     // 4. The Main Thread Watchdog
//     let mut compressed_results = loop {
//         // Ask Python if the user hit Ctrl+C
//         if let Err(e) = py.check_signals() {
//             // Instantly flip the atomic flag so Rayon threads commit suicide
//             cancel.store(true, Ordering::Relaxed);
//             return Err(e); 
//         }

//         // Check if Rayon finished its work 
//         match rx.recv_timeout(Duration::from_millis(50)) {
//             Ok(results) => break results, // Done! Exit loop with the data.
//             Err(mpsc::RecvTimeoutError::Timeout) => continue, // Still working.
//             Err(mpsc::RecvTimeoutError::Disconnected) => {
//                 return Err(pyo3::exceptions::PyRuntimeError::new_err("Rust worker thread crashed."));
//             }
//         }
//     };

//     // 5. Remap to original IDs and chop zeroes
//     let mut final_counts = vec![vec![]; n];
//     for new_id in 0..v_prime {
//         let old_id = valid_roots[new_id];
//         let mut counts = std::mem::take(&mut compressed_results[new_id]);
        
//         if !counts.is_empty() {
//             let mut actual_max = counts.len().saturating_sub(1);
//             while actual_max > 0 && counts[actual_max].is_zero() { actual_max -= 1; }
//             counts.truncate(actual_max + 1);
//         }
//         final_counts[old_id] = counts;
//     }

//     Ok(final_counts)
// }

// // --- Vertex Hot Loop ---
// fn branch_vertex(
//     root_node: SCTnodeChn,
//     compressed_nbhds: &[Vec<usize>],
//     min_k: usize,
//     max_k: usize,
//     cancel_flag: &AtomicBool // <-- Added token
// ) -> HashMap<usize, Vec<BigUint>> {

//     let mut local_counts = HashMap::new();
//     let mut stack = Vec::new();
//     stack.push(root_node);

//     let mut iteration = 0usize;

//     while let Some(SCTnodeChn { label, p, h, pv, hv }) = stack.pop() {
        
//         // --- Cooperative Cancellation Check ---
//         iteration = iteration.wrapping_add(1);
//         if iteration & 1023 == 0 {
//             if cancel_flag.load(Ordering::Relaxed) {
//                 return HashMap::new(); // Drop the branch instantly
//             }
//         }

//         let size = label.count_ones(..);

//         // --- Leaf Node Reached ---
//         if size == 0 {
//             let max_i = std::cmp::min(p, max_k.saturating_sub(h));
//             if h + max_i >= min_k {
//                 for i in 0..=max_i {
//                     let k = h + i;
//                     if k >= min_k && k <= max_k {
//                         let ncr_0 = ncr(p, i);
                        
//                         if !ncr_0.is_zero() {
//                             // Apply to all Hold nodes
//                             for &v_hold in &hv {
//                                 let target = local_counts
//                                     .entry(v_hold)
//                                     .or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
//                                 target[k] += &ncr_0;
//                             }
                            
//                             // Apply to all Pivot nodes
//                             if i > 0 && p > 0 {
//                                 let mut ncr_p = &ncr_0 * i.to_biguint().unwrap();
//                                 ncr_p /= p.to_biguint().unwrap();
                                
//                                 if !ncr_p.is_zero() {
//                                     for &v_pivot in &pv {
//                                         let target = local_counts
//                                             .entry(v_pivot)
//                                             .or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
//                                         target[k] += &ncr_p;
//                                     }
//                                 }
//                             }
//                         }
//                     }
//                 }
//             }
//             continue;
//         }

//         if h + p + size < min_k { continue; }

//         // --- Find the Pivot ---
//         let mut pivot = 0;
//         let mut max_degree = 0;
//         for w in label.ones() {
//             let mut isect = label.clone();
//             isect.intersect_with(&compressed_nbhds[w]);
//             let deg = isect.count_ones(..);
//             if deg >= max_degree {
//                 max_degree = deg;
//                 pivot = w;
//                 if max_degree == size - 1 { break; } 
//             }
//         }

//         // --- 1. Pivot Branch ---
//         let mut p_label = label.clone();
//         p_label.intersect_with(&compressed_nbhds[pivot]);
        
//         let mut new_pv = pv.clone();
//         new_pv.push(pivot);
        
//         stack.push(SCTnodeChn { label: p_label, p: p + 1, h, pv: new_pv, hv: hv.clone() });

//         // --- 2. Hold Branches ---
//         if h + 1 <= max_k {
//             let mut h_cands = label.clone();
//             h_cands.difference_with(&compressed_nbhds[pivot]);
//             h_cands.set(pivot, false);

//             let mut excluded_holds = FixedBitSet::with_capacity(label.len());

//             for w in h_cands.ones() {
//                 let mut h_label = label.clone();
//                 h_label.intersect_with(&compressed_nbhds[w]);
//                 h_label.difference_with(&excluded_holds);

//                 let mut new_hv = hv.clone();
//                 new_hv.push(w);

//                 stack.push(SCTnodeChn { label: h_label, p, h: h + 1, pv: pv.clone(), hv: new_hv });
//                 excluded_holds.insert(w);
//             }
//         }
//     }
//     local_counts
// }


// // ███████ ██████   ██████  ███████ 
// // ██      ██   ██ ██       ██      
// // █████   ██   ██ ██   ███ █████   
// // ██      ██   ██ ██    ██ ██      
// // ███████ ██████   ██████  ███████ 


// #[inline]
// fn normalize_edge(u: usize, v: usize) -> (usize, usize) {
//     if u < v { (u, v) } else { (v, u) }
// }


// // --- Edge PyFunction ---
// #[pyfunction]
// pub fn count_edge(
//     py: Python, // <-- PyO3 injects the GIL token here
//     edges: Vec<(usize, usize)>, 
//     n: usize, 
//     procs: usize, 
//     min_k: usize, 
//     max_k: usize
// ) -> PyResult<HashMap<(usize, usize), Vec<BigUint>>> {
    
//     // 1. Build Compressed Neighborhoods
//     let (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k) = 
//         setup_graph(&edges, n, min_k, max_k);

//     let v_prime = valid_roots.len();

//     // 2. Setup the Cancellation Token & Channel
//     let cancel = Arc::new(AtomicBool::new(false));
//     let cancel_worker = Arc::clone(&cancel); 
//     let (tx, rx) = mpsc::channel();

//     // 3. Spawn Rayon in the Background Thread
//     std::thread::spawn(move || {
//         let pool = rayon::ThreadPoolBuilder::new().num_threads(procs).build().unwrap();

//         let compressed_results = pool.install(|| {
//             (0..v_prime)
//                 .into_par_iter()
//                 .map(|new_v| {
//                     // Initialize the root task dynamically
//                     let mut initial_label = FixedBitSet::with_capacity(v_prime);
//                     for &u in &compressed_degen_nbhds[new_v] {
//                         initial_label.insert(u);
//                     }
//                     let root_node = SCTnodeChn {
//                         label: initial_label,
//                         p: 0,
//                         h: 1,
//                         pv: Vec::new(),
//                         hv: vec![new_v],
//                     };

//                     branch_edge(
//                         root_node, 
//                         &compressed_nbhds, 
//                         min_k, 
//                         effective_max_k,
//                         &cancel_worker // Pass token to worker
//                     )
//                 })
//                 // Thread-Local Accumulator HashMap
//                 .fold(
//                     || -> HashMap<(usize, usize), Vec<BigUint>> { HashMap::new() },
//                     |mut acc: HashMap<(usize, usize), Vec<BigUint>>, local_map: HashMap<(usize, usize), Vec<BigUint>>| {
//                         if !cancel_worker.load(Ordering::Relaxed) {
//                             for (e, counts) in local_map {
//                                 let target = acc.entry(e).or_insert_with(|| vec![BigUint::zero(); effective_max_k + 1]);
//                                 for i in 0..counts.len() { target[i] += &counts[i]; }
//                             }
//                         }
//                         acc
//                     }
//                 )
//                 // Global Merge
//                 .reduce(
//                     || -> HashMap<(usize, usize), Vec<BigUint>> { HashMap::new() },
//                     |mut acc1: HashMap<(usize, usize), Vec<BigUint>>, acc2: HashMap<(usize, usize), Vec<BigUint>>| {
//                         if !cancel_worker.load(Ordering::Relaxed) {
//                             for (e, counts) in acc2 {
//                                 let target = acc1.entry(e).or_insert_with(|| vec![BigUint::zero(); effective_max_k + 1]);
//                                 for i in 0..counts.len() { target[i] += &counts[i]; }
//                             }
//                         }
//                         acc1
//                     }
//                 )
//         });

//         // Send the result back to the main thread
//         let _ = tx.send(compressed_results);
//     });

//     // 4. The Main Thread Watchdog
//     let compressed_results = loop {
//         // Ask Python if the user hit Ctrl+C
//         if let Err(e) = py.check_signals() {
//             // Instantly flip the atomic flag so Rayon threads commit suicide
//             cancel.store(true, Ordering::Relaxed);
//             return Err(e); 
//         }

//         // Check if Rayon finished its work
//         match rx.recv_timeout(Duration::from_millis(50)) {
//             Ok(results) => break results, // Done! Exit loop with the data.
//             Err(mpsc::RecvTimeoutError::Timeout) => continue, // Still working.
//             Err(mpsc::RecvTimeoutError::Disconnected) => {
//                 return Err(pyo3::exceptions::PyRuntimeError::new_err("Rust worker thread crashed."));
//             }
//         }
//     };

//     // 5. Remap back to original graph IDs and format for Python
//     let mut final_counts = HashMap::new();
//     for ((new_u, new_v), mut counts) in compressed_results {
//         let old_u = valid_roots[new_u];
//         let old_v = valid_roots[new_v];
        
//         // Ensure edge direction remains consistent after translating IDs
//         let norm_e = normalize_edge(old_u, old_v);

//         let mut actual_max = counts.len().saturating_sub(1);
//         while actual_max > 0 && counts[actual_max].is_zero() { actual_max -= 1; }
//         counts.truncate(actual_max + 1);

//         final_counts.insert(norm_e, counts);
//     }

//     Ok(final_counts)
// }

// // --- Edge Hot Loop ---
// fn branch_edge(
//     root_node: SCTnodeChn,
//     compressed_nbhds: &[Vec<usize>],
//     min_k: usize,
//     max_k: usize,
//     cancel_flag: &AtomicBool // <-- Added token
// ) -> HashMap<(usize, usize), Vec<BigUint>> {

//     let mut local_counts = HashMap::new();
//     let mut stack = Vec::new();
//     stack.push(root_node);

//     let mut iteration = 0usize;

//     while let Some(SCTnodeChn { label, p, h, pv, hv }) = stack.pop() {
        
//         // --- Cooperative Cancellation Check ---
//         iteration = iteration.wrapping_add(1);
//         if iteration & 1023 == 0 {
//             if cancel_flag.load(Ordering::Relaxed) {
//                 return HashMap::new(); // Drop the branch instantly
//             }
//         }

//         let size = label.count_ones(..);

//         // --- Leaf Node Reached ---
//         if size == 0 {
//             let max_i = std::cmp::min(p, max_k.saturating_sub(h));
//             if h + max_i >= min_k {
//                 for i in 0..=max_i {
//                     let k = h + i;
//                     if k < min_k || k < 2 || k > max_k { continue; }

//                     let ncr_0 = ncr(p, i);
                    
//                     let ncr_1 = if i > 0 && p > 0 {
//                         (&ncr_0 * i.to_biguint().unwrap()) / p.to_biguint().unwrap()
//                     } else { BigUint::zero() };
                    
//                     let ncr_2 = if i > 1 && p > 1 {
//                         (&ncr_1 * (i - 1).to_biguint().unwrap()) / (p - 1).to_biguint().unwrap()
//                     } else { BigUint::zero() };

//                     // Case A: Both Holds
//                     if !ncr_0.is_zero() && hv.len() >= 2 {
//                         for x in 0..hv.len() {
//                             for y in (x + 1)..hv.len() {
//                                 let e = normalize_edge(hv[x], hv[y]);
//                                 let target = local_counts.entry(e).or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
//                                 target[k] += &ncr_0;
//                             }
//                         }
//                     }

//                     // Case B: One Hold, One Pivot
//                     if !ncr_1.is_zero() && !hv.is_empty() && !pv.is_empty() {
//                         for &n1 in &hv {
//                             for &n2 in &pv {
//                                 let e = normalize_edge(n1, n2);
//                                 let target = local_counts.entry(e).or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
//                                 target[k] += &ncr_1;
//                             }
//                         }
//                     }

//                     // Case C: Both Pivots
//                     if !ncr_2.is_zero() && pv.len() >= 2 {
//                         for x in 0..pv.len() {
//                             for y in (x + 1)..pv.len() {
//                                 let e = normalize_edge(pv[x], pv[y]);
//                                 let target = local_counts.entry(e).or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
//                                 target[k] += &ncr_2;
//                             }
//                         }
//                     }
//                 }
//             }
//             continue;
//         }

//         if h + p + size < min_k { continue; }

//         // --- Find the Pivot ---
//         let mut pivot = 0;
//         let mut max_degree = 0;
//         for w in label.ones() {
//             let mut isect = label.clone();
//             isect.intersect_with(&compressed_nbhds[w]);
//             let deg = isect.count_ones(..);
//             if deg >= max_degree {
//                 max_degree = deg;
//                 pivot = w;
//                 if max_degree == size - 1 { break; } 
//             }
//         }

//         // --- 1. Pivot Branch ---
//         let mut p_label = label.clone();
//         p_label.intersect_with(&compressed_nbhds[pivot]);
//         let mut new_pv = pv.clone();
//         new_pv.push(pivot);
//         stack.push(SCTnodeChn { label: p_label, p: p + 1, h, pv: new_pv, hv: hv.clone() });

//         // --- 2. Hold Branches ---
//         if h + 1 <= max_k {
//             let mut h_cands = label.clone();
//             h_cands.difference_with(&compressed_nbhds[pivot]);
//             h_cands.set(pivot, false);

//             let mut excluded_holds = FixedBitSet::with_capacity(label.len());
//             for w in h_cands.ones() {
//                 let mut h_label = label.clone();
//                 h_label.intersect_with(&compressed_nbhds[w]);
//                 h_label.difference_with(&excluded_holds);
                
//                 let mut new_hv = hv.clone();
//                 new_hv.push(w);
//                 stack.push(SCTnodeChn { label: h_label, p, h: h + 1, pv: pv.clone(), hv: new_hv });
//                 excluded_holds.insert(w);
//             }
//         }
//     }
//     local_counts
// }

