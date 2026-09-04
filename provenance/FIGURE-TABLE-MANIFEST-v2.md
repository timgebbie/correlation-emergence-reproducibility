# Figure and table manifest - v2.1.0

All captions are in `captions/caption-register-v2.md`.

| ID | Public output | Generating command | Machine-readable evidence |
|---|---|---|---|
| F1 | `figures/figure-01-ordinary-epps-components-v1.pdf` | `python scripts/03_generate_figures.py` | `outputs/figure-01-ordinary-epps-components-data-v1.csv` |
| F2 | `figures/figure-02-ordinary-epps-sensitivity-v1.pdf` | same | `outputs/figure-02-ordinary-epps-sensitivity-data-v1.csv` |
| F3 | `figures/figure-03-fractional-epps-sensitivity-v1.pdf` | same | `outputs/figure-03-fractional-epps-sensitivity-data-v1.csv` |
| F4 | `figures/figure-04-boundary-to-epps-propagation-v1.pdf` | same | `outputs/figure-04-boundary-to-epps-data-v1.csv` |
| F5 | `figures/figure-05-finite-grid-epps-distortion-v1.pdf` | same | `outputs/figure-05-finite-grid-epps-data-v1.csv` |
| F6 | `figures/figure-06-calendar-time-epps-memory-v1.pdf` | same | `outputs/figure-06-calendar-time-epps-memory-data-v1.csv` |
| F7 | `figures/figure-07-final-estimator-aware-epps-v2.pdf` | `python scripts/36_generate_final_epps_integration.py` | `outputs/final-estimator-aware-epps-curves-v1.9.csv`; summary CSV |
| F8 | `figures/figure-08-corrected-translation-mode-coupling-v2.pdf` | `python scripts/29_run_corrected_coupling_recovery.py` | corrected-coupling curves, response and summary CSVs |
| F9 | `figures/figure-09-single-trade-impact-v2.pdf` | `python scripts/33_run_single_trade_impact.py` | single-trade curves, events and summary CSVs |
| F10 | `figures/figure-10-meta-order-impact-v2.pdf` | `python scripts/34_run_meta_order_impact.py` | meta-order trajectory, relaxation, schedules, events and summary CSVs |
| F11 | `figures/figure-11-mid-price-trade-sign-autocorrelations-v2.pdf` | `python scripts/35_run_dependence_diagnostics.py` | mid-price, event-sign, signed-flow, agreement and summary CSVs |
| F12 | `figures/figure-12-order-book-shock-recovery-v2.pdf` | `python scripts/40_run_order_book_shock_recovery.py` | shock summary, density ledger and accepted NPZ archive |
| F13 | `figures/figure-13-stylised-facts-recovery-v2.pdf` | `python scripts/43_run_r13_long_memory_clock_impact.py` | twelve panel pairs, R13 panel manifest, clock summary and long-memory clock NPZ archive |
| F14 | `figures/figure-14-clock-subordinated-impact-v2.pdf` | same | paired impact curve CSV, response NPZ archive and R13 science/mathematics checks |
| T1 | `tables/table-01-parameter-timescale-identifiability-v1.tex` | `python scripts/02_make_tables.py` | matching CSV |
| T2 | `tables/table-02-numerical-benchmarks-v1.tex` | same | matching CSV and `diagnostics/diagnostic-results-v1.csv` |
| S1 | `supplementary-materials/SUPPLEMENTARY-MATERIAL-v2.1.0.pdf` | local LaTeX compilation | root TeX, F1--F14 and T1--T2 |

The active route regenerates or scientifically verifies every claim-bearing
computational result. Accepted version suffixes on curve CSVs are retained as
object provenance. Retired development figures, stored member/path archives
and the Bauer executable reproduction surface are not public release outputs.
