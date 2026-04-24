use pyo3::prelude::*;
use rayon::prelude::*;
use std::collections::HashMap;

use fixedbitset::FixedBitSet;
use num_bigint::BigUint;
use num_traits::Zero;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, mpsc};
use std::time::Duration;

use super::utils::{precompute_ncr, setup_graph, SCTnode, SCTnodeChn};

//  ██████  ██       ██████  ██████   █████  ██      
// ██       ██      ██    ██ ██   ██ ██   ██ ██      
// ██   ███ ██      ██    ██ ██████  ███████ ██      
// ██    ██ ██      ██    ██ ██   ██ ██   ██ ██      
//  ██████  ███████  ██████  ██████  ██   ██ ███████ 

#[pyfunction]
pub fn count_global(
    py: Python, 
    edges: Vec<(usize, usize)>, 
    n: usize, 
    procs: usize, 
    min_k: usize, 
    max_k: usize
) -> PyResult<Vec<BigUint>> {
    
    let (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k) = 
        setup_graph(&edges, n, min_k, max_k);

    let max_p = compressed_degen_nbhds.iter().map(|nbhd| nbhd.len()).max().unwrap_or(0);

    let v_prime = valid_roots.len();

    let cancel = Arc::new(AtomicBool::new(false));
    let cancel_worker = Arc::clone(&cancel); 
    let (tx, rx) = mpsc::channel();

    std::thread::spawn(move || {
        let pool = rayon::ThreadPoolBuilder::new().num_threads(procs).build().unwrap();
        
        let parallel_counts = pool.install(|| {
            let ncr_table = precompute_ncr(max_p, effective_max_k);

            (0..v_prime)
                .into_par_iter()
                .rev()
                .map(|new_v| {
                    let cands = &compressed_degen_nbhds[new_v];
                    let num_cands = cands.len();

                    if 1 + num_cands < min_k {
                        return vec![BigUint::zero(); effective_max_k + 1];
                    }

                    let mut local_nbhds = vec![FixedBitSet::with_capacity(num_cands); num_cands];

                    for (local_u, &global_u) in cands.iter().enumerate() {
                        for &global_w in &compressed_nbhds[global_u] {
                            if let Ok(local_w) = cands.binary_search(&global_w) {
                                local_nbhds[local_u].insert(local_w);
                            }
                        }
                    }

                    let mut initial_label = FixedBitSet::with_capacity(num_cands);
                    initial_label.insert_range(..); 

                    branch_global(
                        SCTnode {label: initial_label, p: 0, h: 1}, 
                        &local_nbhds, 
                        min_k, 
                        effective_max_k,
                        &cancel_worker,
                        &ncr_table
                    )
                })
                .reduce(
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

        let _ = tx.send(parallel_counts);
    });

    let mut global_counts = loop {
        if let Err(e) = py.check_signals() {
            cancel.store(true, Ordering::Relaxed);
            return Err(e); 
        }

        match rx.recv_timeout(Duration::from_millis(50)) {
            Ok(counts) => break counts, 
            Err(mpsc::RecvTimeoutError::Timeout) => continue, 
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                return Err(pyo3::exceptions::PyRuntimeError::new_err("Rust worker thread crashed."));
            }
        }
    };

    let mut actual_max = global_counts.len().saturating_sub(1);
    while actual_max > 0 && global_counts[actual_max].is_zero() { 
        actual_max -= 1;
    }
    
    global_counts.truncate(actual_max + 1);

    Ok(global_counts)
}

fn branch_global(
    root_node: SCTnode, 
    local_nbhds: &[FixedBitSet],
    min_k: usize,
    max_k: usize,
    cancel_flag: &AtomicBool,
    ncr_table: &Vec<Vec<BigUint>>
) -> Vec<BigUint> {

    let mut local_counts = vec![BigUint::zero(); max_k + 1];
    let mut stack = Vec::new();
    stack.push(root_node);

    let mut iteration = 0usize;

    while let Some(SCTnode { label, p, h }) = stack.pop() {
        
        iteration = iteration.wrapping_add(1);
        if iteration & 1023 == 0 {
            if cancel_flag.load(Ordering::Relaxed) {
                return vec![]; 
            }
        }

        let size = label.count_ones(..);

        if size == 0 {
            let max_i = std::cmp::min(p, max_k.saturating_sub(h));
            if h + max_i >= min_k {
                for i in 0..=max_i {
                    let k = h + i;
                    if k >= min_k && k <= max_k {
                        local_counts[k] += &ncr_table[p][i];
                    }
                }
            }
            continue;
        }

        if h + p + size < min_k {
            continue;
        }

        let mut pivot = 0;
        let mut max_degree = 0;
        
        for w in label.ones() {
            let mut isect = label.clone();
            isect.intersect_with(&local_nbhds[w]);
            
            let deg = isect.count_ones(..);
            if deg >= max_degree {
                max_degree = deg;
                pivot = w;
                if max_degree == size - 1 { break; } 
            }
        }

        let mut p_label = label.clone();
        p_label.intersect_with(&local_nbhds[pivot]);
        
        stack.push(SCTnode { label: p_label, p: p + 1, h });

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

// ██    ██ ███████ ██████  ████████ ███████ ██   ██ 
// ██    ██ ██      ██   ██    ██    ██       ██ ██  
// ██    ██ █████   ██████     ██    █████     ███   
//  ██  ██  ██      ██   ██    ██    ██       ██ ██  
//   ████   ███████ ██   ██    ██    ███████ ██   ██ 

#[pyfunction]
pub fn count_vertex(
    py: Python, 
    edges: Vec<(usize, usize)>, 
    n: usize, 
    procs: usize, 
    min_k: usize, 
    max_k: usize
) -> PyResult<HashMap<usize, Vec<BigUint>>> { 
    
    let (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k) = 
        setup_graph(&edges, n, min_k, max_k);

    let max_p = compressed_degen_nbhds.iter().map(|nbhd| nbhd.len()).max().unwrap_or(0);

    let v_prime = valid_roots.len();
    let cancel = Arc::new(AtomicBool::new(false));
    let cancel_worker = Arc::clone(&cancel); 
    let (tx, rx) = mpsc::channel();

    std::thread::spawn(move || {
        let pool = rayon::ThreadPoolBuilder::new().num_threads(procs).build().unwrap();

        let parallel_results = pool.install(|| {
            let ncr_table = precompute_ncr(max_p, effective_max_k);

            (0..v_prime)
                .into_par_iter()
                .rev()
                .map(|new_v| {
                    let cands = &compressed_degen_nbhds[new_v];
                    let num_cands = cands.len();

                    if 1 + num_cands < min_k {
                        return HashMap::new();
                    }

                    let mut local_nbhds = vec![FixedBitSet::with_capacity(num_cands); num_cands];
                    for (local_u, &global_u) in cands.iter().enumerate() {
                        for &global_w in &compressed_nbhds[global_u] {
                            if let Ok(local_w) = cands.binary_search(&global_w) {
                                local_nbhds[local_u].insert(local_w);
                            }
                        }
                    }

                    let mut initial_label = FixedBitSet::with_capacity(num_cands);
                    initial_label.insert_range(..);

                    let root_node = SCTnodeChn {
                        label: initial_label,
                        p: 0,
                        h: 1,
                        pv: Vec::new(),
                        hv: vec![new_v], 
                    };

                    branch_vertex(
                        root_node, 
                        &local_nbhds, 
                        cands, 
                        min_k, 
                        effective_max_k,
                        &cancel_worker,
                        &ncr_table
                    )
                })
                .fold(
                    || -> HashMap<usize, Vec<BigUint>> { HashMap::new() }, 
                    |mut acc, local_map| {
                        if !cancel_worker.load(Ordering::Relaxed) {
                            for (v, counts) in local_map {
                                let target = acc.entry(v).or_insert_with(|| vec![BigUint::zero(); effective_max_k + 1]);
                                for i in 0..counts.len() { target[i] += &counts[i]; }
                            }
                        }
                        acc
                    }
                )
                .reduce(
                    || -> HashMap<usize, Vec<BigUint>> { HashMap::new() },
                    |mut acc1, acc2| {
                        if !cancel_worker.load(Ordering::Relaxed) {
                            for (v, counts) in acc2 {
                                let target = acc1.entry(v).or_insert_with(|| vec![BigUint::zero(); effective_max_k + 1]);
                                for i in 0..counts.len() { target[i] += &counts[i]; }
                            }
                        }
                        acc1
                    }
                )
        });
        let _ = tx.send(parallel_results);
    });

    let compressed_results = loop {
        if let Err(e) = py.check_signals() {
            cancel.store(true, Ordering::Relaxed);
            return Err(e); 
        }
        match rx.recv_timeout(Duration::from_millis(50)) {
            Ok(results) => break results,
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                return Err(pyo3::exceptions::PyRuntimeError::new_err("Rust worker thread crashed."));
            }
        }
    };

    let mut final_counts = HashMap::new();
    for (new_id, mut counts) in compressed_results {
        let old_id = valid_roots[new_id];
        
        let mut actual_max = counts.len().saturating_sub(1);
        while actual_max > 0 && counts[actual_max].is_zero() { actual_max -= 1; }
        counts.truncate(actual_max + 1);
        
        if counts.iter().any(|c| !c.is_zero()) {
            final_counts.insert(old_id, counts);
        }
    }

    Ok(final_counts)
}

fn branch_vertex(
    root_node: SCTnodeChn,
    local_nbhds: &[FixedBitSet],
    cands: &[usize], 
    min_k: usize,
    max_k: usize,
    cancel_flag: &AtomicBool,
    ncr_table: &Vec<Vec<BigUint>>
) -> HashMap<usize, Vec<BigUint>> {

    let mut local_counts = HashMap::new();
    let mut stack = Vec::new();
    stack.push(root_node);

    let mut iteration = 0usize;

    while let Some(SCTnodeChn { label, p, h, pv, hv }) = stack.pop() {
        iteration = iteration.wrapping_add(1);
        if iteration & 1023 == 0 && cancel_flag.load(Ordering::Relaxed) {
            return HashMap::new(); 
        }

        let size = label.count_ones(..);

        if size == 0 {
            let max_i = std::cmp::min(p, max_k.saturating_sub(h));
            if h + max_i >= min_k {
                for i in 0..=max_i {
                    let k = h + i;
                    if k >= min_k && k <= max_k {
                        let ncr_0 = &ncr_table[p][i];
                        
                        if !ncr_0.is_zero() {
                            for &v_hold in &hv {
                                let target = local_counts.entry(v_hold).or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
                                target[k] += ncr_0;
                            }
                            
                            if i > 0 && p > 0 {
                                let ncr_p = &ncr_table[p - 1][i - 1];
                                
                                if !ncr_p.is_zero() {
                                    for &v_pivot in &pv {
                                        let target = local_counts.entry(v_pivot).or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
                                        target[k] += ncr_p;
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

        let mut pivot = 0;
        let mut max_degree = 0;
        for w in label.ones() {
            let mut isect = label.clone();
            isect.intersect_with(&local_nbhds[w]);
            let deg = isect.count_ones(..);
            if deg >= max_degree {
                max_degree = deg;
                pivot = w;
                if max_degree == size - 1 { break; } 
            }
        }

        let mut p_label = label.clone();
        p_label.intersect_with(&local_nbhds[pivot]);
        
        let mut new_pv = pv.clone();
        new_pv.push(cands[pivot]); 
        
        stack.push(SCTnodeChn { label: p_label, p: p + 1, h, pv: new_pv, hv: hv.clone() });

        if h + 1 <= max_k {
            let mut h_cands = label.clone();
            h_cands.difference_with(&local_nbhds[pivot]);
            h_cands.set(pivot, false);

            let mut excluded_holds = FixedBitSet::with_capacity(label.len());

            for w in h_cands.ones() {
                let mut h_label = label.clone();
                h_label.intersect_with(&local_nbhds[w]);
                h_label.difference_with(&excluded_holds);

                let mut new_hv = hv.clone();
                new_hv.push(cands[w]); 

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

#[pyfunction]
pub fn count_edge(
    py: Python, 
    edges: Vec<(usize, usize)>, 
    n: usize, 
    procs: usize, 
    min_k: usize, 
    max_k: usize
) -> PyResult<HashMap<(usize, usize), Vec<BigUint>>> {
    
    let (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k) = 
        setup_graph(&edges, n, min_k, max_k);
    
    let max_p = compressed_degen_nbhds.iter().map(|nbhd| nbhd.len()).max().unwrap_or(0);

    let v_prime = valid_roots.len();
    let cancel = Arc::new(AtomicBool::new(false));
    let cancel_worker = Arc::clone(&cancel); 
    let (tx, rx) = mpsc::channel();

    std::thread::spawn(move || {
        let pool = rayon::ThreadPoolBuilder::new().num_threads(procs).build().unwrap();

        let compressed_results = pool.install(|| {
            let ncr_table = precompute_ncr(max_p, effective_max_k);
            (0..v_prime)
                .into_par_iter()
                .map(|new_v| {
                    let cands = &compressed_degen_nbhds[new_v];
                    let num_cands = cands.len();

                    if 1 + num_cands < min_k {
                        return HashMap::new();
                    }

                    let mut local_nbhds = vec![FixedBitSet::with_capacity(num_cands); num_cands];
                    for (local_u, &global_u) in cands.iter().enumerate() {
                        for &global_w in &compressed_nbhds[global_u] {
                            if let Ok(local_w) = cands.binary_search(&global_w) {
                                local_nbhds[local_u].insert(local_w);
                            }
                        }
                    }

                    let mut initial_label = FixedBitSet::with_capacity(num_cands);
                    initial_label.insert_range(..);

                    branch_edge(
                        SCTnodeChn {label: initial_label, p: 0, h: 1, pv: Vec::new(), hv: vec![new_v]}, 
                        &local_nbhds, 
                        cands, 
                        min_k, 
                        effective_max_k,
                        &cancel_worker,
                        &ncr_table
                    )
                })
                .fold(
                    || -> HashMap<(usize, usize), Vec<BigUint>> { HashMap::new() },
                    |mut acc, local_map| {
                        if !cancel_worker.load(Ordering::Relaxed) {
                            for (e, counts) in local_map {
                                let target = acc.entry(e).or_insert_with(|| vec![BigUint::zero(); effective_max_k + 1]);
                                for i in 0..counts.len() { target[i] += &counts[i]; }
                            }
                        }
                        acc
                    }
                )
                .reduce(
                    || -> HashMap<(usize, usize), Vec<BigUint>> { HashMap::new() },
                    |mut acc1, acc2| {
                        if !cancel_worker.load(Ordering::Relaxed) {
                            for (e, counts) in acc2 {
                                let target = acc1.entry(e).or_insert_with(|| vec![BigUint::zero(); effective_max_k + 1]);
                                for i in 0..counts.len() { target[i] += &counts[i]; }
                            }
                        }
                        acc1
                    }
                )
        });
        let _ = tx.send(compressed_results);
    });

    let compressed_results = loop {
        if let Err(e) = py.check_signals() {
            cancel.store(true, Ordering::Relaxed);
            return Err(e); 
        }
        match rx.recv_timeout(Duration::from_millis(50)) {
            Ok(results) => break results,
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                return Err(pyo3::exceptions::PyRuntimeError::new_err("Rust worker thread crashed."));
            }
        }
    };

    let mut final_counts = HashMap::new();
    for ((new_u, new_v), mut counts) in compressed_results {
        let old_u = valid_roots[new_u];
        let old_v = valid_roots[new_v];
        
        let norm_e = normalize_edge(old_u, old_v);

        let mut actual_max = counts.len().saturating_sub(1);
        while actual_max > 0 && counts[actual_max].is_zero() { actual_max -= 1; }
        counts.truncate(actual_max + 1);

        if counts.iter().any(|c| !c.is_zero()) {
            final_counts.insert(norm_e, counts);
        }
    }

    Ok(final_counts)
}

fn branch_edge(
    root_node: SCTnodeChn,
    local_nbhds: &[FixedBitSet],
    cands: &[usize], 
    min_k: usize,
    max_k: usize,
    cancel_flag: &AtomicBool,
    ncr_table: &Vec<Vec<BigUint>>
) -> HashMap<(usize, usize), Vec<BigUint>> {

    let mut local_counts = HashMap::new();
    let mut stack = Vec::new();
    stack.push(root_node);

    let mut iteration = 0usize;

    while let Some(SCTnodeChn { label, p, h, pv, hv }) = stack.pop() {
        iteration = iteration.wrapping_add(1);
        if iteration & 1023 == 0 && cancel_flag.load(Ordering::Relaxed) {
            return HashMap::new();
        }

        let size = label.count_ones(..);

        if size == 0 {
            let max_i = std::cmp::min(p, max_k.saturating_sub(h));
            if h + max_i >= min_k {
                for i in 0..=max_i {
                    let k = h + i;
                    if k < min_k || k < 2 || k > max_k { continue; }

                    let ncr_0 = &ncr_table[p][i];
                    let ncr_1 = if p > 0 && i > 0 { &ncr_table[p - 1][i - 1] } else { &ncr_table[0][0] };
                    let ncr_2 = if p > 1 && i > 1 { &ncr_table[p - 2][i - 2] } else { &ncr_table[0][0] };

                    if !ncr_0.is_zero() && hv.len() >= 2 {
                        for x in 0..hv.len() {
                            for y in (x + 1)..hv.len() {
                                let e = normalize_edge(hv[x], hv[y]);
                                let target = local_counts.entry(e).or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
                                target[k] += ncr_0;
                            }
                        }
                    }

                    if !ncr_1.is_zero() && !hv.is_empty() && !pv.is_empty() {
                        for &n1 in &hv {
                            for &n2 in &pv {
                                let e = normalize_edge(n1, n2);
                                let target = local_counts.entry(e).or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
                                target[k] += ncr_1;
                            }
                        }
                    }

                    if !ncr_2.is_zero() && pv.len() >= 2 {
                        for x in 0..pv.len() {
                            for y in (x + 1)..pv.len() {
                                let e = normalize_edge(pv[x], pv[y]);
                                let target = local_counts.entry(e).or_insert_with(|| vec![BigUint::zero(); max_k + 1]);
                                target[k] += ncr_2;
                            }
                        }
                    }
                }
            }
            continue;
        }

        if h + p + size < min_k { continue; }

        let mut pivot = 0;
        let mut max_degree = 0;
        for w in label.ones() {
            let mut isect = label.clone();
            isect.intersect_with(&local_nbhds[w]);
            let deg = isect.count_ones(..);
            if deg >= max_degree {
                max_degree = deg;
                pivot = w;
                if max_degree == size - 1 { break; } 
            }
        }

        let mut p_label = label.clone();
        p_label.intersect_with(&local_nbhds[pivot]);
        let mut new_pv = pv.clone();
        new_pv.push(cands[pivot]); 
        
        stack.push(SCTnodeChn { label: p_label, p: p + 1, h, pv: new_pv, hv: hv.clone() });

        if h + 1 <= max_k {
            let mut h_cands = label.clone();
            h_cands.difference_with(&local_nbhds[pivot]);
            h_cands.set(pivot, false);

            let mut excluded_holds = FixedBitSet::with_capacity(label.len());
            for w in h_cands.ones() {
                let mut h_label = label.clone();
                h_label.intersect_with(&local_nbhds[w]);
                h_label.difference_with(&excluded_holds);
                
                let mut new_hv = hv.clone();
                new_hv.push(cands[w]); 
                
                stack.push(SCTnodeChn { label: h_label, p, h: h + 1, pv: pv.clone(), hv: new_hv });
                excluded_holds.insert(w);
            }
        }
    }
    local_counts
}