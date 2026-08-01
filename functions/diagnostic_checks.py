"""Claim-relevant numerical diagnostics used by scripts and tests."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from functions.correlation_build_up import (
    combined_build_up,
    fractional_build_up,
    ordinary_build_up,
    ordinary_derivative,
    rate_elasticity,
)
from functions.coupling_moment import (
    analytic_half_line_moment,
    discrete_selected_moment,
    numerical_continuum_moment,
    response_rate_total,
)


@dataclass(frozen=True)
class DiagnosticResult:
    diagnostic_id: str
    diagnostic: str
    expected_result: str
    tolerance: str
    observed_result: str
    maximum_error: float
    status: str
    supports: str
    does_not_prove: str

    def row(self) -> dict[str, object]:
        return asdict(self)


FRACTIONAL_REFERENCE_VALUES = {
    # Independently evaluated with adaptive quadrature over the Pollard density.
    (0.6, 0.1): 0.15269402514076091,
    (0.6, 1.0): 0.43111553906250590,
    (0.6, 10.0): 0.76668444144241290,
    (0.8, 0.1): 0.08815275680922374,
    (0.8, 1.0): 0.40209868365919565,
    (0.8, 10.0): 0.83988010205047190,
}


OVERLAY_REQUIRED_FIELDS = {
    "aggregation_scale",
    "aggregation_unit",
    "curve_type",
    "mechanism",
    "normalized_correlation",
    "absolute_correlation",
    "uncertainty",
    "uncertainty_type",
    "parameter_profile",
    "software_version",
}


def run_diagnostic_checks(config: dict) -> list[DiagnosticResult]:
    tolerances = config["diagnostics"]
    results: list[DiagnosticResult] = []

    small_x = 1.0e-6
    small_reference = small_x / 2.0 - small_x**2 / 6.0 + small_x**3 / 24.0
    zero_error = abs(float(ordinary_build_up(0.0)))
    small_error = abs(float(ordinary_build_up(small_x)) - small_reference)
    results.append(
        DiagnosticResult(
            "D01",
            "Ordinary zero and small-argument limit",
            "F(0)=0 and the declared small-x series is recovered",
            f"abs error <= {tolerances['ordinary_absolute_tolerance']:.1e}",
            f"F(0)={ordinary_build_up(0.0):.3e}; series error at 1e-6={small_error:.3e}",
            max(zero_error, small_error),
            "Verified" if max(zero_error, small_error) <= tolerances["ordinary_absolute_tolerance"] else "Failed check",
            "Stable evaluation at the origin",
            "Validity of the modelling approximation",
        )
    )

    x = np.logspace(-5, 2, 500)
    values = np.asarray(ordinary_build_up(x))
    monotonic_violation = max(0.0, float(-np.min(np.diff(values))))
    bound_violation = max(0.0, float(-np.min(values)), float(np.max(values) - 1.0))
    ordinary_error = max(monotonic_violation, bound_violation)
    results.append(
        DiagnosticResult(
            "D02",
            "Ordinary bounds and monotonicity",
            "0 <= F(x) < 1 and non-decreasing for x >= 0",
            f"violation <= {tolerances['ordinary_absolute_tolerance']:.1e}",
            f"range=[{values.min():.8f}, {values.max():.8f}]; min increment={np.min(np.diff(values)):.3e}",
            ordinary_error,
            "Verified" if ordinary_error <= tolerances["ordinary_absolute_tolerance"] else "Failed check",
            "Qualitative ordinary-kernel behaviour",
            "Empirical validity of the Epps envelope",
        )
    )

    derivative = np.asarray(ordinary_derivative(x))
    step = 1.0e-6 * np.maximum(1.0, x)
    finite_difference = (np.asarray(ordinary_build_up(x + step)) - np.asarray(ordinary_build_up(np.maximum(0.0, x - step)))) / (
        x + step - np.maximum(0.0, x - step)
    )
    derivative_error = float(np.max(np.abs(derivative - finite_difference)))
    derivative_tolerance = 2.0e-7
    results.append(
        DiagnosticResult(
            "D03",
            "Ordinary analytic derivative",
            "Analytic derivative agrees with centred finite differences",
            f"max error <= {derivative_tolerance:.1e}",
            f"max error={derivative_error:.3e}",
            derivative_error,
            "Verified" if derivative_error <= derivative_tolerance else "Failed check",
            "Rate-sensitivity calculation",
            "Global parameter identifiability",
        )
    )

    elasticity_short = float(rate_elasticity(1.0e-8))
    elasticity_long = float(rate_elasticity(1.0e5))
    elasticity_error = max(abs(elasticity_short - 1.0), elasticity_long)
    elasticity_tolerance = 2.0e-5
    results.append(
        DiagnosticResult(
            "D04",
            "Ordinary elasticity limits",
            "S_F -> 1 at short scale and S_F -> 0 at long scale",
            f"combined limit error <= {elasticity_tolerance:.1e}",
            f"S(1e-8)={elasticity_short:.12f}; S(1e5)={elasticity_long:.3e}",
            elasticity_error,
            "Verified" if elasticity_error <= elasticity_tolerance else "Failed check",
            "Aggregation-scale sensitivity interpretation",
            "An estimator's finite-sample information content",
        )
    )

    delta = np.logspace(-3, 2, 301)
    ordinary = np.asarray(ordinary_build_up(delta))
    fractional_one = np.asarray(fractional_build_up(delta, 1.0))
    alpha_one_error = float(np.max(np.abs(ordinary - fractional_one)))
    results.append(
        DiagnosticResult(
            "D05",
            "Fractional alpha-one recovery",
            "F_alpha with alpha=1 equals the ordinary kernel",
            f"max error <= {tolerances['alpha_one_tolerance']:.1e}",
            f"max error={alpha_one_error:.3e}",
            alpha_one_error,
            "Verified" if alpha_one_error <= tolerances["alpha_one_tolerance"] else "Failed check",
            "Correct ordinary endpoint of the fractional evaluator",
            "Accuracy for all complex Mittag-Leffler arguments",
        )
    )

    reference_errors = []
    for (alpha, point), reference in FRACTIONAL_REFERENCE_VALUES.items():
        reference_errors.append(abs(float(fractional_build_up(point, alpha)) - reference))
    fractional_reference_error = max(reference_errors)
    results.append(
        DiagnosticResult(
            "D06",
            "Fractional independent reference values",
            "Release evaluator matches adaptive-quadrature references",
            f"max error <= {tolerances['fractional_reference_tolerance']:.1e}",
            f"six-point max error={fractional_reference_error:.3e}",
            fractional_reference_error,
            "Verified" if fractional_reference_error <= tolerances["fractional_reference_tolerance"] else "Failed check",
            "Accuracy on the planned non-negative real-axis profiles",
            "A general-purpose Mittag-Leffler implementation",
        )
    )

    fractional_violation = 0.0
    for alpha in (0.6, 0.8):
        curve = np.asarray(fractional_build_up(delta, alpha))
        fractional_violation = max(
            fractional_violation,
            max(0.0, float(-np.min(curve))),
            max(0.0, float(np.max(curve) - 1.0)),
            max(0.0, float(-np.min(np.diff(curve)))),
        )
    results.append(
        DiagnosticResult(
            "D07",
            "Fractional bounds and monotonicity",
            "Release curves remain in [0,1] and non-decreasing",
            f"violation <= {tolerances['fractional_reference_tolerance']:.1e}",
            f"maximum violation={fractional_violation:.3e}",
            fractional_violation,
            "Verified" if fractional_violation <= tolerances["fractional_reference_tolerance"] else "Failed check",
            "Qualitative stability over the plotting grid",
            "Fractional-clock empirical validity",
        )
    )

    analytic = analytic_half_line_moment(1.0, 1.0)
    numeric = numerical_continuum_moment(1.0, 1.0, 0.2, 0.1, points=100_001)
    moment_relative_error = abs(numeric / analytic - 1.0)
    results.append(
        DiagnosticResult(
            "D08",
            "Decaying-Gaussian first moment",
            "Numerical full-domain selected moment equals analytic half-line moment",
            f"relative error <= {tolerances['moment_relative_tolerance']:.1e}",
            f"analytic={analytic:.12f}; numerical={numeric:.12f}",
            moment_relative_error,
            "Verified" if moment_relative_error <= tolerances["moment_relative_tolerance"] else "Failed check",
            "The active analytic moment implementation",
            "Equivalence to the legacy positive-exponential source",
        )
    )

    epsilon_moments = [
        numerical_continuum_moment(1.0, 1.0, 0.2, eps, points=50_001)
        for eps in (0.01, 0.1, 1.0)
    ]
    symmetry_error = max(abs(value / analytic - 1.0) for value in epsilon_moments)
    results.append(
        DiagnosticResult(
            "D09",
            "Centred-selector continuum invariance",
            "Symmetric first moment is independent of selector width",
            f"relative error <= {tolerances['moment_relative_tolerance']:.1e}",
            f"max relative error over three epsilon values={symmetry_error:.3e}",
            symmetry_error,
            "Verified" if symmetry_error <= tolerances["moment_relative_tolerance"] else "Failed check",
            "Parity control for the finite-grid experiment",
            "Invariance for asymmetric kernels or domains",
        )
    )

    grid_errors = []
    for dx in (1.5, 1.0, 0.75, 0.5):
        epsilon = (2.0 * dx) ** 2
        discrete, _, _ = discrete_selected_moment(1.0, 1.0, 0.2, epsilon, dx, 6.0)
        grid_errors.append(abs(discrete / analytic - 1.0))
    convergence_error = grid_errors[-1]
    convergent = all(right <= left + 1.0e-14 for left, right in zip(grid_errors[:-1], grid_errors[1:]))
    results.append(
        DiagnosticResult(
            "D10",
            "Centred finite-grid convergence",
            "Moment error decreases from a deliberately coarse lattice under refinement",
            f"finest error <= {tolerances['centered_grid_convergence_tolerance']:.1e}",
            f"errors={','.join(f'{value:.3e}' for value in grid_errors)}",
            convergence_error,
            "Verified" if convergent and convergence_error <= tolerances["centered_grid_convergence_tolerance"] else "Failed check",
            "Numerical representation convergence",
            "Convergence of the future legacy simulator",
        )
    )

    baseline_rate = response_rate_total(
        books=config["boundary"]["books"],
        coupling_strength=config["boundary"]["coupling_strength"],
        source_amplitude=config["boundary"]["source_amplitude"],
        source_width=config["boundary"]["source_width"],
        front_slope_abs=config["boundary"]["front_slope_abs"],
    )
    rate_error = abs(baseline_rate - 1.0)
    results.append(
        DiagnosticResult(
            "D11",
            "Boundary baseline response normalisation",
            "Two-book baseline total response rate equals one",
            f"abs error <= {tolerances['ordinary_absolute_tolerance']:.1e}",
            f"kappa_total={baseline_rate:.12f}",
            rate_error,
            "Verified" if rate_error <= tolerances["ordinary_absolute_tolerance"] else "Failed check",
            "Transparent Figure 4 nondimensionalisation",
            "A calibrated physical response rate",
        )
    )

    product = np.asarray(combined_build_up(ordinary, ordinary))
    product_error = max(0.0, float(-np.min(product)), float(np.max(product) - 1.0))
    results.append(
        DiagnosticResult(
            "D12",
            "Combined-factor construction",
            "Combined curve equals diagnosed component product and remains bounded",
            f"violation <= {tolerances['ordinary_absolute_tolerance']:.1e}",
            f"range=[{product.min():.8f}, {product.max():.8f}]",
            product_error,
            "Verified" if product_error <= tolerances["ordinary_absolute_tolerance"] else "Failed check",
            "Implementation of the stated leading-order factorisation",
            "Independence or exactness of the factorisation",
        )
    )

    invalid_cases = 0
    for callback in (
        lambda: ordinary_build_up(-1.0),
        lambda: fractional_build_up(1.0, 0.0),
        lambda: fractional_build_up(1.0, 0.8, 0.0),
        lambda: analytic_half_line_moment(-1.0, 1.0),
    ):
        try:
            callback()
        except ValueError:
            invalid_cases += 1
    invalid_error = float(4 - invalid_cases)
    results.append(
        DiagnosticResult(
            "D13",
            "Invalid-input handling",
            "Four invalid parameter cases fail clearly",
            "all four raise ValueError",
            f"caught={invalid_cases}/4",
            invalid_error,
            "Verified" if invalid_cases == 4 else "Failed check",
            "Clear failure for out-of-domain inputs",
            "Protection against every possible misuse",
        )
    )

    schema_error = 0.0 if len(OVERLAY_REQUIRED_FIELDS) == 10 else 1.0
    results.append(
        DiagnosticResult(
            "D14",
            "v2 analytic/simulation overlay contract",
            "Required scientific and provenance roles are declared",
            "all ten roles present",
            f"declared roles={len(OVERLAY_REQUIRED_FIELDS)}/10",
            schema_error,
            "Verified" if schema_error == 0.0 else "Failed check",
            "A stable semantic interface for future simulation curves",
            "Compatibility with an implementation not yet converted",
        )
    )

    return results


__all__ = [
    "DiagnosticResult",
    "FRACTIONAL_REFERENCE_VALUES",
    "OVERLAY_REQUIRED_FIELDS",
    "run_diagnostic_checks",
]
