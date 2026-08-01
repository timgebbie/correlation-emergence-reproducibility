# Figure and table provenance register

All outputs use `config/config-v1.json`, deterministic NumPy evaluation, and software version `1.0.0`. There is no random seed because no stochastic computation is active.

## F1-F2

- Theory: ordinary clock/coupling envelopes and analytical elasticity.
- Parameters: unit clock rate; response ratios 0.25, 1, 4; 301 log-spaced aggregation points from (10^{-3}) to (10^2).
- Diagnostics: D01-D04, D12; S01-S04.
- Interpretation: component decomposition and local sensitivity, not empirical identification.

## F3

- Theory: fractional clock and response formulas in Apps. A/C.
- Parameters: unit characteristic times; order pairs `(1,1)`, `(0.8,0.8)`, `(0.6,1)`, `(0.6,0.6)`.
- Numerical method: defining series below the declared switch and fixed real-axis quadrature elsewhere.
- Diagnostics: D05-D07; S05-S08.
- Interpretation: fractional curvature and equal-sum confounding, not empirical order estimates.

## F4

- Theory: decaying-Gaussian moment and frozen-front response mapping in App. B.
- Parameters: two symmetric books; unit amplitude/width/slope; coupling strength (2/\sqrt\pi); one-at-a-time factors 0.5, 1, 2.
- Diagnostics: D08, D11-D12; S09-S12.
- Interpretation: conditional propagation, not unique boundary inference.

## F5

- Theory: selector parity and weak first-moment criterion in App. D.
- Numerical choice: four lattice spacings, five selector-resolution ratios, centred/half-cell-shifted selectors, full/truncated domains, directed spread 0.2.
- Diagnostics: D09-D10; S13-S16.
- Interpretation: continuum control versus representation error, not a new continuum mechanism.

## F6

- Theory: ordinary Poisson no-refresh survival and exponential coupling relaxation/covariance memory from Apps. A--C.
- Parameters: illustrative calendar convention only; clock rate `0.1 s^-1`, response rate `0.025 s^-1`, characteristic times 10 s and 40 s, and normalisation `rho_inf=1`.
- Numerical method: direct ordinary build-up and exponential-memory evaluation on deterministic linear grids.
- Presentation: exact square PDF/PNG canvas and square main panel; the grey dotted reference line is the machine-readable constant normalised limit `1`.
- Diagnostics: unit tests verify the exponential memory values and F6 output-panel roles.
- Interpretation: dimensional bridge to conventional calendar-time Epps plots, not a calibration, path autocorrelation, spectrum, or stochastic uncertainty estimate.

## T1-T2

- T1 is generated from the implementation parameter register in `scripts/02_make_tables.py`.
- T2 is generated from the current diagnostic CSV; no status is typed manually into the LaTeX table.
- Regression tests verify the two CSV/LaTeX pairs and the diagnostic IDs/statuses.

No plotted data or generated table values were manually edited.
