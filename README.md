# Correlation emergence in coupled limit order books

Reproducibility code and supplementary materials for:

> Chris Angstmann and Tim Gebbie, **“Correlation emergence and the Epps effect
> in two coupled limit order books,”**
> [arXiv:2606.14182](https://arxiv.org/abs/2606.14182).

**Version:** `v2.0.0`

This is the accepted scientific payload promoted to the untagged `v2.0.0`
repository state. It removes the retired Bauer computational implementation,
preserves the corrected science accepted at v1.9.3 and remains deliberately
untagged until its rendered GitHub presentation has been inspected.

## Key result: estimator-aware theory and simulation

![Figure 7: estimator-aware Epps theory and simulation](figures/figure-07-final-estimator-aware-epps-v2.png)

**Figure 7. Final estimator-aware Epps integration.** The first two panels
compare the frozen clock-only and corrected coupling-only simulations with
their theoretical curves. The third panel is a no-refit holdout comparison of
the combined simulation with both the paper's leading-order separable product
and the finite-grid, finite-step conditional moment evaluated on the same
realised clocks as the estimator. All panels share the same linear 0--400
second and 0--1.1 normalized-covariance scales. The estimator-aware reference
reduces combined RMSE from `0.066963` to `0.039719`, with standardized RMSE
`0.455132` and full pointwise 95% normal-band coverage. No clock, coupling,
boundary, normalization or simulation parameter is refitted.

The machine-readable curves and summary are
[`outputs/final-estimator-aware-epps-curves-v1.9.csv`](outputs/final-estimator-aware-epps-curves-v1.9.csv)
and
[`outputs/final-estimator-aware-epps-summary-v1.9.csv`](outputs/final-estimator-aware-epps-summary-v1.9.csv).

## Scientific model and correction boundary

The corrected implementation separates three operations:

1. both order-book densities evolve on one uniform operational-time grid;
2. labelled limit-order, market-order and meta-order events act on that grid;
3. completed paths are observed through separate book-specific calendar clocks
   by explicit previous-refresh subordination.

Calendar waiting intervals never enter the density recurrence. Calendar prices
are previous-completed-state observations; no interpolation, extrapolation or
nonuniform state update is used.

The historical Bauer et al. implementation was used during development as a
numerical antecedent and conversion audit. It mixed a nonuniform update with
the state recurrence and used a different source convention. That executable
surface, its stored simulations and its development-only tests are not part of
this release. The attribution and the scientifically necessary
contrast remain in
[`provenance/BAUER-ANTECEDENT-AND-CORRECTIONS-v2.md`](provenance/BAUER-ANTECEDENT-AND-CORRECTIONS-v2.md).

### Boundary representation

The production coupling acts on the resolved reaction front's translation
mode, `-d(phi)/dx`. This representation moves the zero crossing of the density
field already carried by the numerical state; it does not add a second fixed
selector width or a separate boundary layer. The bounded regularized source
in the Angstmann--Gebbie analysis is retained as an analytical weak/local
moment closure. The claimed correspondence is therefore after projection onto
front displacement, not pointwise equality of the two kernels.

The corrected numerical source uses `exp(-mu*y^2)`. The rejected translated
legacy form `exp(-(mu*y)^2)` remains documented only to make the correction
auditable. The response coefficient and operational/calendar exponents retain
their distinct meanings throughout.

## Retained evidence

The public figure sequence is deliberately compact:

| Figure | Evidence |
|---|---|
| 1--6 | Analytical mechanism, sensitivity, finite-grid and calendar-time results |
| 7 | Final estimator-aware clock/coupling/combined Epps comparison |
| 8 | Corrected translation-mode coupling recovery on uniform operational time |
| 9 | Paired single-trade own- and cross-impact simulation |
| 10 | Scheduled meta-order own- and cross-impact simulation |
| 11 | Log-mid increment and trade-sign autocorrelations across event, operational and calendar layers |

Figure 11 explicitly includes log-mid increment autocorrelation, event-time
trade-sign autocorrelation, subordinated signed-flow autocorrelation and
sign-convention agreement. Price-level autocorrelation is intentionally
excluded.

The release also retains two publication tables, curve-level CSV evidence,
claim summaries, the frozen target-paper source, the corrected computational
supplement and a compact scientific regression suite. Stored simulation-member
archives and development-only figures are regenerated only when scientifically
needed and are not shipped as public evidence.

## Installation

Python 3.12 is the controlled release environment. The complete route was also
verified on Windows with Python 3.13. In both cases the numerical packages are
exactly pinned by `requirements.txt`.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate with:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --no-cache-dir --progress-bar off -r .\requirements.txt
```

## Reproduce and verify

From a newly extracted release archive, run the single active route:

```bash
python scripts/run_all.py
```

The default mode is strict. It verifies the pinned runtime and every archive
manifest entry before executing the retained analytical and simulation route,
the scientific tests and the immutable-source verification.

For a repeat in an already-used tree:

```bash
python scripts/run_all.py --rerun
```

Rerun mode still checks the runtime and immutable inputs. Generated artifacts
are assessed by numerical, schema, figure and scientific tests rather than by
cross-platform byte identity. Use the default mode for a newly downloaded ZIP.

## Repository map

```text
config/                  Accepted scientific and final-release configurations
functions/operational/   Uniform-grid density and corrected coupling dynamics
functions/observation/   Clocks, previous-refresh sampling and subordination
functions/events/        Order-event records, tapes and impact operations
scripts/run_all.py       Single active reproducibility entry point
tests/                   Compact claim-bearing regression suite
outputs/                 Machine-readable curve and summary evidence
figures/                 Eleven selected PDF/PNG figure pairs
diagnostics/             Generated scientific acceptance checks
source/source-v1/        Frozen Angstmann--Gebbie target-paper source
source/source-v2/        Computational correction and conformity inserts
provenance/              Compact theory-to-code and numerical traceability
supplementary-materials/ Compiled computational supplement
```

Names such as `config-v1.7.7.json` and output suffixes such as `-v1.8.csv` are
retained where they identify an accepted scientific object. They do not imply
that the public repository is a collection of active historical releases.
Release-facing figures, README text, supplement and archive naming use the
clean `v2.0.0` publication vocabulary.

## Development lineage and provenance

The public payload is streamlined, but its complete scientific development
line remains explicit:

| Version | Established or changed | Status in v2 |
|---|---|---|
| `v1.0.0` | Analytical supplement, Figures 1--6, tables and numerical diagnostics | Retained |
| `v1.1.x` | Target-paper, source, fixtures and verification boundary frozen | Frozen source retained |
| `v1.2.x` | Bauer Julia-to-Python conversion and declared-input reconstruction | Retired code; sealed gates/history only |
| `v1.3.x` | Statistical legacy recovery and audit; uniform-operational target architecture specified | Audit conclusions retained compactly |
| `v1.4.x` | Uniform-grid operational primitives, solver, paths and robustness | Retained corrected core |
| `v1.5.x` | Explicit clocks, previous-refresh sampling and calendar subordination | Retained corrected core |
| `v1.6.x` | Paired clock/boundary decomposition and robustness experiments | Conclusions folded into final evidence |
| `v1.7.0--v1.7.6` | Theory/simulation conformity design, clock-only recovery and rejected preliminary coupling route | Superseded experiments retired |
| `v1.7.7` | Corrected receiving-front translation-mode coupling and `exp(-mu*y^2)` convention accepted | Retained as Figure 8 and core code |
| `v1.7.11--v1.7.12` | Combined no-refit prediction and Stage 7 closure | Retained in final integration evidence |
| `v1.8.0` | Event taxonomy, tape, sign conventions and impact semantics | Retained |
| `v1.8.1` | Single-trade own/cross impact | Retained as Figure 9 |
| `v1.8.2` | Scheduled meta-order own/cross impact | Retained as Figure 10 |
| `v1.8.3` | Log-mid increment and trade-sign dependence diagnostics | Retained as Figure 11 |
| `v1.9.0` | Estimator-aware final Epps integration with frozen parameters | Retained as key Figure 7 |
| `v1.9.1` | GitHub-facing README, release identity and pre-release inspection sequence fixed | Publication policy retained |
| `v1.9.2` | Physical payload slimming and full/slim claim-equivalence gate | Accepted parent of v1.9.3 |
| `v1.9.3` | Bauer executable retirement, compact provenance, final Figure 1--11 map and v2 supplement | Accepted final local gate |
| `v2.0.0` | Same accepted scientific payload promoted to the untagged repository state | Current public version; tag deferred pending inspection |

The key development link is therefore not erased: Bauer et al. supplied the
computational antecedent; the staged audit exposed the time-update, source and
interface distinctions; the Angstmann--Gebbie route separated uniform
operational dynamics from explicit calendar observation; the corrected
translation-mode representation passed component and combined no-refit gates;
and v1.9.3 removed the superseded implementation only after those conclusions
and final claim-bearing outputs are frozen.

[`CHANGELOG.md`](CHANGELOG.md) records the patch-level decisions. The sealed
pre-v1.9.3 gate archives and Git history preserve the retired files and exact
development tests, while
[`provenance/BAUER-ANTECEDENT-AND-CORRECTIONS-v2.md`](provenance/BAUER-ANTECEDENT-AND-CORRECTIONS-v2.md)
states the compact public scientific boundary.

## Publication sequence

The accepted payload is now the untagged `v2.0.0` repository state. The
remaining publication sequence is fixed:

1. push this repository state without creating a tag or GitHub Release;
2. inspect the rendered README, Figure 7, tree, links and a clean clone;
3. correct and re-inspect if necessary;
4. only after acceptance, create tag `v2.0.0` and one GitHub Release titled
   `v2.0.0 — Correlation emergence and explicit-subordination simulation extension`;
5. attach `correlation-emergence-reproducibility-v2.0.0.zip`.

No fork is required: the repository history preserves the retired development
surface without shipping it in the public release payload.

## Reproducibility interpretation

The estimator-aware curve refines the finite-sample measurement of the accepted
simulation. It does not replace the paper's leading-order mechanism
decomposition with a fit. PDF bytes can differ across platforms because of
renderer metadata and compression; scientific equivalence is judged from
frozen inputs, machine-readable curves, declared tolerances and claim-bearing
tests.

The target-paper source in `source/source-v1/` remains frozen. The boundary
representation clarification and computational corrections are made explicit
in this README, the supplement and `source/source-v2/` before any later paper
revision is considered.

## Citation and license

> Angstmann, Chris; Gebbie, Tim (2026). *Correlation emergence and the Epps
> effect in two coupled limit order books*. arXiv:2606.14182.

Code is released under the MIT License. Supplementary text, captions, generated
figures, tables and documentation are released under CC BY 4.0 unless otherwise
stated. See `LICENSE`, `CONTENT-LICENSE.md` and `CITATION.cff`.
