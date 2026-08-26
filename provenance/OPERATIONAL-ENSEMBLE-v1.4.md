# Complete operational ensembles and target views — `v1.4.3`

## Scope and layer boundary

This checkpoint executes the complete two-book dynamics accepted through
`v1.4.2`. Every density step lies on one fixed price grid and one common
uniform operational-time grid. The ensemble functions consume caller-supplied
innovations and shock arrays; they own neither a random generator nor an event
clock. There is no nonuniform sampling, previous-tick interpolation,
subordination, timestamp-aware estimator or calendar-time label.

This separation is the principal architectural conformity result needed before
Stage 5. The operational fields and reaction boundaries can now be evolved and
measured independently of the clocks through which they will later be
observed.

## Declared experiment

`config/config-v1.4.json` fixes the complete experiment:

- price grid `[-10,10]` with 201 points and `Delta x=0.1`;
- two ordinary operational kernels, diffusion `D_1=D_2=0.5`, transport
  probability `r=0.5` and `Delta u=0.005`;
- corrected source `-lambda*mu*y*exp(-mu*y^2)` with `lambda=1`, `mu=0.1`;
- appendix thickness parameterisation `epsilon=|z_ref|*w_ref=0.5`;
- symmetric regularised coupling `gamma=10` and an uncoupled matched control;
- eight paths, 2,400 steps and external innovation scales `(0.4,0.4)`;
- lags 1--600, using every overlapping window on the operational grid.

The script owns the declared seed only to construct a reproducible external
array. It centres, normalises and orthogonalises the two flattened input
columns. Their measured sample correlation is
`2.5905203907920324e-18`. The model-facing ensemble function receives this
array and does not regenerate it.

## Effective boundary-price correlation

For lag `h`, the primary estimator forms

```text
R_j^(m)(n,h) = p_j^(m)(n+h) - p_j^(m)(n)
```

for every valid operational start step `n` and path `m`. The reported pooled
coefficient is the uncentred realised correlation

```text
sum(R_1 R_2) / sqrt(sum(R_1^2) sum(R_2^2)).
```

Individual-path coefficients, their mean, sample standard deviation and
normal standard-error band are stored separately. The pooled curve must not be
mistaken for the path mean, and the overlapping windows must not be counted as
independent path replicates.

| Lag | Operational scale | Coupled pooled correlation | Matched control |
|---:|---:|---:|---:|
| 1 | 0.005 | 0.002176 | 0.000000 |
| 100 | 0.5 | 0.119597 | -0.079166 |
| 300 | 1.5 | 0.366039 | -0.048121 |
| 600 | 3.0 | 0.510121 | -0.029704 |

Thus zero microscopic forcing correlation is not identified with zero
effective reaction-boundary correlation. The regularised interaction produces
a finite operational response and a scale-dependent build-up. Figure 10 is
the operational counterpart to the historical Bauer target; it is not a fit,
pointwise recovery or pixel recovery of that target.

## Paired density impulse

A second deterministic experiment applies one Gaussian order-density impulse
to book 1 at operational step 40. Its integrated density quantity is `0.05`
and width is `0.25`; an otherwise identical control receives no impulse.
Figures 11 and 12 show the applied state at step 40 and the relaxed state at
step 300. The applied own boundary response is `0.1019382060`. At step 300 the
signed cross response is `-0.0026883571` while the external impulse is zero.

The sign and asymmetry are retained as measured full-field responses. The gate
requires a nonzero cross response but does not impose the sign of the reduced
linear SDE on this finite density impulse. That reduced sign follows from a
collective-coordinate closure and is not a pointwise identity for a large
finite field perturbation. Later impact work must test directional response
after explicit limit-order, market-order and trade semantics exist.

The present impulse is therefore labelled only as an external order-density
perturbation. It is not an observed trade, market order, limit order,
single-trade impact estimate or meta-order.

## Evidence and outputs

Run:

```bash
python scripts/15_run_operational_ensemble.py
python -m unittest tests.test_operational_ensemble -v
```

The route writes:

- `diagnostics/operational-ensemble-checks-v1.4.csv` — 19 checks;
- `outputs/operational-epps-curves-v1.4.csv` — 1,200 scenario-lag rows;
- `outputs/operational-epps-path-correlations-v1.4.csv` — 9,600 path rows;
- `outputs/operational-ensemble-summary-v1.4.csv` — coupled/control summary;
- `outputs/operational-shock-response-v1.4.csv` — 501 paired response rows;
- `outputs/operational-shock-selected-densities-v1.4.csv` — 804 density rows;
- Figures 10--12 as PDF and PNG.

Nine tests cover ensemble shapes, input copying, invalid arrays, exact
correlation benchmarks, estimator validation, paired response, output schemas,
event semantics, figure structure and the absence of target-layer clocks or
random generation.

Stage: 4 — complete uniform-operational ensembles (`v1.4.3`)

Science status: accepted; Stage 4 closed

Acceptance status: 182-entry manifest, 19 generated checks and complete
190-test route passed from a fresh extraction of the accepted archive.

Next decision: introduce explicit book-specific clocks and subordination at
`v1.5.0` without changing the accepted operational dynamics.
