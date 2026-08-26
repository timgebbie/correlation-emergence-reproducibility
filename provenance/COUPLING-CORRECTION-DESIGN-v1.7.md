# Coupling-correction design — `v1.7.6`

Status: accepted design gate

## Decision

The claim-bearing corrected coupling is the current-front translation-mode
source

\[
v_j(x,u)=-\partial_x\varphi^{(j)}(x,u),
\qquad
\ell_{T}^{(j,k)}(x,u)
=-\kappa_{jk}z_{jk}(u)v_j(x,u),
\]

where (z_{jk}=p^{(j)}-p^{(k)}) and the density is taken from the immutable
pre-step state of the receiving book. Equivalently,

\[
\ell_{T}^{(j,k)}
=\kappa_{jk}z_{jk}\partial_x\varphi^{(j)}.
\]

This is the minimal numerical source that realizes the normalized
reaction-front projection in the accepted Angstmann--Gebbie appendix. It is a
new coupling contract, not a reinterpretation of the accepted
`RegularizedCoupling.gamma` parameter.

No production coupling, solver or path implementation changes at this design
gate. The accepted v1.7.5 coupling and its `invalid_experiment` evidence remain
unchanged.

## Why this is the selected correction

The appendix defines the frozen translation mode by

\[
v_j=-\partial_x\varphi_j^\star,
\qquad
N_j=\langle\psi_j,v_j\rangle,
\]

and the projected boundary velocity by

\[
\dot p_j=\frac{\langle\psi_j,\ell^{(j,k)}\rangle}{N_j}.
\]

Substitution of

\[
\ell_T^{(j,k)}=-\kappa_{jk}z_{jk}v_j
\]

gives directly

\[
\dot p_j=-\kappa_{jk}z_{jk}.
\]

The unknown adjoint normalization cancels. The coupling thickness is inherited
from the complete current reaction front through its spatial derivative; it is
not supplied by a separate selector width. For (z_{jk}>0), book (j) lies
above book (k) and receives a negative drift. The reciprocal ordered pair has
(z_{kj}<0) and receives a positive drift. Hence

\[
\dot z=-(\kappa_{12}+\kappa_{21})z.
\]

This settles the receiving-book sign without an additional convention.

## Candidate assessment

| Candidate | Decision | Reason |
|---|---|---|
| Fixed-(\varepsilon) regularised source | Rejected for primary recovery | Its small-spread leading term is proportional to the base source and v1.7.5 measured a non-positive boundary-response rate. |
| Hard-side or fixed-spatial-width source | Deferred robustness case | It retains the side-order interpretation, but is not differentiable or independently rate-normalized at zero spread. |
| Shifted source centre | Rejected for primary recovery | Its observed rate depends on the density generator and conflates the one-book source location with coupling. |
| Current-front translation mode | Selected | It excites the appendix displacement mode directly and makes each ordered rate explicit. |

The smooth selector (W(y,z;\varepsilon)) and its noncommuting
(z\to0), (\varepsilon\to0) limits therefore do not enter the primary
v1.7.7 linear-response experiment. A later side-selective residual is
admissible only after its adjoint projection onto the translation mode has been
removed. This prevents that residual from changing the registered coupling
rate.

## Rate and time map

The registered total spread rate remains

\[
\kappa=2.5\ \text{per model-time unit}=0.025\ \mathrm{s}^{-1}.
\]

The symmetric primary experiment uses

\[
\kappa_{12}=\kappa_{21}=1.25
\]

per model-time unit. With

\[
\Delta u=0.005,
\]

the explicit spread factor is

\[
1-\kappa\Delta u=0.9875,
\]

which is positive and resolves the 40-second response time with 80 operational
steps.

## Deterministic tractability probe

The design script does not implement the new production coupling. It injects
the proposed field through the accepted solver's existing external-source
entry and compares the result with a paired no-coupling step. This isolates
the field-to-boundary response without random innovations, clocks or
subordination.

For nine registered spreads from (-0.08) to (0.08), including zero:

- every nonzero spread produces the required receiving-book drift signs;
- the observed total rate lies between `2.498338` and `2.499672` per
  model-time unit;
- the largest relative rate error is `0.000665`;
- opposite signed spreads give equal measured rates;
- the pair-centre drift is at most `6.1e-16`;
- zero spread gives exactly zero coupling response; and
- all reaction boundaries are unique and more than eight log-price units from
  a domain edge.

This is a one-step deterministic tractability result. It does not establish
long-path nonlinear stability or the stochastic coupling-only Epps curve;
those are v1.7.7 tests.

## v1.7.7 implementation contract

The next gate must:

1. add a distinct `TranslationModeCoupling` type whose parameter is the
   ordered response rate `kappa_jk`;
2. retain `RegularizedCoupling` byte-for-byte as the accepted comparator;
3. construct each mode from the receiving book's immutable most recent
   pre-step density on the uniform grid;
4. keep zero-spread stationary initialization unchanged;
5. recover the ordered and total rates from deterministic local drift and
   perturbation relaxation before generating stochastic paths;
6. test signed perturbations, grid convergence, unique boundaries, front-mode
   projection error and pair-centre preservation;
7. run the coupling-only stochastic Epps experiment only after the independent
   rate gate passes; and
8. leave the combined curve untouched and unfitted until v1.7.8.

The previously registered statistical curve criteria remain in force: rate
error at most 5%, curve RMSE at most 0.03, standardized RMSE at most 2.0,
pointwise normal 95% coverage at least 0.90 and plateau shift at most 5%.

## Evidence

- `config/config-v1.7.6.json` freezes the decision and v1.7.7 contract;
- `outputs/coupling-correction-candidates-v1.7.csv` records four candidates;
- `outputs/coupling-translation-mode-probe-v1.7.csv` records nine signed
  deterministic probes;
- `diagnostics/coupling-correction-design-checks-v1.7.csv` records 26 verified
  checks and zero failures; and
- `source/source-v2/COUPLING-CORRECTION-DESIGN-v1.7.tex` records the formal
  design without editing the accepted paper source.

## Stage boundary

External acceptance was recorded on 2026-08-20. The v1.7.7 gate implements and
independently validates this correction. The combined no-refit prediction was
originally assigned v1.7.8; external portability corrections and one
slope-consistency test correction moved the active combined/reproducibility
gate to v1.7.11 and Stage 7 stability and integrity closure to v1.7.12.
