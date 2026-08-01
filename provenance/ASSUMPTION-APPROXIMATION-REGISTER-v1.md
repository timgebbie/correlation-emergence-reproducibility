# Assumption and approximation register

| Item | Treatment in v1.0.0 |
|---|---|
| Poisson refresh curve | Evaluated as the paper's renewal/overlap envelope, not asserted as an exact asynchronous estimator law in every setting. |
| Exponential response curve | Evaluated after accepting the stated response-kernel and linear-variance normalisation. No OU path simulation is used as a surrogate proof. |
| Combined curve | Treated as the paper's leading-order separable approximation under its C-assumptions. |
| Fractional curve | Evaluated on the non-negative real axis with declared characteristic-time scaling. No unconditional dimensional “slower” claim is made. |
| Fractional identifiability | The leading combined exponent identifies an order sum; separate orders require later-scale information or independent constraints. |
| Correlation scale | `rho_inf` is separated from attenuation and fixed to one in normalised figures. |
| Source convention | Only the decaying Gaussian with finite analytic moment is active. The legacy positive-exponential finite-domain convention is excluded. |
| Boundary response | Frozen-front, first-moment projection is used conditionally. The normalising convention is absorbed into coupling strength as in the paper. |
| Boundary thickness | Front slope/structural thickness, selector width, and lattice spacing are not interchangeable. |
| Selector width | Centred symmetric continuum moment is parity invariant; epsilon sensitivity shown in F5 is numerical representation sensitivity when alignment/domain controls change. |
| Discrete experiment | Rectangle-rule grid, half-cell selector shift, and truncated domain are explicit diagnostics, not the v2 legacy simulator. |
| Computational evidence | Figures and tests illustrate and numerically verify implemented objects; they do not prove assumptions or validate market behaviour empirically. |
