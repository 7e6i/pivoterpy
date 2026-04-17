use pyo3::prelude::*;
use rayon::prelude::*;
use std::collections::HashMap;

use fixedbitset::FixedBitSet;
use num_bigint::{BigUint, ToBigUint};
use num_traits::{Zero, One};


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

// --- Module Definition ---

#[pymodule]
fn pivoter_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(count_global, m)?)?;
    m.add_function(wrap_pyfunction!(count_vertex, m)?)?;
    m.add_function(wrap_pyfunction!(count_edge, m)?)?;
    m.add_function(wrap_pyfunction!(count_global_exp, m)?)?;
    Ok(())
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
) -> (Vec<FixedBitSet>, Vec<FixedBitSet>, Vec<usize>, usize) {
    
    // ---------------------------------------------------------
    // 1. Build initial neighborhoods and degree buckets
    // ---------------------------------------------------------
    let mut nbhds = vec![FixedBitSet::with_capacity(n); n];
    let mut degrees = vec![0; n];

    for &(u, v) in edges {
        nbhds[u].insert(v);
        nbhds[v].insert(u);
        degrees[u] += 1;
        degrees[v] += 1;
    }

    let mut by_degrees = vec![vec![]; n];
    for (v, &deg) in degrees.iter().enumerate() {
        by_degrees[deg].push(v);
    }

    // ---------------------------------------------------------
    // 2. Matula-Beck Degeneracy Ordering O(m)
    // ---------------------------------------------------------
    let mut degen_ranks = vec![0; n]; // degen_ranks[v] = rank of v
    let mut core_numbers = vec![0; n];
    let mut degeneracy = 0;
    let mut min_deg = 0;
    let mut processed = vec![false; n];

    for rank in 0..n {
        while min_deg < n && by_degrees[min_deg].is_empty() {
            min_deg += 1;
        }

        let v = by_degrees[min_deg].pop().unwrap();
        processed[v] = true;
        degen_ranks[v] = rank;

        degeneracy = std::cmp::max(degeneracy, min_deg);
        core_numbers[v] = degeneracy;

        // .ones() is a blazingly fast FixedBitSet iterator 
        for w in nbhds[v].ones() {
            if !processed[w] {
                let old_deg = degrees[w];
                if let Some(pos) = by_degrees[old_deg].iter().position(|&x| x == w) {
                    by_degrees[old_deg].swap_remove(pos);
                }
                degrees[w] -= 1;
                let new_deg = degrees[w];
                by_degrees[new_deg].push(w);

                if new_deg < min_deg {
                    min_deg = new_deg;
                }
            }
        }
    }

    // ---------------------------------------------------------
    // 3. Compute topological limits
    // ---------------------------------------------------------
    let effective_max_k = std::cmp::min(max_k, degeneracy + 1);
    let core_threshold = if min_k > 0 { min_k - 1 } else { 0 };


    // ---------------------------------------------------------
    // 4. Graph Compression (Vertex ID Remapping)
    // ---------------------------------------------------------
    
    // 4a. Build the Translation Map
    let mut valid_roots = Vec::new();           // This acts as our `new_to_old` dictionary
    let mut old_to_new = vec![usize::MAX; n];   // usize::MAX represents a "ghost" node

    for v in 0..n {
        if core_numbers[v] >= core_threshold {
            let new_id = valid_roots.len();
            old_to_new[v] = new_id;
            valid_roots.push(v); 
        }
    }

    let v_prime = valid_roots.len();

    // 4b. Allocate the hyper-compressed data structures
    // These only take V' memory instead of N memory!
    let mut compressed_nbhds = vec![FixedBitSet::with_capacity(v_prime); v_prime];
    let mut compressed_degen_nbhds = vec![FixedBitSet::with_capacity(v_prime); v_prime];

    // 4c. Populate the compressed graph using the translation map
    for new_v in 0..v_prime {
        let old_v = valid_roots[new_v];
        let v_rank = degen_ranks[old_v];

        // Iterate through the original uncompressed neighborhood
        for old_u in nbhds[old_v].ones() {
            let new_u = old_to_new[old_u];

            // If new_u != MAX, the neighbor survived the core threshold
            if new_u != usize::MAX {
                // 1. Add to the omnidirectional compressed neighborhood
                compressed_nbhds[new_v].insert(new_u);

                // 2. Add to the forward-directional neighborhood (if rank is higher)
                if degen_ranks[old_u] > v_rank {
                    compressed_degen_nbhds[new_v].insert(new_u);
                }
            }
        }
    }

    // We no longer need the massive, original `nbhds`. It gets dropped from RAM here.
    (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k)
}


#[inline]
fn ncr(n: usize, k: usize) -> BigUint {
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


#[pyfunction]
pub fn count_global(
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

    // 2. Initialize a custom Rayon ThreadPool
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(procs)
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    // 3. Parallel Execution inside the pool
    let mut global_counts = pool.install(|| {
        (0..v_prime)
            .into_par_iter()
            .map(|new_v| {
                // Initialize the root task dynamically
                let root_node = SCTnode {
                    label: compressed_degen_nbhds[new_v].clone(),
                    p: 0,
                    h: 1,
                };

                // Pass it to the unified DFS engine
                branch_global(
                    root_node, 
                    &compressed_nbhds, 
                    min_k, 
                    effective_max_k
                )
            })
            .reduce(
                || vec![BigUint::zero(); effective_max_k + 1],
                |mut acc, local| {
                    for i in 0..acc.len() {
                        acc[i] += &local[i];
                    }
                    acc
                }
            )
    });

    // 4. Chop Trailing Zeroes
    let mut actual_max = global_counts.len().saturating_sub(1);
    while actual_max > 0 && global_counts[actual_max].is_zero() { 
        actual_max -= 1;
    }
    
    global_counts.truncate(actual_max + 1);

    Ok(global_counts)
}


// --- 3. The Unified Hot Loop DFS Engine ---
fn branch_global(
    root_node: SCTnode, // Now accepts any initialized task node
    compressed_nbhds: &[FixedBitSet],
    min_k: usize,
    max_k: usize,
) -> Vec<BigUint> {
    let mut local_counts = vec![BigUint::zero(); max_k + 1];
    let mut stack = Vec::new();

    // Start directly from the provided task
    stack.push(root_node);

    while let Some(SCTnode { label, p, h }) = stack.pop() {
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
        
        stack.push(SCTnode {
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


// ██    ██ ███████ ██████  ████████ ███████ ██   ██ 
// ██    ██ ██      ██   ██    ██    ██       ██ ██  
// ██    ██ █████   ██████     ██    █████     ███   
//  ██  ██  ██      ██   ██    ██    ██       ██ ██  
//   ████   ███████ ██   ██    ██    ███████ ██   ██ 


// --- Vertex PyFunction ---
#[pyfunction]
pub fn count_vertex(
    edges: Vec<(usize, usize)>, 
    n: usize, 
    procs: usize, 
    min_k: usize, 
    max_k: usize
) -> PyResult<Vec<Vec<BigUint>>> {
    
    let (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k) = 
        setup_graph(&edges, n, min_k, max_k);

    let v_prime = valid_roots.len();
    let pool = rayon::ThreadPoolBuilder::new().num_threads(procs).build().unwrap();

    let mut compressed_results = pool.install(|| {
        (0..v_prime)
            .into_par_iter()
            .map(|new_v| {
                branch_vertex(new_v, &compressed_nbhds, &compressed_degen_nbhds, min_k, effective_max_k)
            })
            // Thread-Local Accumulator (v_prime matrix)
            .fold(
                || vec![vec![]; v_prime], 
                |mut acc, local_map| {
                    for (v, counts) in local_map {
                        if acc[v].is_empty() { acc[v] = vec![BigUint::zero(); effective_max_k + 1]; }
                        for i in 0..counts.len() { acc[v][i] += &counts[i]; }
                    }
                    acc
                }
            )
            // Global Merge
            .reduce(
                || vec![vec![]; v_prime],
                |mut acc1, acc2| {
                    for v in 0..v_prime {
                        if !acc2[v].is_empty() {
                            if acc1[v].is_empty() {
                                acc1[v] = acc2[v].clone();
                            } else {
                                for i in 0..acc2[v].len() { acc1[v][i] += &acc2[v][i]; }
                            }
                        }
                    }
                    acc1
                }
            )
    });

    // Remap to original IDs and chop zeroes
    let mut final_counts = vec![vec![]; n];
    for new_id in 0..v_prime {
        let old_id = valid_roots[new_id];
        let mut counts = std::mem::take(&mut compressed_results[new_id]);
        
        if !counts.is_empty() {
            let mut actual_max = counts.len().saturating_sub(1);
            while actual_max > 0 && counts[actual_max].is_zero() { actual_max -= 1; }
            counts.truncate(actual_max + 1);
        }
        final_counts[old_id] = counts;
    }

    Ok(final_counts)
}

// --- Vertex Hot Loop ---
fn branch_vertex(
    start_v: usize,
    compressed_nbhds: &[FixedBitSet],
    compressed_degen_nbhds: &[FixedBitSet],
    min_k: usize,
    max_k: usize,
) -> HashMap<usize, Vec<BigUint>> {
    let mut local_counts = HashMap::new();
    let mut stack = Vec::new();

    stack.push(SCTnodeChn {
        label: compressed_degen_nbhds[start_v].clone(),
        p: 0,
        h: 1,
        pv: Vec::new(),
        hv: vec![start_v], // The root is always a hold
    });

    while let Some(SCTnodeChn { label, p, h, pv, hv }) = stack.pop() {
        let size = label.count_ones(..);

        // --- Leaf Node Reached ---
        if size == 0 {
            let max_i = std::cmp::min(p, max_k.saturating_sub(h));
            if h + max_i >= min_k {
                for i in 0..=max_i {
                    let k = h + i;
                    if k >= min_k && k <= max_k {
                        let ncr_0 = ncr(p, i);
                        
                        if !ncr_0.is_zero() {
                            // Apply to all Hold nodes
                            for &v_hold in &hv {
                                let target = local_counts
                                    .entry(v_hold)
                                    .or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
                                target[k] += &ncr_0;
                            }
                            
                            // Apply to all Pivot nodes
                            if i > 0 && p > 0 {
                                let mut ncr_p = &ncr_0 * i.to_biguint().unwrap();
                                ncr_p /= p.to_biguint().unwrap();
                                
                                if !ncr_p.is_zero() {
                                    for &v_pivot in &pv {
                                        let target = local_counts
                                            .entry(v_pivot)
                                            .or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
                                        target[k] += &ncr_p;
                                    }
                                }
                            }
                        }
                    }
                }
            }
            continue;
        }

        if h + p + size < min_k { continue; }

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
        
        let mut new_pv = pv.clone();
        new_pv.push(pivot);
        
        stack.push(SCTnodeChn { label: p_label, p: p + 1, h, pv: new_pv, hv: hv.clone() });

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

                let mut new_hv = hv.clone();
                new_hv.push(w);

                stack.push(SCTnodeChn { label: h_label, p, h: h + 1, pv: pv.clone(), hv: new_hv });
                excluded_holds.insert(w);
            }
        }
    }
    local_counts
}


// ███████ ██████   ██████  ███████ 
// ██      ██   ██ ██       ██      
// █████   ██   ██ ██   ███ █████   
// ██      ██   ██ ██    ██ ██      
// ███████ ██████   ██████  ███████ 


#[inline]
fn normalize_edge(u: usize, v: usize) -> (usize, usize) {
    if u < v { (u, v) } else { (v, u) }
}


// --- Edge PyFunction ---
#[pyfunction]
pub fn count_edge(
    edges: Vec<(usize, usize)>, 
    n: usize, 
    procs: usize, 
    min_k: usize, 
    max_k: usize
) -> PyResult<HashMap<(usize, usize), Vec<BigUint>>> {
    
    let (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k) = 
        setup_graph(&edges, n, min_k, max_k);

    let v_prime = valid_roots.len();
    let pool = rayon::ThreadPoolBuilder::new().num_threads(procs).build().unwrap();

    let compressed_results = pool.install(|| {
        (0..v_prime)
            .into_par_iter()
            .map(|new_v| {
                branch_edge(new_v, &compressed_nbhds, &compressed_degen_nbhds, min_k, effective_max_k)
            })
            // Thread-Local Accumulator HashMap
            .fold(
                || HashMap::new(),
                |mut acc, local_map| {
                    for (e, counts) in local_map {
                        let target = acc.entry(e).or_insert_with(|| vec![BigUint::zero(); effective_max_k + 1]);
                        for i in 0..counts.len() { target[i] += &counts[i]; }
                    }
                    acc
                }
            )
            // Global Merge
            .reduce(
                || HashMap::new(),
                |mut acc1, acc2| {
                    for (e, counts) in acc2 {
                        let target = acc1.entry(e).or_insert_with(|| vec![BigUint::zero(); effective_max_k + 1]);
                        for i in 0..counts.len() { target[i] += &counts[i]; }
                    }
                    acc1
                }
            )
    });

    // Remap back to original graph IDs and format for Python
    let mut final_counts = HashMap::new();
    for ((new_u, new_v), mut counts) in compressed_results {
        let old_u = valid_roots[new_u];
        let old_v = valid_roots[new_v];
        
        let norm_e = normalize_edge(old_u, old_v);

        let mut actual_max = counts.len().saturating_sub(1);
        while actual_max > 0 && counts[actual_max].is_zero() { actual_max -= 1; }
        counts.truncate(actual_max + 1);

        final_counts.insert(norm_e, counts);
    }

    Ok(final_counts)
}


// --- Edge Hot Loop ---
fn branch_edge(
    start_v: usize,
    compressed_nbhds: &[FixedBitSet],
    compressed_degen_nbhds: &[FixedBitSet],
    min_k: usize,
    max_k: usize,
) -> HashMap<(usize, usize), Vec<BigUint>> {
    let mut local_counts = HashMap::new();
    let mut stack = Vec::new();

    stack.push(SCTnodeChn {
        label: compressed_degen_nbhds[start_v].clone(),
        p: 0,
        h: 1,
        pv: Vec::new(),
        hv: vec![start_v],
    });

    while let Some(SCTnodeChn { label, p, h, pv, hv }) = stack.pop() {
        let size = label.count_ones(..);

        if size == 0 {
            let max_i = std::cmp::min(p, max_k.saturating_sub(h));
            if h + max_i >= min_k {
                for i in 0..=max_i {
                    let k = h + i;
                    if k < min_k || k < 2 || k > max_k { continue; }

                    let ncr_0 = ncr(p, i);
                    
                    let ncr_1 = if i > 0 && p > 0 {
                        (&ncr_0 * i.to_biguint().unwrap()) / p.to_biguint().unwrap()
                    } else { BigUint::zero() };
                    
                    let ncr_2 = if i > 1 && p > 1 {
                        (&ncr_1 * (i - 1).to_biguint().unwrap()) / (p - 1).to_biguint().unwrap()
                    } else { BigUint::zero() };

                    // Case A: Both Holds
                    if !ncr_0.is_zero() && hv.len() >= 2 {
                        for x in 0..hv.len() {
                            for y in (x + 1)..hv.len() {
                                let e = normalize_edge(hv[x], hv[y]);
                                let target = local_counts.entry(e).or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
                                target[k] += &ncr_0;
                            }
                        }
                    }

                    // Case B: One Hold, One Pivot
                    if !ncr_1.is_zero() && !hv.is_empty() && !pv.is_empty() {
                        for &n1 in &hv {
                            for &n2 in &pv {
                                let e = normalize_edge(n1, n2);
                                let target = local_counts.entry(e).or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
                                target[k] += &ncr_1;
                            }
                        }
                    }

                    // Case C: Both Pivots
                    if !ncr_2.is_zero() && pv.len() >= 2 {
                        for x in 0..pv.len() {
                            for y in (x + 1)..pv.len() {
                                let e = normalize_edge(pv[x], pv[y]);
                                let target = local_counts.entry(e).or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
                                target[k] += &ncr_2;
                            }
                        }
                    }
                }
            }
            continue;
        }

        if h + p + size < min_k { continue; }

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
        let mut new_pv = pv.clone();
        new_pv.push(pivot);
        stack.push(SCTnodeChn { label: p_label, p: p + 1, h, pv: new_pv, hv: hv.clone() });

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
                
                let mut new_hv = hv.clone();
                new_hv.push(w);
                stack.push(SCTnodeChn { label: h_label, p, h: h + 1, pv: pv.clone(), hv: new_hv });
                excluded_holds.insert(w);
            }
        }
    }
    local_counts
}



// ███████ ██   ██ ██████  ███████ ██████  ██ ███    ███ ███████ ███    ██ ████████  █████  ██      
// ██       ██ ██  ██   ██ ██      ██   ██ ██ ████  ████ ██      ████   ██    ██    ██   ██ ██      
// █████     ███   ██████  █████   ██████  ██ ██ ████ ██ █████   ██ ██  ██    ██    ███████ ██      
// ██       ██ ██  ██      ██      ██   ██ ██ ██  ██  ██ ██      ██  ██ ██    ██    ██   ██ ██      
// ███████ ██   ██ ██      ███████ ██   ██ ██ ██      ██ ███████ ██   ████    ██    ██   ██ ███████ 


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
    // Phase 2: Massively Parallel Execution
    // ---------------------------------------------------------
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(procs)
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    let parallel_counts = pool.install(|| {
        task_queue
            .into_par_iter() // Parallelize over the fine-grained tasks, not the roots!
            .map(|task| {
                branch_global(
                    task, 
                    &compressed_nbhds, 
                    min_k, 
                    effective_max_k
                )
            })
            .reduce(
                || vec![BigUint::zero(); effective_max_k + 1],
                |mut acc, local| {
                    for i in 0..acc.len() {
                        acc[i] += &local[i];
                    }
                    acc
                }
            )
    });

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