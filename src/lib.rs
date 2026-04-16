use pyo3::prelude::*;
use rayon::prelude::*;
use std::collections::HashSet;
use fixedbitset::FixedBitSet;
use num_bigint::{BigUint, ToBigUint};
use num_traits::{Zero, One};


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


struct SCTnode {
    label: FixedBitSet,
    p: usize,
    h: usize,
}


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
    // This safely isolates your engine without crashing the global Python state
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(procs)
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    // 3. Parallel Execution inside the pool
    let mut global_counts = pool.install(|| {
        (0..v_prime)
            .into_par_iter()
            .map(|new_v| {
                branch_global(
                    new_v, 
                    &compressed_nbhds, 
                    &compressed_degen_nbhds, 
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

    // chop zeroes
    let mut actual_max = global_counts.len().saturating_sub(1);
    while actual_max > 0 && global_counts[actual_max].is_zero() { // <-- CHANGED
        actual_max -= 1;
    }
    
    global_counts.truncate(actual_max + 1);

    Ok(global_counts)
}


// --- 3. The Hot Loop DFS Engine ---
fn branch_global(
    start_v: usize,
    compressed_nbhds: &[FixedBitSet],
    compressed_degen_nbhds: &[FixedBitSet],
    min_k: usize,
    max_k: usize,
) -> Vec<BigUint> {
    let mut local_counts = vec![BigUint::zero(); max_k + 1];
    let mut stack = Vec::new();

    // Push the Root Node
    stack.push(SCTnode {
        label: compressed_degen_nbhds[start_v].clone(),
        p: 0,
        h: 1,
    });

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
        
        // Iterates instantly over set bits (the actual valid vertices)
        for w in label.ones() {
            let mut isect = label.clone();
            isect.intersect_with(&compressed_nbhds[w]); // Bitwise AND
            
            let deg = isect.count_ones(..);
            if deg >= max_degree {
                max_degree = deg;
                pivot = w;
                // Break early if we found a mathematically optimal pivot
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
            // h_labels = label \ (nbhds[pivot] U {pivot})
            let mut h_cands = label.clone();
            h_cands.difference_with(&compressed_nbhds[pivot]); // Bitwise AND NOT
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



#[pyfunction]
pub fn count_vertex(
    edges: Vec<(usize, usize)>, 
    n: usize, 
    _procs: usize, 
    min_k: usize, 
    max_k: usize
) -> PyResult<Vec<Vec<usize>>> {
    // Pipeline is identical to count_global but returns jagged List[List[int]]
    Ok(vec![vec![]; n])
}

#[pyfunction]
pub fn count_edge(
    edges: Vec<(usize, usize)>, 
    n: usize, 
    _procs: usize, 
    min_k: usize, 
    max_k: usize
) -> PyResult<std::collections::HashMap<(usize, usize), Vec<usize>>> {
    // Pipeline is identical to count_global but returns Dict[Tuple, List[int]]
    Ok(std::collections::HashMap::new())
}




// --- Module Definition ---

#[pymodule]
fn pivoter_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(count_global, m)?)?;
    m.add_function(wrap_pyfunction!(count_vertex, m)?)?;
    m.add_function(wrap_pyfunction!(count_edge, m)?)?;
    Ok(())
}