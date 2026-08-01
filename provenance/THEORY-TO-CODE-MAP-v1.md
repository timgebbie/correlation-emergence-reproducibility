# Theory-to-code map - v1.0.0

| Theory object | Frozen source | Computational representation | Active function/script | Dependent outputs | Diagnostic boundary |
|---|---|---|---|---|---|
| Ordinary attenuation (F(x)=1-(1-e^{-x})/x) | Main Eqs. (8)-(11); Apps. A-C | `expm1` plus origin series | `functions/correlation_build_up.py` | F1, F2, F4, F5, T2 | zero/small/large limits, monotonicity, bounds |
| Ordinary derivative and elasticity | Analytic derivative of the ordinary kernel | closed derivative plus origin series; (xF'/F) | `ordinary_derivative`, `rate_elasticity` | F2, T2 | finite difference and limit checks |
| Fractional attenuation (1-E_{\alpha,2}[-(\Delta/\tau)^\alpha]) | Apps. A and C | small-(x) series; real-axis composite quadrature; exact alpha-one endpoint | `fractional_build_up` | F3, T2 | alpha-one recovery, six independent references, bounds |
| Combined Epps factor | Main Eq. (11); App. C | leading-order product of diagnosed components | `combined_build_up` | F1-F6 where used | exact array product and bounds; separability remains an approximation |
| Ordinary response/memory diagnostic | Apps. A--C | `exp(-rate * lag)` no-refresh or relaxation survival | `exponential_memory` | F6 inset | exact reference values, monotonicity inherited analytically, positive-rate validation |
| Decaying Gaussian (q_j(y)) | Main Eq. (5); App. B | active source kernel only | `source_kernel` | F4, F5, T1-T2 | invalid parameters and moment recovery |
| Half-line first moment (M_j^+) | App. B Eq. (B.12) | analytic formula plus continuum quadrature check | `analytic_half_line_moment` | F4, F5, T2 | analytic/numerical relative error |
| Response rate (kappa_j=\gamma_{jk}|M_j|/|\mathcal L_j|) | App. B Eq. (B.13) | single-book rate and symmetric book sum | `response_rate_single`, `response_rate_total` | F4, F5, T1 | unit baseline and conditional elasticities |
| Smooth selector (W(y,z;\varepsilon)) | Main Eq. (6); App. D | stable hyperbolic tangent | `smooth_selector` | F5, T1 | centred continuum parity invariance |
| Lattice first-moment representation | App. D weak-equivalence criterion; finite-grid sensitivity question | symmetric rectangle-rule lattice with alignment and domain controls | `discrete_selected_moment` | F5, T2 | coarse-to-fine convergence; centred/shifted/truncated cases |
| Analytic/simulation overlay | v1-v2 interface | long-form CSV roles with empty deterministic uncertainty | `scripts/03_generate_figures.py` | `outputs/epps-overlay-v1.csv` | schema and output tests |

The discrete alignment experiment is a labelled numerical modelling choice. It is not presented as the legacy simulator or as an additional continuum equation.
