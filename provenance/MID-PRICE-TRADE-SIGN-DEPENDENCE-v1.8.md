# Mid-price and trade-sign dependence diagnostics — `v1.8.3`

Status: provisional gate; external acceptance pending

Accepted parent: `v1.8.2` at commit `aedfdc6`

## Architecture

The experiment completes a declared market-event tape on the uniform
operational grid. Each market-order density delta is applied immediately
before its declared operational step. No clock, interpolation, stochastic wait
or nonuniform state update enters this recurrence. Only after the complete
two-book path exists are two independent book-specific Poisson
previous-refresh clocks applied. Operational dynamics and calendar observation
therefore remain separate in the Angstmann--Gebbie sense used throughout the
v2 extension.

The driver owns the event and sign fixtures. It uses eight symmetry-controlled
innovation paths, 48 fully filled market orders per book and path, and 768
market-event records in total. The market orders have quantity 0.015. Passive
limit orders remain nontrades and are excluded from every trade-sign series.
The accepted translation-mode coupling, clock rates and source convention are
unchanged; there is no component or combined-curve refit.

## Estimands

The price diagnostic is the Pearson autocorrelation of five-second log-mid
price increments. It is measured on the uniform operational path and on the
same query grid after previous-refresh subordination. Mid-price level
autocorrelation is excluded because the simulated price level is not the
stationary estimand required by this diagnostic.

Three sign conventions are retained separately on the same fully filled event
records:

1. ground-truth aggressor side from the declared market event;
2. quote/midpoint classification from the consumed-grid execution-price proxy
   relative to the pre-event midpoint; and
3. the frozen legacy tick rule, with first sign zero and zero ticks carrying
   the preceding nonzero sign.

Event-time sign autocorrelation is measured by same-book event lag. Calendar-
time signed-flow autocorrelation is a different statistic: declared events are
mapped through the book-specific clock, accumulated, sampled in five-second
calendar bins and differenced. These two axes and estimators are not silently
identified with each other.

## Result

- all 49 registered checks pass;
- ground-truth lag-one event-sign autocorrelation is `0.401336`;
- quote/midpoint agreement with ground truth is `1.000000`;
- legacy tick-rule agreement with ground truth is `0.947917`;
- cross-book declared-sign correlation is `0.062500`;
- operational/calendar log-mid-increment ACF RMSE is `0.150248`; and
- minimum registered price-increment variance is `0.000412220`.

Figure 11 reports the log-mid increment and trade-sign autocorrelations across
the operational, event and calendar layers, including the three event-time sign
curves, the three subordinated signed-flow curves, and convention agreement.
The machine-readable evidence contains 42 price-curve rows, 672 price-member
rows, 39 event-sign curve rows, 624 event-sign member rows, 63 calendar-flow
curve rows, 1,008 calendar-flow member rows, three agreement rows, 768 event
rows, 16 clock rows and one compressed path archive.

## Scientific boundary

The Markov sign generator is a finite persistent estimator fixture. Its
persistence is declared input, not a simulated market result, and it is not
endogenous long memory. The exact quote/ground-truth identity follows from the
one-front event semantics and is not an empirical statement about a classifier.
The tick rule uses a consumed-grid execution-price proxy rather than an
observed exchange transaction price. The one-front model still has no explicit
best bid/ask spread or matching engine. Accordingly these are measurement and
architecture diagnostics, not an empirical calibration or a claim that the
model has generated real-market order-sign persistence.

The source-v1 paper remains frozen. Figure 11 adds no theoretical curve and
does not amend the analytical Epps construction. It verifies that event-time,
operational-time and explicitly subordinated calendar-time measurements can be
kept distinct on the accepted numerical architecture. External acceptance
closes Stage 8 and advances to `v1.9.0`, the final estimator-aware combined
Epps theory/simulation integration.
