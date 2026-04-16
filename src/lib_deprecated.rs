use pyo3::prelude::*;
use rayon::prelude::*;
use fixedbitset::FixedBitSet;
use num_bigint::{BigUint, ToBigUint};
use num_traits::{Zero, One};
use std::collections::HashMap;

// 1. A struct to hold the merged results from the worker threads
struct WorkerResult {
    global_counts: Vec<BigUint>,
    vertex_counts: Option<HashMap<usize, Vec<BigUint>>>,
}


#[pyclass]
pub struct RustPivoter {
    n: usize,
    neighborhoods: Vec<FixedBitSet>, 
    roots: Vec<usize>,
    forward_neighborhoods: Vec<FixedBitSet>,
}


#[pymethods]
impl RustPivoter {
    #[new]
    fn new(
        n: usize, 
        edges: Vec<(usize, usize)>, 
        roots: Vec<usize>, 
        degen_forward_edges: Vec<Vec<usize>>
    ) -> Self {

        let mut neighborhoods = vec![FixedBitSet::with_capacity(n); n];
        let mut forward_neighborhoods = vec![FixedBitSet::with_capacity(n); n];

        for &(u, v) in &edges {
            neighborhoods[u].insert(v);
            neighborhoods[v].insert(u);
        }

        for (v, forward_nodes) in degen_forward_edges.into_iter().enumerate() {
            for u in forward_nodes {
                forward_neighborhoods[v].insert(u);
            }
        }

        RustPivoter { n, neighborhoods, roots, forward_neighborhoods }
    }

    // 2. Updated signature to accept the boolean flag and return a Tuple
    #[pyo3(signature = (procs=1, get_vertex=false))]
    fn count(&self, procs: usize, get_vertex: bool) -> PyResult<(Vec<BigUint>, Option<Vec<Vec<BigUint>>>)> {

        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(procs)
            .build()
            .expect("Failed to build Rayon thread pool");

        let mut final_results = pool.install(|| {
            self.roots.par_iter()
                .map(|&root| self.count_from_root(root, get_vertex))
                .reduce(
                    || WorkerResult {
                        global_counts: vec![BigUint::zero(); self.n + 1],
                        vertex_counts: if get_vertex { Some(HashMap::new()) } else { None },
                    },
                    |mut acc, local| {
                        // Merge Globals
                        for i in 0..acc.global_counts.len() {
                            acc.global_counts[i] += &local.global_counts[i];
                        }

                        // Merge Vertices
                        if let (Some(acc_v), Some(local_v)) = (acc.vertex_counts.as_mut(), local.vertex_counts) {
                            for (v, counts) in local_v {
                                let target = acc_v.entry(v).or_insert_with(Vec::new);
                                // Pad with zeros if necessary
                                if counts.len() > target.len() {
                                    target.resize(counts.len(), BigUint::zero());
                                }
                                for i in 0..counts.len() {
                                    target[i] += &counts[i];
                                }
                            }
                        }
                        acc
                    }
                )
        });

        // Trim trailing zeros from the global list
        while let Some(count) = final_results.global_counts.last() {
            if count.is_zero() {
                final_results.global_counts.pop();
            } else {
                break;
            }
        }

        // Convert the sparse HashMap into a perfectly dense Vec<Vec> for Python
        let dense_vertex_counts = final_results.vertex_counts.map(|mut v_map| {
            // Iterate from 0 to N-1
            (0..self.n).map(|v| {
                // Remove the node from the map. 
                // If it doesn't exist, return [0, 1] (which is redundant because it will always be visted)
                v_map.remove(&v).unwrap_or_else(|| vec![BigUint::zero(), BigUint::one()])
            }).collect()
        });

        // Return the tuple! Python receives a perfect List[List[int]]
        Ok((final_results.global_counts, dense_vertex_counts))
    }
}

// --- INTERNAL RUST METHODS --- //
impl RustPivoter {
    fn count_from_root(&self, root: usize, get_vertex: bool) -> WorkerResult {
        
        let mut global_counts = vec![BigUint::zero(); self.n + 1];
        let mut vertex_counts = if get_vertex { Some(HashMap::new()) } else { None };
        
        let initial_label = self.forward_neighborhoods[root].clone();
        
        // 3. Initialize our high-speed backtracking arrays
        let mut pv = Vec::with_capacity(self.n / 2); // An educated guess
        let mut hv = Vec::with_capacity(self.n / 2); 
        hv.push(root);
        
        self.dfs(
            initial_label, 0, 1, 
            &mut global_counts, 
            get_vertex, 
            &mut pv, &mut hv, 
            &mut vertex_counts
        );
        
        WorkerResult { global_counts, vertex_counts }
    }

    fn dfs(
        &self, 
        label: FixedBitSet, 
        p: usize, 
        h: usize, 
        global_counts: &mut Vec<BigUint>,
        get_vertex: bool,
        pv: &mut Vec<usize>,
        hv: &mut Vec<usize>,
        vertex_counts: &mut Option<HashMap<usize, Vec<BigUint>>>
    ) {
        // Base Case: Leaf Node
        if label.count_ones(..) == 0 {
            for i in 0..=p {
                let k = h + i;
                let ncr = self.comb(p, i);
                global_counts[k] += &ncr;

                // 4. VERTEX COMBINATORICS
                if get_vertex {
                    if let Some(vc) = vertex_counts.as_mut() {
                        
                        // Add counts to Holds
                        for &node in hv.iter() {
                            let target = vc.entry(node).or_insert_with(Vec::new);
                            if target.len() <= k { target.resize(k + 1, BigUint::zero()); }
                            target[k] += &ncr;
                        }

                        // Add counts to Pivots
                        if i > 0 && p > 0 {
                            let ncr_p = (&ncr * i.to_biguint().unwrap()) / p.to_biguint().unwrap();
                            for &node in pv.iter() {
                                let target = vc.entry(node).or_insert_with(Vec::new);
                                if target.len() <= k { target.resize(k + 1, BigUint::zero()); }
                                target[k] += &ncr_p;
                            }
                        }
                    }
                }
            }
            return;
        }

        let pivot = label.ones().max_by_key(|&v| {
            let mut temp = label.clone();
            temp.intersect_with(&self.neighborhoods[v]);
            temp.count_ones(..)
        }).unwrap();

        // THE PIVOT BRANCH
        let mut p_label = label.clone();
        p_label.intersect_with(&self.neighborhoods[pivot]);
        
        if get_vertex { pv.push(pivot); } // Push before recursion
        self.dfs(p_label, p + 1, h, global_counts, get_vertex, pv, hv, vertex_counts);
        if get_vertex { pv.pop(); } // Pop after recursion

        // THE HOLD BRANCHES
        let mut h_nodes = label.clone();
        h_nodes.difference_with(&self.neighborhoods[pivot]);
        h_nodes.set(pivot, false);

        let mut excluded_holds = FixedBitSet::with_capacity(self.n);

        for h_node in h_nodes.ones() {
            let mut h_label = label.clone();
            h_label.intersect_with(&self.neighborhoods[h_node]);
            h_label.difference_with(&excluded_holds);

            if get_vertex { hv.push(h_node); } // Push before recursion
            self.dfs(h_label, p, h + 1, global_counts, get_vertex, pv, hv, vertex_counts);
            if get_vertex { hv.pop(); } // Pop after recursion
            
            excluded_holds.insert(h_node);
        }
    }

    fn comb(&self, n: usize, k: usize) -> BigUint {
        if k > n { return BigUint::zero(); }
        if k == 0 || k == n { return BigUint::one(); }
        let k = if k > n / 2 { n - k } else { k };
        let mut res = BigUint::one();
        for i in 1..=k {
            res = (res * (n - i + 1).to_biguint().unwrap()) / i.to_biguint().unwrap();
        }
        res
    }
}


#[pymodule]
#[pyo3(name = "_rust_engine")] // <-- THIS IS THE MAGIC FIX
fn _rust_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RustPivoter>()?;
    Ok(())
}