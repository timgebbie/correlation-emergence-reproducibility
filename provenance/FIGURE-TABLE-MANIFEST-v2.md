# Figure and table manifest - v2.2.0

All captions are in `captions/caption-register-v2.md`.

| ID | Public output | Generating command | Machine-readable evidence |
|---|---|---|---|
| F1 | `figures/figure-01-ordinary-epps-components-v1.pdf` | `python scripts/03_generate_figures.py` | `outputs/figure-01-ordinary-epps-components-data-v1.csv` |
| F2 | `figures/figure-02-ordinary-epps-sensitivity-v1.pdf` | same | `outputs/figure-02-ordinary-epps-sensitivity-data-v1.csv` |
| F3 | `figures/figure-03-fractional-epps-sensitivity-v1.pdf` | same | `outputs/figure-03-fractional-epps-sensitivity-data-v1.csv` |
| F4 | `figures/figure-04-boundary-to-epps-propagation-v1.pdf` | same | `outputs/figure-04-boundary-to-epps-data-v1.csv` |
| F5 | `figures/figure-05-finite-grid-epps-distortion-v1.pdf` | same | `outputs/figure-05-finite-grid-epps-data-v1.csv` |
| F6 | `figures/figure-06-calendar-time-epps-memory-v1.pdf` | same | `outputs/figure-06-calendar-time-epps-memory-data-v1.csv` |
| F7 | `figures/figure-07a-clock-only-epps-v2.pdf`; `figures/figure-07b-coupling-only-epps-v2.pdf`; `figures/figure-07c-combined-epps-v2.pdf` | `python scripts/36_generate_final_epps_integration.py` | `outputs/figure-07-curves-v2.2.0.csv`; `outputs/figure-07-ensemble-v2.2.0.npz` |
| F7 overview | `figures/figure-07-final-estimator-aware-epps-v2.pdf` | same; used in the README and supplement | same Figure 7 evidence |
| F8 | `figures/figure-08-corrected-translation-mode-coupling-v2.pdf` | `python scripts/29_run_corrected_coupling_recovery.py` | corrected-coupling curves, response and summary CSVs |
| F9 | `figures/figure-09-single-trade-impact-v2.pdf` | `python scripts/33_run_single_trade_impact.py` | `outputs/impact-ensemble-v2.2.0.npz`; retained single-trade events and summary CSVs |
| F10 | `figures/figure-10-meta-order-impact-v2.pdf` | `python scripts/34_run_meta_order_impact.py` | `outputs/impact-ensemble-v2.2.0.npz`; retained schedule, event and summary CSVs |
| F10 companion | `figures/meta-order-individual-envelopes-v2.2.0.pdf` | `python scripts/34_run_meta_order_impact.py` | `outputs/impact-ensemble-v2.2.0.npz`; individual 10th–90th percentile envelopes |
| F11 | `figures/figure-11-mid-price-trade-sign-autocorrelations-v2.pdf` | `python scripts/35_run_dependence_diagnostics.py` | `outputs/finite-dependence-ensemble-v2.2.0.npz`; retained diagnostic CSVs |
| F12 | `figures/figure-12-order-book-shock-recovery-v2.pdf` | `python scripts/40_run_order_book_shock_recovery.py` | shock summary, density ledger and accepted NPZ archive |
| F13 | `figures/figure-13-stylised-facts-recovery-v2.pdf` | `python scripts/43_run_long_memory_clock_impact.py` | twelve panel pairs and observation-clock panel manifest; `outputs/persistent-dependence-ensemble-v2.2.0.npz` |
| F14 | `figures/figure-14-clock-subordinated-impact-v2.pdf` | same | `outputs/impact-ensemble-v2.2.0.npz`; clock-impact science/mathematics checks |
| T1 | `tables/table-01-parameter-timescale-identifiability-v1.tex` | retained table and typesetting | matching v1 CSV |
| T2 | `tables/table-02-numerical-benchmarks-v2.2.0.tex` | retained table and typesetting | matching v1 CSV and `diagnostics/diagnostic-results-v1.csv` |
| S1 | `supplementary-materials/SUPPLEMENTARY-MATERIAL-v2.2.0.pdf` | local LaTeX compilation | root TeX, F1--F14 and T1--T2 |

The active route regenerates or scientifically verifies every claim-bearing
computational result. Accepted version suffixes on curve CSVs are retained as
object provenance. The v2.2.0 ensemble archives above support the updated figures. Retired
development figures, unrelated member/path archives and the Bauer executable
reproduction surface are not public release outputs.
