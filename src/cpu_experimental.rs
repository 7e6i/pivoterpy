// src/cpu_exp.rs


use pyo3::prelude::*;
use rayon::prelude::*;

use fixedbitset::FixedBitSet;
use num_bigint::{BigUint};
use num_traits::{Zero};

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, mpsc};
use std::time::Duration;


use crate::cpu_backend::setup_graph;
use crate::cpu_backend::ncr;

struct SCTnode {
    label: FixedBitSet,
    p: usize,
    h: usize,
}


// ███████ ██   ██ ██████  ███████ ██████  ██ ███    ███ ███████ ███    ██ ████████  █████  ██      
// ██       ██ ██  ██   ██ ██      ██   ██ ██ ████  ████ ██      ████   ██    ██    ██   ██ ██      
// █████     ███   ██████  █████   ██████  ██ ██ ████ ██ █████   ██ ██  ██    ██    ███████ ██      
// ██       ██ ██  ██      ██      ██   ██ ██ ██  ██  ██ ██      ██  ██ ██    ██    ██   ██ ██      
// ███████ ██   ██ ██      ███████ ██   ██ ██ ██      ██ ███████ ██   ████    ██    ██   ██ ███████ 


/*
Focuses on parallelizing at level 2 nodes by looping through the level 1 (degen order) nodes
and adding their children to a list. By performing DFS on the level 2 nodes, we aim to 
create more units of work, allowing for the Rayon work stealing to better distribute the load.

While the inital setup work recaculates the neighborhood bitsets on the induced subgraph of 
the min_k-core, this optimization does not re-calculate the induced subgraphs for level 1 nodes.
*/

// --- 1. Sequential Expansion (Level 1) ---
fn expand_root(
    start_v: usize,
    compressed_nbhds: &[FixedBitSet],
    compressed_degen_nbhds: &[FixedBitSet],
    min_k: usize,
    max_k: usize,
) -> (Vec<BigUint>, Vec<SCTnode>) {
    let mut local_counts = vec![BigUint::zero(); max_k + 1];
    let mut sub_tasks = Vec::new();

    let label = compressed_degen_nbhds[start_v].clone();
    let p = 0;
    let h = 1;
    let size = label.count_ones(..);

    // --- Leaf Node Reached Immediately ---
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
        return (local_counts, sub_tasks);
    }

    // --- Pruning Wall ---
    if h + p + size < min_k {
        return (local_counts, sub_tasks);
    }

    // --- Find the Pivot ---
    let mut pivot = 0;
    let mut max_degree = 0;
    
    for w in label.ones() {
        let mut isect = label.clone();
        isect.intersect_with(&compressed_nbhds[w]); 
        
        let deg = isect.count_ones(..);
        if deg >= max_degree {
            max_degree = deg;
            pivot = w;
            if max_degree == size - 1 { break; } 
        }
    }

    // --- 1. Pivot Branch ---
    let mut p_label = label.clone();
    p_label.intersect_with(&compressed_nbhds[pivot]);
    
    sub_tasks.push(SCTnode {
        label: p_label,
        p: p + 1,
        h,
    });

    // --- 2. Hold Branches ---
    if h + 1 <= max_k {
        let mut h_cands = label.clone();
        h_cands.difference_with(&compressed_nbhds[pivot]); 
        h_cands.set(pivot, false);

        let mut excluded_holds = FixedBitSet::with_capacity(label.len());

        for w in h_cands.ones() {
            let mut h_label = label.clone();
            h_label.intersect_with(&compressed_nbhds[w]);
            h_label.difference_with(&excluded_holds);

            sub_tasks.push(SCTnode {
                label: h_label,
                p,
                h: h + 1,
            });
            
            excluded_holds.insert(w);
        }
    }

    (local_counts, sub_tasks)
}


#[pyfunction]
pub fn count_global_exp(
    py: Python, // <-- PyO3 injects the GIL token here
    edges: Vec<(usize, usize)>, 
    n: usize, 
    procs: usize, 
    min_k: usize, 
    max_k: usize
) -> PyResult<Vec<BigUint>> {
    
    let (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k) = 
        setup_graph(&edges, n, min_k, max_k);

    let v_prime = valid_roots.len();
    let mut global_counts = vec![BigUint::zero(); effective_max_k + 1];
    
    // ---------------------------------------------------------
    // Phase 1: Sequential Task Generation
    // ---------------------------------------------------------
    let mut task_queue: Vec<SCTnode> = Vec::new();

    for new_v in 0..v_prime {
        let (root_counts, mut sub_tasks) = expand_root(
            new_v, 
            &compressed_nbhds, 
            &compressed_degen_nbhds, 
            min_k, 
            effective_max_k
        );

        // Add any trivial/immediate leaf counts to the global total
        for i in 0..global_counts.len() {
            global_counts[i] += &root_counts[i];
        }

        // Append to our massive queue of independent jobs
        task_queue.append(&mut sub_tasks);
    }

    // ---------------------------------------------------------
    // Phase 2: Setup the Cancellation Token & Channel
    // ---------------------------------------------------------
    let cancel = Arc::new(AtomicBool::new(false));
    let cancel_worker = Arc::clone(&cancel); 
    let (tx, rx) = mpsc::channel();

    // ---------------------------------------------------------
    // Phase 3: Massively Parallel Execution (Background Thread)
    // ---------------------------------------------------------
    std::thread::spawn(move || {
        let pool = rayon::ThreadPoolBuilder::new().num_threads(procs).build().unwrap();

        let parallel_counts = pool.install(|| {
            task_queue
                .into_par_iter() // Parallelize over the fine-grained tasks, not the roots!
                .map(|task| {
                    branch_global_compress(
                        task, 
                        &compressed_nbhds, 
                        min_k, 
                        effective_max_k,
                        &cancel_worker // Pass token to worker
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

    // ---------------------------------------------------------
    // Phase 4: The Main Thread Watchdog
    // ---------------------------------------------------------
    let parallel_counts = loop {
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

    // Merge the parallel results back into the global totals
    for i in 0..global_counts.len() {
        global_counts[i] += &parallel_counts[i];
    }

    // Chop Trailing Zeroes
    let mut actual_max = global_counts.len().saturating_sub(1);
    while actual_max > 0 && global_counts[actual_max].is_zero() {
        actual_max -= 1;
    }
    
    global_counts.truncate(actual_max + 1);

    Ok(global_counts)
}


// --- global hot loop that compresses the provided root_node.label (dege_nbhds)
// and the already compressed neighborhoods

fn branch_global_compress(
    root_node: SCTnode, 
    compressed_nbhds: &[FixedBitSet],
    min_k: usize,
    max_k: usize,
    cancel_flag: &std::sync::atomic::AtomicBool,
) -> Vec<BigUint> {
    let mut local_counts = vec![BigUint::zero(); max_k + 1];

    // --- 1. Map Global IDs to Local IDs ---
    // Extract exactly which global vertices are in this specific sub-problem
    let global_ids: Vec<usize> = root_node.label.ones().collect();
    let n_local = global_ids.len();

    // If the neighborhood is already empty, immediately calculate the leaf score and exit
    // (This saves us from allocating anything at all for dead-end roots)
    if n_local == 0 {
        let p = root_node.p;
        let h = root_node.h;
        let max_i = std::cmp::min(p, max_k.saturating_sub(h));
        if h + max_i >= min_k {
            for i in 0..=max_i {
                let k = h + i;
                if k >= min_k && k <= max_k {
                    local_counts[k] += ncr(p, i);
                }
            }
        }
        return local_counts;
    }

    // --- 2. Allocate and Populate the Micro-Graph ---
    // Create N new bitsets, but each one is strictly N bits wide instead of V bits wide
    let mut local_nbhds = vec![FixedBitSet::with_capacity(n_local); n_local];

    for i in 0..n_local {
        let global_u = global_ids[i];
        for j in 0..n_local {
            // O(1) lookup against the massive global graph
            if i != j && compressed_nbhds[global_u].contains(global_ids[j]) {
                local_nbhds[i].insert(j);
            }
        }
    }

    // --- 3. Translate the Root Label ---
    // In our new micro-universe, the root node contains *every* vertex, so it is all 1s.
    let mut local_root_label = FixedBitSet::with_capacity(n_local);
    local_root_label.insert_range(0..n_local);

    let mut stack = Vec::new();
    stack.push(SCTnode {
        label: local_root_label,
        p: root_node.p,
        h: root_node.h,
    });

    let mut iteration = 0usize;

    // --- 4. Launch the Lightning-Fast DFS ---
    while let Some(SCTnode { label, p, h }) = stack.pop() {
        
        // --- Cooperative Cancellation Check ---
        iteration = iteration.wrapping_add(1);
        if iteration & 1023 == 0 {
            if cancel_flag.load(std::sync::atomic::Ordering::Relaxed) {
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
            let mut isect = label.clone();
            // ONLY DIFFERENCE: We intersect with the micro-graph!
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
        p_label.intersect_with(&local_nbhds[pivot]); // Micro-graph lookup
        
        stack.push(SCTnode {
            label: p_label,
            p: p + 1,
            h,
        });

        // --- 2. Hold Branches ---
        if h + 1 <= max_k {
            let mut h_cands = label.clone();
            h_cands.difference_with(&local_nbhds[pivot]); // Micro-graph lookup
            h_cands.set(pivot, false);

            // Because label capacity is n_local, this is perfectly sized
            let mut excluded_holds = FixedBitSet::with_capacity(n_local);

            for w in h_cands.ones() {
                let mut h_label = label.clone();
                h_label.intersect_with(&local_nbhds[w]); // Micro-graph lookup
                h_label.difference_with(&excluded_holds);

                stack.push(SCTnode {
                    label: h_label,
                    p,
                    h: h + 1,
                });
                
                excluded_holds.insert(w);
            }
        }
    }

    local_counts
}