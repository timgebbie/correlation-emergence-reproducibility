# Bauer antecedent and corrected release boundary

## Status

The public v2 computational route does not contain or execute the historical
Bauer et al. Julia-to-Python port. That implementation was used during staged
development as a numerical antecedent, a conversion audit and a contrast case.
Its code, stored simulations, development figures and legacy-only tests remain
recoverable in the sealed pre-v1.9.3 gates and repository history.

This document retains only the provenance needed to interpret the corrected
Angstmann--Gebbie implementation without suggesting that the v2 archive
reproduces the retired code.

## Scientifically relevant distinctions

1. **Time layer.** The retired route allowed nonuniform waiting information to
   enter the state update. The accepted route evolves both books first on one
   uniform operational grid. Book-specific calendar clocks act afterwards by
   previous-completed-state sampling.
2. **Observation.** Calendar observations are explicit subordination of a
   complete operational path. No interpolation, extrapolation or nonuniform
   recurrence is used.
3. **Source convention.** The corrected translated source uses
   `exp(-mu*y^2)`. The rejected antecedent form was `exp(-(mu*y)^2)`. These are
   different whenever `mu` is not zero or one and must not be interchanged.
4. **Boundary coupling.** The numerical coupling is applied through the
   receiving front's translation mode, `-d(phi)/dx`, so the resolved density
   profile supplies the boundary width. It does not add a second fixed selector
   layer.
5. **Analytical relationship.** The bounded regularized source in the paper is
   a weak/local moment closure. Its correspondence with the numerical
   translation mode is asserted after projection onto front displacement, not
   as pointwise kernel identity.
6. **Parameters and exponents.** The accepted response coefficient is frozen.
   Operational-time and calendar-time exponents are distinct mathematical
   objects and are not relabelled as one another.

## Claim boundary

The release claims reproducibility of the corrected uniform-operational,
explicit-subordination model and its registered figures, tables, curves and
tests. It credits Bauer et al. as a computational antecedent and documents the
specific corrections above. It does not claim that the downloadable v2 bundle
re-executes or reproduces the Bauer implementation.

The frozen target-paper source in `source/source-v1/` is unchanged. These
clarifications are supplied in the README, computational supplement and
`source/source-v2/` so that any later paper revision can be considered only
after the software release boundary has been reviewed.
