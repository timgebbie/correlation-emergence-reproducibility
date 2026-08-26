# Legacy Julia to Python map — `v1.1.1`

This is a static map of `DominicGBauer/InteractingLOBs.jl` at commit
`c8206c66906580516d2389b57c6955bb2f526862`. It records legacy behaviour before
any correction. Static inspection does not establish that the Julia package
executes in the current environment. The package declares version 0.1.0 and its
manifest records Julia 1.8.5.

## Scientific operation map

| Scientific operation | Frozen Julia location | Observed legacy behaviour | Planned Python object |
|---|---|---|---|
| Model state and discretisation | `src/reaction_diffusion_path.jl`: `SLOB` | Stores nominal `Delta x`, `Delta t` and, for the nonuniform route, per-step `Delta xs`, `Delta ts`, and cumulative times | `SimulationConfig`, `BookState`, `GridSpec` dataclasses |
| Source | `src/source_function.jl` | Decaying odd Gaussian source `-lambda*mu*y*exp(-(mu*y)^2)` with periodic wrapping | `order_book_sources.py` with scalar and vector tests |
| Pair coupling | `src/coupling_function.jl` | Bounded, spread-dependent rescaling of the source; this is the legacy phenomenology, not the current paper’s regularised local-response approximation | `legacy_coupling.py`, isolated from later response models |
| Stochastic jump bias | `src/randomness_function.jl` | Gaussian innovations clipped through left/right jump probabilities; optional lag response | `innovations.py` consuming explicit arrays, not hidden global RNG state |
| Sibuya history kernel | `src/reaction_diffusion_path.jl` | Kernel is constructed manually; `SibuyaKernelModified` is exported but has no definition in the repository | `sibuya.py` with coefficient and convolution fixtures |
| Density recurrence | `src/reaction_diffusion_spde.jl`: `calculate_next_step_no_exp` | Fixed-step DTRW recurrence on a uniform grid | `dtrw_solver.py::step_uniform_legacy` |
| Variable-step recurrence | `src/reaction_diffusion_spde.jl`: `calculate_next_step_exp` | Cancellation/source terms use actual waiting intervals; the transport history is evaluated through a variable spatial shift | `dtrw_solver.py::step_nonuniform_legacy` only for reproduction |
| Variable spatial shift | `src/reaction_diffusion_spde.jl`: `dr_g_way` | Converts the step-specific displacement into integer offset plus linear interpolation | `legacy_interpolation.py`, explicitly quarantined from the new scheme |
| Reaction boundary | `src/reaction_diffusion_spde.jl` | Searches near the previous crossing and linearly interpolates the zero; returns `-1` on failure | `price_boundary.py::local_zero_crossing` with explicit failure type |
| One-book impulse | `src/rl_push_function.jl` | Adds a fixed-grid order-density impulse during a simulation-index interval | `shocks.py::apply_density_impulse` |
| Multi-book stepping | `src/reaction_diffusion_path.jl`: `InteractOrderBooks` | Books advance at the same integer loop index; coupling consumes the contemporaneous other-book state | `coupled_solver.py` with a declared update convention |
| Nonuniform clock generation | `src/reaction_diffusion_path.jl`: `generate_Delta_ts_exp` | Exponential intervals use a hard-coded seed of 1; identically parameterised books therefore receive identical clock arrays | `legacy_clock.py` for reproduction; later replaced by book-specific `ClockPath` objects |
| Price sampling | `src/reaction_diffusion_path.jl`: `get_sample_inds_by_sampling_at_integer_real_times` | Index selection uses nominal uniform `Delta t` and does not use cumulative nonuniform times | `sampling.py::previous_tick` using explicit time arrays |
| Epps estimation | `src/Epps/epps.jl` and NUFFT helpers | Previous-tick sampling is followed by a Fourier correlation estimator, but nonuniform raw cumulative times are not supplied to the top-level call | `epps_estimators.py` with timestamps mandatory in the API |
| Epps inset | `src/Epps/generate_power_spectrum.jl` | FFT is applied to the averaged Epps curve | `diagnostics.py::curve_spectrum`, named to avoid a price-spectrum claim |

Unicode Julia identifiers are written in words in this document so the map is
portable; the code remains authoritative for exact spelling.

## Reaction boundary versus regularised transition layer

The legacy and target models use the same observable price architecture: each
book has one mid-price extracted from the zero crossing of its signed density,
with linear interpolation between neighbouring grid points. The “thick” object
in the current paper is not a second price boundary. It is the resolved
transition layer in the regularised directed coupling

`W(y,z;epsilon) = (1 + tanh(y*z/epsilon))/2`,

whose width in the local coordinate is approximately `epsilon/abs(z)`. The
paper requires the reference width to be larger than the grid spacing and
smaller than the source-variation scale. The Julia pair-trader source instead
uses finite-grid side-selective rescaling through `f(y/g)` and `g*f(y)`. These
sources are not pointwise identical. Their comparison is therefore made through
the projected front-response moment, with the regularisation width, spatial
grid, and front slope kept as separate quantities.

The Python conversion will preserve the legacy finite-grid coupling for Stage 3
parity. The regularised transition-layer response becomes a separate model
component for the later boundary/clock decomposition; changing its width must
not change either book's observation clock.

## Legacy versus target time construction

| Layer | Legacy nonuniform implementation | Target construction |
|---|---|---|
| Spatial grid | Step-dependent effective displacement and interpolation | One fixed grid `x_i = i Delta x` |
| Solver clock | Variable waiting intervals enter the recurrence | Uniform operational time `u_n = n Delta u` |
| Book clocks | Recreated from the same fixed seed for equal books | Explicit, independently seeded or supplied `T_1(u)` and `T_2(u)` |
| Boundary | Extracted after each variable-step update | Extracted once per uniform operational step |
| Calendar observation | Nominal-step index helper | Explicit subordination/previous-tick rule based on cumulative clock paths |
| Mechanism comparison | Clock and boundary interpolation are entangled | Hold operational paths fixed while clocks vary, then hold clocks fixed while boundary response varies |

## Findings that must be preserved as tests, not copied as design

1. The same fixed seed in `generate_Delta_ts_exp` couples the two legacy clocks
   perfectly when their parameters agree.
2. The nonuniform sampling helper ignores cumulative waiting times.
3. The Epps call supplies integer indices for raw paths rather than their
   nonuniform timestamps.
4. Julia tests are stale and do not form an executable regression oracle for the
   current API.
5. The package exports `SibuyaKernelModified`, but no implementation was found.
6. The calibrated scripts invoke `InteractOrderBooks(..., -1, ...)`, so the
   saved figures do not carry a reproducible master seed for all innovations.

These behaviours explain why pixel hashes are provenance anchors rather than
the cross-language numerical acceptance criterion. Stage 2 must reproduce
legacy formulas with explicit inputs. Stage 4 must implement the fixed-grid
operational-time scheme independently, not silently mutate the legacy routine.

## Source-kernel correction boundary

The faithful Stage 2 port and Stage 3 legacy reproduction retain the Julia
source

`-lambda*mu*y*exp(-(mu*y)^2)`.

After the legacy parity tests pass, the new operational-time implementation will
replace the exponent `-(mu*y)^2` by `-mu*y^2`. This is a deliberate model
correction, not part of the language conversion. Both implementations must
remain separately named and tested so that a change in the source width cannot
be mistaken for a clock or boundary-response effect.

## Planned module boundary

The initial Python conversion will add focused modules under `functions/`:

- `simulation_state.py` for immutable configuration and mutable book state;
- `order_book_sources.py` and `legacy_coupling.py` for deterministic fields;
- `sibuya.py` and `dtrw_solver.py` for history weights and recurrences;
- `legacy_interpolation.py` solely for parity with the old nonuniform solver;
- `price_boundary.py`, `shocks.py`, and `coupled_solver.py` for observable paths;
- `sampling.py` and `epps_estimators.py` for timestamp-explicit estimation.

Clock/subordination APIs become authoritative only in Stages 4 and 5. The
legacy path remains separately callable until the Stage 3 reproduction gate is
accepted.
