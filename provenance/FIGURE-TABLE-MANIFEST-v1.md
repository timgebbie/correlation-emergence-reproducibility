# Figure-table manifest

| ID | Output | Generating command | Machine-readable source | Caption |
|---|---|---|---|---|
| F1 | `figures/figure-01-ordinary-epps-components-v1.pdf` | `python scripts/03_generate_figures.py` | `outputs/figure-01-ordinary-epps-components-data-v1.csv` | `captions/caption-register-v1.md` |
| F2 | `figures/figure-02-ordinary-epps-sensitivity-v1.pdf` | same | `outputs/figure-02-ordinary-epps-sensitivity-data-v1.csv` | same |
| F3 | `figures/figure-03-fractional-epps-sensitivity-v1.pdf` | same | `outputs/figure-03-fractional-epps-sensitivity-data-v1.csv` | same |
| F4 | `figures/figure-04-boundary-to-epps-propagation-v1.pdf` | same | `outputs/figure-04-boundary-to-epps-data-v1.csv` | same |
| F5 | `figures/figure-05-finite-grid-epps-distortion-v1.pdf` | same | `outputs/figure-05-finite-grid-epps-data-v1.csv` | same |
| F6 | `figures/figure-06-calendar-time-epps-memory-v1.pdf` | same | `outputs/figure-06-calendar-time-epps-memory-data-v1.csv` | same |
| T1 | `tables/table-01-parameter-timescale-identifiability-v1.tex` | `python scripts/02_make_tables.py` | matching `.csv` | embedded and caption register |
| T2 | `tables/table-02-numerical-benchmarks-v1.tex` | same, after diagnostics | matching `.csv`; `diagnostics/diagnostic-results-v1.csv` | embedded and caption register |
| S1 | `supplementary-materials/SUPPLEMENTARY-MATERIAL-v1.0.0.pdf` | `latexmk ... SUPPLEMENTARY-MATERIAL-v1.0.0.tex` or Overleaf | root TeX plus F1-F6/T1-T2 | embedded |

All active outputs are regenerated or checked by `python scripts/run_all.py`, except compilation of the supplement, which is intentionally left to local LaTeX or Overleaf.
