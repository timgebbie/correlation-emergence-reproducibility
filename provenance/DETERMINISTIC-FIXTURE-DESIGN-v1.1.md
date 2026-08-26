# Deterministic fixture design — `v1.1.3`

The Julia and Python implementations must be compared with identical stored
inputs. Matching language-specific random seeds is not sufficient because RNG
algorithms, draw order, and implicit global state can differ.

## Fixture set

| ID | Stored inputs | Required outputs | Purpose |
|---|---|---|---|
| `FX-01` | Small `y` grid and source/coupling parameters | Source and coupling arrays | Sign, scaling, branch, and wrapping checks |
| `FX-02` | `gamma`, length, and hand-checkable short kernel | Sibuya coefficients and cumulative history weights | Off-by-one and kernel-normalisation checks |
| `FX-03` | Synthetic density and several effective shifts | Integer offset, interpolation fraction, shifted arrays | Exact legacy `dr_g_way` parity |
| `FX-04` | Density profiles with one, several, and no local crossings | Crossing index and interpolated boundary or explicit failure | Reaction-boundary continuity and failure semantics |
| `FX-05` | One fixed state, innovations, coupling field, and shock field | One uniform and one legacy nonuniform density step | Term-by-term recurrence parity |
| `FX-06` | Complete short two-book innovations, waiting intervals, and initial densities | Density history, raw boundaries, sampled prices | Coupled update-order parity |
| `FX-07` | Nine-step shock inputs matching `B-SHOCK-01` | Density surfaces and boundaries for every frame | Full shock sequence; frames 1 and 9 are plotted |
| `FX-08` | Ten calibrated path inputs with explicit innovations and clock arrays | Per-path correlations at lags 1:400, mean curve, dispersion inputs, curve spectrum | `B-EPP-01` numerical reproduction |

Fixture files will be machine-readable NPZ/CSV plus a JSON metadata record with
shape, dtype, units, index convention, source commit, parameter set, and SHA-256.
Julia must export the authoritative arrays once in a Julia-capable environment;
Python consumes them without regeneration. Human-readable CSV is used for small
diagnostic arrays, while NPZ is used for density histories.

## Numerical criteria

| Quantity | Deterministic criterion | Reason |
|---|---|---|
| Source, coupling, and kernel primitives | `atol=1e-12`, `rtol=1e-12` | Direct double-precision formulas |
| Shifted density and one-step recurrence | `atol=1e-12`, `rtol=1e-11` | Floating-point accumulation and interpolation |
| Boundary on the same density | absolute error at most `1e-10` price units | One linear interpolation after a discrete sign search |
| Short coupled paths | arrays within `atol=1e-11`, `rtol=1e-10`; identical failure flags | Repeated recurrence without Monte Carlo averaging |
| Correlations and averaged Epps curve | absolute error at most `1e-8` on identical path/timestamp arrays | Cross-library Fourier summation order may differ |
| Figure reproduction | data criteria above plus labelled structural comparison | Renderer metadata makes pixel equality unsuitable |

The tolerances are provisional until Julia exports quantify platform variation.
They may be loosened only with a recorded error budget and no qualitative change
to the target curves.

## Invariants required independently of Julia parity

- array shapes, finite values, and declared dtypes are checked at every step;
- jump probabilities remain in `[0,1]` and satisfy the stated mass balance;
- cancellation/source discretisations satisfy their stability restrictions;
- the fixed operational grid never changes with a clock realization;
- cumulative clock paths are finite and nondecreasing;
- two book clocks are independently addressable and are identical only when the
  fixture explicitly requests it;
- previous-tick sampling never uses future information;
- no-crossing and multiple-crossing cases are explicit failures or declared
  selection rules, never the numeric sentinel `-1` in public results;
- fixed-grid results receive spatial and operational-time refinement checks;
- mechanism-decomposition experiments reuse the same operational innovations.

## Stage gates

1. **Stage 2 entry:** accept this schema and the source/target freeze.
2. **Legacy primitive gate:** `FX-01` through `FX-05` pass before full paths are
   interpreted.
3. **Legacy figure gate:** `FX-06` through `FX-08` pass before Stage 3 is
   accepted.
4. **New-scheme gate:** the operational-time solver passes invariants and
   refinement independently of legacy pixel similarity.
5. **Subordination gate:** identity clocks reproduce operational paths;
   controlled identical and independent clocks behave as declared.

## Current evidence boundary

No authoritative Julia arrays have yet been exported because Julia is not
available in the present execution surface. Fixture definitions and tolerances
are frozen; population of `FX-01` through `FX-08` is a Stage 2 task in a
Julia-capable environment. Until then the Julia formulas are manually audited,
not independently reproduced.

Stage 2 status update: `v1.2.1` adds manually evaluated Python fixture records
for `FX-01` through `FX-04`. These support formula and indexing tests but do not
replace the authoritative Julia export required for cross-language parity.

The accepted `v1.2.2` checkpoint adds a manually evaluated, term-level `FX-05` record for one
fixed-step and one legacy variable-step recurrence. It freezes the history,
removal, source, updated-density, and spatial-shift terms separately. This
advances formula and indexing verification but remains provisional until the
same arrays are exported from the frozen Julia commit.

The accepted `v1.2.3` checkpoint adds a frozen Python `FX-06` orchestration record with two
books, three intervals, explicit realised Normal draws, initial shifted
densities, one shock, and complete stored fields. It is a regression reference
for the audited composition of the term-tested primitives. It is not an
independent Julia export and therefore does not close the cross-language gate.

The accepted `v1.2.4` checkpoint adds `FX-06A`, a small control-flow fixture for the observed
and corrected initialization and clock modes. It freezes the discarded
stationary state, effective zero state, sequential price inputs, retained
intervals, cumulative times, and effective displacements. Like `FX-06`, it is
a Python regression record grounded in static Julia inspection rather than an
executed cross-language export.

The `v1.2.5` gate adds the `FX-06B` target-input ensemble. Its NPZ archive
contains a shared clock vector and complete realised-draw streams for every
configured book and path in `B-EPP-01` and `B-SHOCK-01`. These arrays define a
new declared Python ensemble because the original Julia master innovation seed
is absent. They enable deterministic Stage 3 figures but cannot establish
pixel or path identity with the historical Julia output.
