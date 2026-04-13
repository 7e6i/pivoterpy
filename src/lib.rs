use pyo3::prelude::*;
use rayon::prelude::*;
use fixedbitset::FixedBitSet;
use num_bigint::{BigUint, ToBigUint};
use num_traits::{Zero, One};

#[pyclass]
pub struct RustPivoter {
    n: usize,
    // We replace Python's list[set()] with an array of lightning-fast BitSets
    neighborhoods: Vec<FixedBitSet>, 
    // We will assume you pass the pre-computed degeneracy roots from Python to keep this clean
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

        // 1. Build the fast BitSets
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


    #[pyo3(signature = (procs=1))]
    fn count(&self, procs: usize) -> PyResult<Vec<BigUint>> {

        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(procs)
            .build()
            .expect("Failed to build Rayon thread pool");

        // 2. Execute map-reduce logic
        let global_counts = pool.install(|| {
            self.roots.par_iter()
                .map(|&root| self.count_from_root(root))
                .reduce(
                    || vec![BigUint::zero(); self.n + 1],
                    |mut acc, local_counts| {
                        for i in 0..acc.len() {
                            acc[i] += &local_counts[i];
                        }
                        acc
                    }
                )
        });

        Ok(global_counts)
    }

}

// --- INTERNAL RUST METHODS --- //
impl RustPivoter {
    fn count_from_root(&self, root: usize) -> Vec<BigUint> {
        let mut counts = vec![BigUint::zero(); self.n + 1];
        
        // Start the DFS. We clone the forward neighborhood to act as our initial candidate set
        let initial_label = self.forward_neighborhoods[root].clone();
        
        self.dfs(initial_label, 0, 1, &mut counts);
        
        counts
    }

    /// The highly optimized recursive DFS. 
    /// Because Rust has effectively zero function-call overhead, we don't need a generator stack!
    fn dfs(&self, label: FixedBitSet, p: usize, h: usize, counts: &mut Vec<BigUint>) {
        // Base Case: Leaf Node
        if label.count_ones(..) == 0 {
            // Update counts using math combinations
            for i in 0..=p {
                counts[h + i] += self.comb(p, i);
            }
            return;
        }

        // 3. PIVOT SELECTION: Find node in `label` with max intersection
        // Notice how fast `clone_and_and` (Bitwise AND) is compared to Python set intersections!
        let pivot = label.ones().max_by_key(|&v| {
            let mut temp = label.clone();
            temp.intersect_with(&self.neighborhoods[v]);
            temp.count_ones(..)
        }).unwrap();

        // 4. THE PIVOT BRANCH
        let mut p_label = label.clone();
        p_label.intersect_with(&self.neighborhoods[pivot]);
        self.dfs(p_label, p + 1, h, counts);

        // 5. THE HOLD BRANCHES
        let mut h_nodes = label.clone();
        h_nodes.difference_with(&self.neighborhoods[pivot]);
        h_nodes.set(pivot, false); // Remove the pivot itself

        let mut excluded_holds = FixedBitSet::with_capacity(self.n);

        for h_node in h_nodes.ones() {
            let mut h_label = label.clone();
            h_label.intersect_with(&self.neighborhoods[h_node]);
            h_label.difference_with(&excluded_holds);

            self.dfs(h_label, p, h + 1, counts);
            
            excluded_holds.insert(h_node);
        }
    }

    /// Fast Combinatorics using BigUint
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
fn _rust_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RustPivoter>()?;
    Ok(())
}

