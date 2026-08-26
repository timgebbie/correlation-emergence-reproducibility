# Declared two-book clock ensembles — `v1.5.1`

## Conformity decision

Angstmann--Gebbie do not impose one observation-clock law. The paper uses an
independent Poisson-refresh approximation and separately gives an
inverse-stable fractional-clock version. The Poisson pooled arrival rate is
exact under independent exponential waits, while the associated overlap
envelope remains an effective approximation. The fractional overlap envelope
is likewise not claimed as the exact joint-overlap law for arbitrary
inverse-stable clocks.

The implementation therefore retains both clock constructions as explicitly
named alternatives. It does not fit one law, infer the calendar exponent from
the order-density exponent, or merge the two ordinary limits.

## Clock transforms

For the Poisson-refresh benchmark, caller-supplied open uniforms are mapped to
calendar waits by

```text
Delta T_j = -log(1-U_j)/lambda_j^clk.
```

The declared rate is 200 per calendar-time unit for each book, so the expected
wait `0.005` matches the Stage 4 operational step in scale. This is a numerical
benchmark rather than an empirical calibration.

For `0 < alpha_t < 1`, caller-supplied uniform pairs are transformed by the
Kanter positive-stable representation. Under the normalization used here,

```text
E[exp(-s Delta T_j)]
    = exp[-Delta u*(calendar_scale_j*s)^alpha_t,j].
```

At `alpha_t=1`, the stable subordinator becomes deterministic drift,
`Delta T_j=calendar_scale_j*Delta u`. It is not the exponential waiting-time
clock. This distinction prevents the Poisson refresh approximation from being
silently identified with the ordinary stable-subordinator limit.

All transform inputs are external arrays. No file under
`functions/observation/` owns a random-number generator.

## Declared ensemble

`config/config-v1.5.1.json` declares 16 paths, 2,400 operational steps and
three scenarios:

1. `poisson_independent`: equal-rate exponential waits from separate book
   streams;
2. `poisson_shared_fraction`: equal-rate waits with a declared 60% common-wait
   mixture and otherwise separate book streams;
3. `inverse_stable_independent`: separate positive-stable clocks with
   `alpha_t=(0.8,0.65)` and unit calendar scales.

The common-wait mixture is a controlled dependence diagnostic. It is not part
of the independent Poisson derivation in the paper and is not presented as a
copula calibration.

`scripts/17_generate_clock_ensembles.py` is the only RNG owner. It uses
explicit PCG64 seeds and maps the top 53 bits to the open unit interval. The
resulting archive and JSON companion retain:

- all realised interval arrays with shape `(16,2400,2)`;
- all cumulative clock paths with shape `(16,2401,2)`;
- the common uniform operational lattice;
- law parameters, stream identifiers and complete seed provenance;
- dependence policies and realised dependence diagnostics;
- array hashes, configuration hash and archive hash.

The stored float64 paths and their hashes are authoritative. Reproduction does
not depend on another NumPy version reproducing the same seeded sequence.

## Evidence and interpretation

`scripts/18_run_clock_ensemble_checks.py` validates 20 properties, including
positivity, cumulative-path identity, extraction of individual book clocks,
exponential mean and survival values, independent and controlled dependence,
the stable Laplace transform, the deterministic `alpha_t=1` limit and the
absence of RNG ownership in the observation library.

It also writes 96 path-book summary rows. A positive-stable realised sample
has a finite numerical mean, but for `alpha_t<1` that number is not interpreted
as an estimator of a finite theoretical increment mean. Clock horizons are
therefore retained path by path rather than summarized by a supposed common
mean horizon.

The gate does not yet apply these clocks to the accepted operational ensemble
or estimate calendar-time correlations. Those operations require an explicit
common supported calendar window and effective sample counts at every lag.

Gate verification: the 202-entry file manifest, all 20 generated ensemble
checks and the complete 215-test route pass in the working bundle.

Stage: 5 — stochastic two-book clock ensembles (`v1.5.1`)

Status: accepted at `v1.5.1`; timestamp-aware calendar estimators accepted at `v1.5.2`
