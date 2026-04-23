//! The pure-CPU implementation of the Pivoter algorithm.
//!
//! This module is responsible for graph preprocessing, degeneracy ordering,
//! and the core Search-and-Count Tree (SCT) exploration algorithms for
//! global, vertex, and edge clique counting.

pub mod core;
pub mod utils;

pub use core::{count_edge, count_global, count_vertex};