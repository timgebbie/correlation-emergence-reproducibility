# Scheduled meta-order own and cross impact — `v1.8.2`

Status: provisional gate; external acceptance pending

Accepted parent: `v1.8.1` at commit
`489412b85a5c982aa0bffc80a688a17d908ffec3`

## Experiment

A meta-order is a declared schedule of separately labelled child market-order
events, not one large density shock. Each child consumes opposing density from
the current reaction boundary immediately before its declared uniform
operational step. Every child has quantity 0.05 and all children must fill
completely. The four children have fixed total quantity 0.20.

Two schedules identify the execution-horizon effect at equal volume:

- `fast`: children at 0, 5, 10 and 15 seconds; and
- `slow`: children at 0, 20, 40 and 60 seconds.

Eight symmetry-controlled innovation paths cover two event books and two
aggressor sides. Every shocked path is paired with an unshocked control using
the same initial state and exactly the same supplied innovations. The complete
two-by-two own/cross response matrix is sampled after each child and at nine
lags from 0 to 200 seconds after the final child.

Both books are completed on the uniform operational grid before observation.
The same complete paths are then sampled by two distinct independent
book-specific Poisson previous-refresh clocks with equal input rate 0.1 per
second. Calendar interpolation and nonuniform state updates remain forbidden.

## Relation to the accepted coupling architecture

The experiment inherits the `v1.8.1` translation-mode coupling without any
new boundary selector, regularisation width or mesoscale thickness parameter.
The finite front profile remains resolved in the density state. Each child
changes that state, and subsequent coupling acts through the receiving book's
current translation mode.

The source-v1 paper remains frozen. Its bounded regularised source is retained
as an analytical weak-moment closure and historical comparator. The production
translation-mode numerical source is not pointwise identical to that source;
their conformity claim is at the projected front-displacement law. The
meta-order and layer-specific implications are drafted in
`source/source-v2/META-ORDER-NUMERICAL-ARCHITECTURE-v1.8.tex` and inherit the
more complete boundary contrast in
`source/source-v2/TRANSLATION-MODE-NUMERICAL-ARCHITECTURE-v1.8.tex`.

## Result

- fast final-child operational own impact: `0.341453`;
- slow final-child operational own impact: `0.199599`;
- absolute equal-volume execution-horizon difference: `0.141854`;
- minimum final-child operational cross-impact: `0.030545`;
- minimum post-completion own-impact relaxation fraction: `0.748239`;
- minimum post-completion peak cross-impact catch-up fraction: `0.287463`;
  and
- 200-second own/cross ratios: `0.884210` and `0.898501`.

The fast schedule builds larger final own impact because less relaxation and
cross-book transmission occur between children. The slow schedule transmits
more of its response during execution; consequently cross-impact has less left
to catch up after completion. Catch-up is therefore measured at its
post-completion peak. The distinct long-lag ratio separately measures later
own/cross convergence, avoiding a confounding of catch-up and relaxation.

All 50 generated checks pass. Figure 24 uses one common linear response scale.
The machine-readable evidence contains 64 trajectory-curve rows, 1,024
trajectory-member rows, 144 relaxation-curve rows, 2,304 relaxation-member
rows, 256 child-event rows, two schedule records, 16 clock records and one
compressed path archive.

## Scientific boundary

The reported quantity divided by execution horizon is a schedule-intensity
proxy, not a participation rate. A true participation rate is not identified
without background market-order volume. The one-front model is not a complete
matching engine and the volume-weighted consumed-grid execution price remains
a registered proxy. The experiment supplies controlled own/cross response
functions; it does not claim an empirical impact law or introduce a new
theoretical impact curve.

Acceptance advances the numeric sequence to `v1.8.3`, mid-price-increment and
three-convention trade-sign dependence diagnostics.
