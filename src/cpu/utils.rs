use fixedbitset::FixedBitSet;
use num_bigint::BigUint;
use num_traits::{One, Zero};
use std::time::Instant;

/// Represents a node in the Succinct Clique Tree (SCT) for global clique counting.
///
/// Tracks the current set of candidate vertices (`label`), along with the number
/// of pivot (`p`) and hold (`h`) vertices assigned along the path to this node.
pub struct SCTnode {
    pub label: FixedBitSet,
    pub p: usize,
    pub h: usize,
}

/// Represents a node in the Succinct Clique Tree (SCT) for local (vertex/edge) clique counting.
///
/// In addition to the basic candidate `label` and counts (`p`, `h`), this structure
/// tracks the exact history of pivot (`pv`) and hold (`hv`) vertex assignments required
/// to attribute specific clique combinations to precise vertices or edges.
pub struct SCTnodeChn {
    pub label: FixedBitSet,
    pub p: usize,
    pub h: usize,
    pub pv: Vec<usize>,
    pub hv: Vec<usize>,
}

/// Precomputes combinations (n choose r) up to `n` and `max_k` using Pascal's identity.
///
/// Returns a 2D table where `table[i][j]` equals `i` choose `j` as a `BigUint`,
/// preventing overflow during the combinatorial counting at the leaf nodes.
pub fn precompute_ncr(n: usize, max_k: usize) -> Vec<Vec<BigUint>> {
    let mut table = vec![vec![BigUint::zero(); max_k + 1]; n + 1];
    
    for i in 0..=n {
        table[i][0] = BigUint::one();
        for j in 1..=std::cmp::min(i, max_k) {
            if i == j {
                table[i][j] = BigUint::one();
            } else {
                let prev1 = table[i - 1][j - 1].clone();
                let prev2 = table[i - 1][j].clone();
                table[i][j] = prev1 + prev2;
            }
        }
    }
    table
}


// ███████ ███████ ████████ ██    ██ ██████  
// ██      ██         ██    ██    ██ ██   ██ 
// ███████ █████      ██    ██    ██ ██████  
//      ██ ██         ██    ██    ██ ██      
// ███████ ███████    ██     ██████  ██  

/// Prepares the graph for processing by building neighborhoods, computing the degeneracy
/// ordering, and pruning the search space.
///
/// This function implements the Batagelj-Zaversnik algorithm for O(V + E) degeneracy
/// ordering. It prunes vertices that cannot participate in a clique of size `min_k`
/// (i.e., vertices with core number < `min_k - 1`). It then maps the surviving vertices
/// to a new contiguous ID space to reduce memory usage during the SCT exploration.
///
/// # Arguments
/// * `edges` - The edge list of the graph.
/// * `n` - The total number of vertices in the original graph.
/// * `min_k` - The minimum clique size to compute.
/// * `max_k` - The maximum clique size to compute.
///
/// # Returns
/// A tuple containing compressed full neighborhoods, compressed degeneracy (forward)
/// neighborhoods, a mapping from new IDs back to original valid roots, and the effective `max_k`.
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
        let v_deg = degrees[v]; 
        
        degeneracy = std::cmp::max(degeneracy, v_deg);
        core_numbers[v] = degeneracy;
        degen_ranks[v] = i;

        for &u in &nbhds[v] {
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

    let effective_max_k = std::cmp::min(max_k, degeneracy + 1);
    let core_threshold = if min_k > 0 { min_k - 1 } else { 0 };

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

    for list in &mut compressed_nbhds { list.sort_unstable(); }
    for list in &mut compressed_degen_nbhds { list.sort_unstable(); }

    println!("Compression & Sorting: {:.3}s", phase3_start.elapsed().as_secs_f64());
    println!("Total Setup Time: {:.3}s", total_start.elapsed().as_secs_f64());

    (compressed_nbhds, compressed_degen_nbhds, valid_roots, effective_max_k)
}
