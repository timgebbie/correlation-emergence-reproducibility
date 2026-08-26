# Future impact, event and dependence diagnostics

## Modelling boundary

The present one-front density model generates a reaction-boundary log-mid-price.
It does not yet generate a best bid, best ask, transaction price or labelled
trade tape. The existing shock field is therefore an order-density impulse. It
must not be called a single trade until an event operator gives it side, size,
aggressor and execution semantics.

An explicit spread ultimately requires distinct bid and ask fronts and the
associated side currents. The one-front event layer below remains useful for
controlled impact experiments, but this limitation must accompany its results.

## Event operators

- A limit-order event passively adds signed density on a declared side and at a
  non-crossing log-price. Cancellation remains a distinct event.
- A market-order event aggressively removes opposing density, beginning at the
  reaction region and consuming outward until its declared volume is filled.
- Each simulated market event carries a ground-truth aggressor sign and size.
  Meta-orders are declared schedules of signed child market events, not one
  large undifferentiated density shock.

## Own impact and cross-impact

For an event in book `k`, measure the signed response in book `j` at operational
lag `ell`, conditional on event sign and size. The diagonal responses are own
impact; the off-diagonal responses are cross-impact. Report the full two-by-two
response matrix, uncertainty, liquidity state and relaxation after the event.

For a meta-order, report impact against cumulative signed volume, participation
rate and execution horizon, followed by post-execution decay. Single-event and
meta-order impact must be measured in operational time first and again after
the Stage 5 book-specific subordination. Common random numbers will separate
impact from path noise.

## Dependence diagnostics

The primary mid-price diagnostic is the autocorrelation of log-mid-price
increments, not the level autocorrelation of a potentially nonstationary price.
Level autocorrelation may be shown only as a clearly marked secondary view.
Operational-event lags and calendar-time lags remain separate.

Three trade-sign series will be constructed and compared:

1. ground-truth aggressor sign from the simulated market event;
2. quote or midpoint-rule sign relative to the pre-event model mid-price; and
3. tick-rule sign from the transaction-price change, with a declared zero-tick
   carry-forward rule.

For each, report sign autocorrelation, effective sample counts, pairwise
agreement and misclassification relative to the simulated ground truth. No
sign convention will be silently substituted for another.

## Planned gates

- `v1.8.0`: explicit limit/market event operators and labelled event records;
- `v1.8.1`: single-event own/cross-impact;
- `v1.8.2`: scheduled meta-orders, own/cross meta-order impact and relaxation;
- `v1.8.3`: operational/calendar mid-price-increment autocorrelations and the
  three trade-sign measurements, closing Stage 8.

These follow the Stage 4 operational solver, Stage 5 clocks, Stage 6 paired
mechanism experiments and Stage 7 publication-figure comparisons. They extend
the Bauer experiments under the Angstmann--Gebbie operational-time/
subordination architecture.
