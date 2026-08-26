# Event semantics and impact entry — `v1.8.0`

Status: provisional gate; external acceptance pending

Accepted parent: `v1.7.12`, which closes Stage 7 with the operational-time and
calendar-observation layers separated. This gate adds no stochastic path, no
scientific figure and no change to the frozen source-v1 paper.

## Purpose and model boundary

The current book has one signed-density front and one zero-crossing log
mid-price. It does not yet resolve separate best-bid and best-ask fronts. The
event layer is therefore a controlled one-front impact laboratory, not a full
limit-order-book matching engine. A deterministic execution-price proxy is the
volume-weighted log price of the grid cells consumed by a market event. It is
not an empirical transaction price.

The density convention is positive bid liquidity below the reaction boundary
and negative ask liquidity above it. A limit order adds passive signed density
at one declared interior, noncrossing grid point. A market order consumes the
opposing density from the boundary outwards. Cancellation is reserved as a
distinct future event and is not silently represented as a negative limit
order.

The older Figures 8 and 9 apply a density impulse without a labelled aggressor,
fill rule or execution record. That object remains a legacy shock and is not a trade-impact result.

## Time-layer conformity

An event creates a density delta on the uniform operational grid. The target
driver will apply that delta and then execute one ordinary uniform operational
step. Complete operational paths are generated before any observation clock is
used. Book-specific previous-refresh selection then provides explicit
subordination into calendar time. Nonuniform state updates and calendar-time
interpolation remain forbidden.

This separation conforms to the Angstmann--Gebbie construction: impact is
measured in operational time first, and the same completed paths can then be
observed under different book clocks. The event module imports no solver,
clock, subordination, legacy implementation or random-number generator.

## Event and sign records

Every declared event records an identifier, event type, book, operational
step, side, quantity and optional limit price. `meta_order_id` and
`child_index` are paired fields so that the same record can later identify a
schedule of child market events without changing single-event semantics.

Three sign conventions remain separate:

1. ground-truth aggressor sign from the recorded market-order side, with
   passive events assigned zero;
2. quote/midpoint sign from execution price relative to the pre-event model
   midpoint; and
3. the legacy-compatible tick rule, whose first sign is zero and whose zero
   ticks carry the previous nonzero sign.

Only the tick rule is inherited from the frozen Julia surface. Ground-truth
and midpoint signs are new explicit Python semantics and must not be attributed
to the Bauer implementation.

## Registered impact programme

The full two-book matrix is retained: its two diagonal cells are own impact and
its two off-diagonal cells are cross-impact. Shocked and control paths must use
common random numbers so that a response is not confounded with a different
innovation realization.

- `v1.8.1` will measure single-trade own and cross impact in operational time
  and again after explicit subordination.
- `v1.8.2` will add scheduled child trades, meta-order impact versus cumulative
  signed volume, execution-horizon effects and post-execution relaxation.
- `v1.8.3` will add mid-price-increment dependence and all three trade-sign
  autocorrelation/agreement diagnostics, closing Stage 8.

The final estimator-aware combined Epps comparison is scheduled for `v1.9.0`.
It will display clock-only theory/simulation, coupling-only theory/simulation,
the combined simulation, the paper's leading-order product and the finite-grid,
finite-step estimator-aware theory. Conformity parameters remain frozen; any
optional fitted curve must be separate and explicitly labelled. `v1.9.1` then
streamlines the release surface into release-critical, provenance-only and
development-only material before the numeric `v2.0.0` release.

## Gate evidence

`scripts/32_run_event_semantics_entry.py` evaluates 44 deterministic checks and
writes a 26-row contract register. Its fixtures cover passive placement,
boundary-outward market consumption, full/partial fill policy, conservation,
sign conventions, impact-matrix roles, the version sequence and the later
streamlining boundary. No stochastic path or publication figure is generated
at this gate.
