//! How several random-path realizations share the thread pool.
//!
//! A node batch holds a few hundred kriging systems. On a large pool the
//! threads finish that and spin until the next batch. Once enough
//! realizations are in flight to occupy the machine, each realization
//! walks its path on one thread instead.

use std::cell::Cell;

use rayon::prelude::*;

thread_local! {
    static NODE_BATCHES: Cell<bool> = const { Cell::new(true) };
}

/// Whether the calling realization may krige a batch of nodes in parallel.
pub(crate) fn node_batches() -> bool {
    NODE_BATCHES.with(Cell::get)
}

fn with_node_batches<T>(enabled: bool, f: impl FnOnce() -> T) -> T {
    struct Restore<'a>(&'a Cell<bool>, bool);
    impl Drop for Restore<'_> {
        fn drop(&mut self) {
            // Rayon reuses the worker after a panic, so restore the flag on unwind.
            self.0.set(self.1);
        }
    }
    NODE_BATCHES.with(|flag| {
        let previous = flag.replace(enabled);
        let _restore = Restore(flag, previous);
        f()
    })
}

/// `f(0)` .. `f(n - 1)`, in that order.
///
/// One realization, or fewer than about a third of the pool, keeps the
/// node batches on their own: the pool scales the batches. More
/// realizations than that share the pool (`threads / n <= 3`). A light
/// realization then walks its path on one thread. Local anisotropy keeps
/// its node batches, because that search still fills the threads. On the
/// scenario grids the light batches stop scaling well before the whole
/// pool, so the idle time between them costs more than those extra threads
/// return.
#[doc(hidden)]
pub fn realizations<T: Send>(n: usize, f: impl Fn(usize) -> T + Sync + Send) -> Vec<T> {
    let threads = rayon::current_num_threads().max(1);
    if n >= 2 && threads / n <= 3 {
        (0..n)
            .into_par_iter()
            .map(|k| with_node_batches(false, || f(k)))
            .collect()
    } else {
        (0..n).map(f).collect()
    }
}

/// Map `f` over `0..len`.
///
/// Parallel when this realization owns the pool. A light batch on a shared
/// pool walks the path on the calling thread: the nested join is the idle
/// spin. `heavy` keeps the join anyway (local anisotropy), because that
/// search still fills the threads.
pub(crate) fn map_nodes<T: Send>(
    len: usize,
    heavy: bool,
    f: impl Fn(usize) -> T + Sync + Send,
) -> Vec<T> {
    if len > 1 && (heavy || node_batches()) {
        (0..len).into_par_iter().map(f).collect()
    } else {
        (0..len).map(f).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::realizations;
    use crate::dss::Dss;
    use crate::sgs::{SgsParams, sgs};
    use crate::sis::{SisParams, sis};
    use estimation::Search;
    use rayon::ThreadPoolBuilder;
    use variogram::{Model, Variogram};

    fn grid(n: usize) -> Vec<(f64, f64, f64)> {
        (0..n * n)
            .map(|i| ((i % n) as f64, (i / n) as f64, 0.0))
            .collect()
    }

    fn check<T: PartialEq + std::fmt::Debug + Send>(
        n: usize,
        threads: usize,
        run: &(impl Fn(usize) -> T + Sync),
    ) {
        let reference: Vec<T> = ThreadPoolBuilder::new()
            .num_threads(1)
            .build()
            .unwrap()
            .install(|| (0..n).map(run).collect());
        let got = ThreadPoolBuilder::new()
            .num_threads(threads)
            .build()
            .unwrap()
            .install(|| realizations(n, run));
        assert_eq!(reference, got, "n={n} threads={threads}");
    }

    #[test]
    fn realizations_follow_the_seed_not_the_scheduler() {
        let g = grid(12);
        let locs: Vec<_> = (0..8)
            .map(|i| ((i % 4) as f64 * 3.0, (i / 4) as f64 * 6.0, 0.0))
            .collect();
        let values: Vec<f64> = (0..8).map(|i| 0.4 + 0.35 * i as f64).collect();
        let cats: Vec<usize> = (0..8).map(|i| i % 3).collect();
        let vg = Variogram::single(Model::Spherical, 1.0, 8.0);
        let search = Search {
            min_samples: 1,
            max_samples: 8,
            radius: 20.0,
            ..Default::default()
        };
        let sgs_one = |k: usize| {
            sgs(
                &locs,
                &values,
                None,
                None,
                &g,
                &vg,
                &SgsParams {
                    search: vec![search.clone()],
                    seed: 7 + k as u64,
                },
                None,
            )
            .unwrap()
            .values
        };
        let fitted = Dss::new(&locs, &values, None, None, None, &vg).unwrap();
        let dss_one = |k: usize| {
            fitted
                .simulate(
                    None,
                    &g,
                    &SgsParams {
                        search: vec![search.clone()],
                        seed: 7 + k as u64,
                    },
                    None,
                )
                .unwrap()
                .values
        };
        let local = estimation::lva::LocalAnisotropy::new(
            g.clone(),
            vec![[30.0, 0.0, 0.0]; g.len()],
            vec![[0.5, 1.0]; g.len()],
        )
        .unwrap();
        let lva_one = |k: usize| {
            sgs(
                &locs,
                &values,
                None,
                None,
                &g,
                &vg,
                &SgsParams {
                    search: vec![search.clone()],
                    seed: 7 + k as u64,
                },
                Some(&local),
            )
            .unwrap()
            .values
        };
        let indicators = vec![Variogram::single(Model::Spherical, 0.2, 8.0); 3];
        let sis_one = |k: usize| {
            sis(
                &locs,
                &cats,
                None,
                &g,
                3,
                &indicators,
                &SisParams {
                    search: search.clone(),
                    seed: 7 + k as u64,
                },
                None,
            )
            .unwrap()
            .categories
        };
        // n=4 on 8 threads is one realization per thread (node batches off).
        // n=2 on 8 threads stays on node batches. Both match the 1-thread path.
        for (n, threads) in [(4, 1), (4, 8), (2, 8)] {
            check(n, threads, &sgs_one);
            check(n, threads, &lva_one);
            check(n, threads, &dss_one);
            check(n, threads, &sis_one);
        }
    }
}
