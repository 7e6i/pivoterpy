use fixedbitset::FixedBitSet;
use num_bigint::BigUint;
use num_traits::{One, Zero};
use pyo3::exceptions::PyValueError;
use pyo3::PyResult;
//use std::time::Instant;

const INVALID: u32 = u32::MAX;

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
/// In addition to the current candidate `label` and counts (`p`, `h`), this structure
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

#[inline]
fn read_edge(raw: &[u8], i: usize) -> (u32, u32) {
    let pos = i * 8;
    let u = u32::from_ne_bytes(raw[pos..pos + 4].try_into().unwrap());
    let v = u32::from_ne_bytes(raw[pos + 4..pos + 8].try_into().unwrap());
    (u, v)
}

/// A flat compressed-sparse-row adjacency structure.
///
/// `offsets` has `n + 1` entries and `nbrs` holds every neighbor exactly once,
/// so there is no per-vertex allocation and no capacity slack.
pub struct Csr {
    pub offsets: Vec<usize>,
    pub nbrs: Vec<u32>,
}

impl Csr {
    #[inline]
    pub fn neighbors(&self, v: usize) -> &[u32] {
        &self.nbrs[self.offsets[v]..self.offsets[v + 1]]
    }

    #[inline]
    pub fn len(&self) -> usize {
        self.offsets.len() - 1
    }
}

/// Prepares the graph for processing from a flat native-endian `u32` edge buffer.
///
/// The buffer contains interleaved ``(u, v)`` pairs. This function builds a CSR
/// adjacency structure, computes the Batagelj-Zaversnik degeneracy ordering,
/// prunes vertices that cannot participate in a clique of size `min_k`, and
/// maps the survivors to a contiguous ID space containing only forward
/// (degeneracy) neighborhoods.
///
/// # Arguments
/// * `raw` - Flat native-endian `u32` pairs, ``[u0, v0, u1, v1, ...]``.
/// * `n` - The total number of vertices in the original graph.
/// * `min_k` - The minimum clique size to compute.
/// * `max_k` - The maximum clique size to compute.
///
/// # Returns
/// A tuple containing compressed full neighborhoods, compressed degeneracy
/// (forward) neighborhoods, a mapping from new IDs back to original valid
/// roots, and the effective `max_k`.
pub fn setup_graph(
    raw: &[u8],
    n: usize,
    min_k: usize,
    max_k: usize,
) -> PyResult<(Csr, Csr, Vec<usize>, usize)> {
    if n > u32::MAX as usize {
        return Err(PyValueError::new_err(
            "graph has too many vertices for the uint32 backend",
        ));
    }
    if raw.len() % 8 != 0 {
        return Err(PyValueError::new_err(
            "edge buffer length is not a multiple of 8 bytes",
        ));
    }

    let m = raw.len() / 8;

    // ---------------------------------------------------------
    // 1. Build a flat CSR adjacency structure
    // ---------------------------------------------------------
    let mut degrees = vec![0u32; n];
    for i in 0..m {
        let (u, v) = read_edge(raw, i);
        let (u, v) = (u as usize, v as usize);
        if u >= n || v >= n {
            return Err(PyValueError::new_err(
                "edge endpoint is outside the node range",
            ));
        }
        if u == v {
            continue;
        }
        degrees[u] += 1;
        degrees[v] += 1;
    }

    let mut offsets = vec![0usize; n + 1];
    for v in 0..n {
        offsets[v + 1] = offsets[v] + degrees[v] as usize;
    }

    let mut nbrs = vec![0u32; offsets[n]];
    let mut cursor = offsets.clone();
    for i in 0..m {
        let (u, v) = read_edge(raw, i);
        let (u, v) = (u as usize, v as usize);
        if u == v {
            continue;
        }
        nbrs[cursor[u]] = v as u32;
        cursor[u] += 1;
        nbrs[cursor[v]] = u as u32;
        cursor[v] += 1;
    }

    for v in 0..n {
        nbrs[offsets[v]..offsets[v + 1]].sort_unstable();
    }

    // ---------------------------------------------------------
    // 2. Batagelj-Zaversnik Degeneracy Ordering O(V + E)
    // ---------------------------------------------------------
    let mut max_deg = 0;
    for &d in &degrees {
        if d as usize > max_deg { max_deg = d as usize; }
    }

    let mut bin = vec![0; max_deg + 1];
    for &d in &degrees {
        bin[d as usize] += 1;
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
        let d = degrees[v] as usize;
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
        
        degeneracy = std::cmp::max(degeneracy, v_deg as usize);
        core_numbers[v] = degeneracy;
        degen_ranks[v] = i;

        for idx in offsets[v]..offsets[v + 1] {
            let u = nbrs[idx] as usize;
            if degrees[u] > degrees[v] {
                let u_deg = degrees[u] as usize;
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

    let effective_max_k = std::cmp::min(max_k, degeneracy + 1);
    let core_threshold = if min_k > 0 { min_k - 1 } else { 0 };

    let mut valid_roots = Vec::new();           
    let mut old_to_new = vec![INVALID; n];   

    for v in 0..n {
        if core_numbers[v] >= core_threshold {
            let new_id = valid_roots.len();
            old_to_new[v] = new_id as u32;
            valid_roots.push(v); 
        }
    }

    let v_prime = valid_roots.len();

    // Two passes over the valid vertices build both compressed adjacencies
    // directly into flat CSR buffers: first count, then fill. This avoids
    // `Vec<Vec<u32>>` (one allocation per vertex plus up to 2x slack).

    let mut full_offsets = vec![0usize; v_prime + 1];
    let mut degen_offsets = vec![0usize; v_prime + 1];
    for new_v in 0..v_prime {
        let old_v = valid_roots[new_v];
        let v_rank = degen_ranks[old_v];
        let (mut full_cnt, mut degen_cnt) = (0usize, 0usize);
        for idx in offsets[old_v]..offsets[old_v + 1] {
            let old_u = nbrs[idx] as usize;
            if old_to_new[old_u] != INVALID {
                full_cnt += 1;
                if degen_ranks[old_u] > v_rank {
                    degen_cnt += 1;
                }
            }
        }
        full_offsets[new_v + 1] = full_offsets[new_v] + full_cnt;
        degen_offsets[new_v + 1] = degen_offsets[new_v] + degen_cnt;
    }

    let mut degen_nbrs = vec![0u32; degen_offsets[v_prime]];
    let mut degen_cursor = degen_offsets.clone();

    for new_v in 0..v_prime {
        let old_v = valid_roots[new_v];
        let v_rank = degen_ranks[old_v];
        for idx in offsets[old_v]..offsets[old_v + 1] {
            let old_u = nbrs[idx] as usize;
            let new_u = old_to_new[old_u];
            if new_u != INVALID && degen_ranks[old_u] > v_rank {
                degen_nbrs[degen_cursor[new_v]] = new_u;
                degen_cursor[new_v] += 1;
            }
        }
    }
    for new_v in 0..v_prime {
        degen_nbrs[degen_offsets[new_v]..degen_offsets[new_v + 1]].sort_unstable();
    }

    // Compact the full neighborhoods in place inside `nbrs`. Writing position
    // `w` never overtakes the read position, so this needs no second buffer.
    let mut w = 0usize;
    for new_v in 0..v_prime {
        let old_v = valid_roots[new_v];
        let (start, end) = (offsets[old_v], offsets[old_v + 1]);
        let row_start = w;
        for idx in start..end {
            let new_u = old_to_new[nbrs[idx] as usize];
            if new_u != INVALID {
                nbrs[w] = new_u;
                w += 1;
            }
        }
        nbrs[row_start..w].sort_unstable();
        full_offsets[new_v] = row_start;
    }
    full_offsets[v_prime] = w;
    nbrs.truncate(w);

    // `offsets` and `degrees` are dropped here, before the search.
    Ok((
        Csr { offsets: full_offsets, nbrs },
        Csr { offsets: degen_offsets, nbrs: degen_nbrs },
        valid_roots,
        effective_max_k,
    ))
}
