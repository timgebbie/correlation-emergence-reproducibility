"""Summarise the frozen structural, fractional, boundary, and grid sensitivities."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.correlation_build_up import combined_build_up, fractional_build_up, ordinary_build_up, rate_elasticity
from functions.coupling_moment import analytic_half_line_moment, discrete_selected_moment, response_rate_total
from functions.diagnostic_checks import OVERLAY_REQUIRED_FIELDS
from functions.io_utils import ensure_output_directories, load_config, write_csv


def _check(identifier: str, name: str, expected: str, observed: str, passed: bool, interpretation: str) -> dict[str, object]:
    return {
        "check_id": identifier,
        "sensitivity_check": name,
        "expected": expected,
        "observed": observed,
        "status": "Verified" if passed else "Failed check",
        "interpretation": interpretation,
    }


def main() -> int:
    ensure_output_directories()
    config = load_config()
    delta = np.geomspace(
        config["aggregation_grid"]["minimum"],
        config["aggregation_grid"]["maximum"],
        config["aggregation_grid"]["points"],
    )
    checks: list[dict[str, object]] = []

    clock = np.asarray(ordinary_build_up(delta))
    for index, ratio in enumerate(config["ordinary"]["coupling_rate_ratios"], start=1):
        response = np.asarray(ordinary_build_up(ratio * delta))
        combined = np.asarray(combined_build_up(clock, response))
        product_error = float(np.max(np.abs(combined - clock * response)))
        checks.append(
            _check(
                f"S{index:02d}",
                f"Ordinary component product at kappa/lambda={ratio:g}",
                "combined equals clock times response",
                f"maximum product error={product_error:.3e}",
                product_error <= 1e-14,
                "Confirms the implemented leading-order separable construction.",
            )
        )

    short_elasticity = float(rate_elasticity(delta[0]))
    long_elasticity = float(rate_elasticity(delta[-1]))
    checks.append(
        _check(
            "S04",
            "Aggregation-scale rate sensitivity",
            "short-scale elasticity near one and plateau elasticity near zero",
            f"S({delta[0]:g})={short_elasticity:.6f}; S({delta[-1]:g})={long_elasticity:.6f}",
            abs(short_elasticity - 1.0) < 4e-4 and long_elasticity < 0.011,
            "Rate information is concentrated before the long-scale plateau.",
        )
    )

    fractional = config["fractional"]
    fractional_kwargs = {
        "series_switch": fractional["series_switch"],
        "quadrature_order": fractional["quadrature_order_per_segment"],
        "quadrature_log_limit": fractional["quadrature_log_limit"],
    }
    slope_estimates: dict[tuple[float, float], float] = {}
    short_mask = delta <= 0.01
    for pair in ((0.8, 0.8), (0.6, 1.0), (0.6, 0.6)):
        clock_fractional = np.asarray(fractional_build_up(delta, pair[0], **fractional_kwargs))
        response_fractional = np.asarray(fractional_build_up(delta, pair[1], **fractional_kwargs))
        combined_fractional = clock_fractional * response_fractional
        slope = float(np.polyfit(np.log(delta[short_mask]), np.log(combined_fractional[short_mask]), 1)[0])
        slope_estimates[pair] = slope
        expected_slope = sum(pair)
        check_number = 5 + len(slope_estimates) - 1
        checks.append(
            _check(
                f"S{check_number:02d}",
                f"Fractional short-scale exponent for {pair}",
                f"log-log slope approaches alpha_c+alpha_r={expected_slope:g}",
                f"fitted slope={slope:.6f}",
                abs(slope - expected_slope) < 0.035,
                "Supports the leading-power sensitivity and equal-sum confounding argument.",
            )
        )
    equal_sum_difference = abs(slope_estimates[(0.8, 0.8)] - slope_estimates[(0.6, 1.0)])
    checks.append(
        _check(
            "S08",
            "Equal-sum fractional-order confounding",
            "equal alpha sums give nearly equal fitted short-scale powers",
            f"slope difference={equal_sum_difference:.6f}",
            equal_sum_difference < 0.02,
            "Short-scale combined curvature alone cannot separate both fractional orders.",
        )
    )

    boundary = config["boundary"]
    expected_elasticities = {
        "coupling_strength": 1.0,
        "source_amplitude": 1.0,
        "source_width": -0.5,
        "front_slope_abs": -1.0,
    }
    for offset, (parameter, expected) in enumerate(expected_elasticities.items(), start=9):
        rates = []
        factors = np.asarray(boundary["perturbation_factors"], dtype=float)
        for factor in factors:
            values = {
                "coupling_strength": boundary["coupling_strength"],
                "source_amplitude": boundary["source_amplitude"],
                "source_width": boundary["source_width"],
                "front_slope_abs": boundary["front_slope_abs"],
            }
            values[parameter] *= factor
            rates.append(response_rate_total(books=boundary["books"], **values))
        fitted = float(np.polyfit(np.log(factors), np.log(rates), 1)[0])
        checks.append(
            _check(
                f"S{offset:02d}",
                f"Boundary-rate elasticity for {parameter}",
                f"elasticity={expected:g}",
                f"fitted elasticity={fitted:.12f}",
                abs(fitted - expected) < 1e-12,
                "Confirms conditional propagation into the response rate, not separate identifiability.",
            )
        )

    discrete = config["discrete_representation"]
    analytic = analytic_half_line_moment(boundary["source_amplitude"], boundary["source_width"])
    centred_errors = []
    shifted_errors = []
    truncated_ratios = []
    for dx in discrete["lattice_spacings"]:
        for resolution in discrete["selector_resolution_ratios"]:
            epsilon = (resolution * dx) ** 2
            centred, _, _ = discrete_selected_moment(
                boundary["source_amplitude"], boundary["source_width"], discrete["directed_spread"], epsilon, dx, discrete["full_domain_halfwidth"]
            )
            shifted, _, _ = discrete_selected_moment(
                boundary["source_amplitude"], boundary["source_width"], discrete["directed_spread"], epsilon, dx, discrete["full_domain_halfwidth"], selector_shift=0.5 * dx
            )
            truncated, _, _ = discrete_selected_moment(
                boundary["source_amplitude"], boundary["source_width"], discrete["directed_spread"], epsilon, dx, discrete["truncated_domain_halfwidth"]
            )
            centred_errors.append(abs(centred / analytic - 1.0))
            shifted_errors.append(abs(shifted / analytic - 1.0))
            truncated_ratios.append(truncated / analytic)
    checks.append(
        _check(
            "S13",
            "Centred full-domain selector invariance",
            "moment ratio remains one across selector and release-grid profiles",
            f"maximum absolute deviation={max(centred_errors):.3e}",
            max(centred_errors) < 1e-12,
            "Confirms the parity control in the discrete implementation.",
        )
    )
    checks.append(
        _check(
            "S14",
            "Off-grid selector sensitivity",
            "half-cell displacement produces a bounded non-zero representation error",
            f"error range=[{min(shifted_errors):.3e},{max(shifted_errors):.3e}]",
            max(shifted_errors) > 0.01 and max(shifted_errors) < 0.15,
            "Shows that alignment can distort the effective response while the continuum moment is unchanged.",
        )
    )
    checks.append(
        _check(
            "S15",
            "Finite-domain truncation sensitivity",
            "truncation lowers the represented moment without changing the continuum formula",
            f"moment-ratio range=[{min(truncated_ratios):.6f},{max(truncated_ratios):.6f}]",
            min(truncated_ratios) > 0.75 and max(truncated_ratios) < 0.95,
            "Separates a finite-domain artefact from structural front thickness.",
        )
    )

    overlay_path = PROJECT_ROOT / "outputs" / "epps-overlay-v1.csv"
    with overlay_path.open("r", encoding="utf-8", newline="") as handle:
        fields = set(csv.DictReader(handle).fieldnames or [])
    missing_fields = OVERLAY_REQUIRED_FIELDS - fields
    checks.append(
        _check(
            "S16",
            "Future v2 overlay schema",
            "all required analytic/simulation semantic fields are present",
            f"missing fields={sorted(missing_fields)}",
            not missing_fields,
            "Allows future simulation curves and uncertainty to be overlaid without changing v1 meanings.",
        )
    )

    fieldnames = list(checks[0])
    write_csv(PROJECT_ROOT / "outputs" / "sensitivity-summary-v1.csv", fieldnames, checks)
    failures = [check for check in checks if check["status"] != "Verified"]
    report = [
        "# Sensitivity and robustness report - v1.0.0",
        "",
        "Artefact status: **diagnostic output**",
        "",
        f"Result: **{len(checks) - len(failures)} verified; {len(failures)} failed**",
        "",
        "| ID | Sensitivity check | Status | Observed |",
        "|---|---|---:|---|",
    ]
    report.extend(
        f"| {check['check_id']} | {check['sensitivity_check']} | {check['status']} | {check['observed']} |"
        for check in checks
    )
    report.extend(
        [
            "",
            "The robust conclusions are local sensitivity, equal-sum fractional confounding, conditional boundary-rate propagation, centred parity invariance, and bounded representation distortions under the declared grid profiles. None is an empirical calibration or a proof of unique parameter recovery.",
            "",
        ]
    )
    (PROJECT_ROOT / "diagnostics" / "sensitivity-report-v1.md").write_text(
        "\n".join(report), encoding="utf-8", newline="\n"
    )

    for check in checks:
        print(f"{check['check_id']}: {check['status']} - {check['sensitivity_check']}")
    if failures:
        print(f"Sensitivity route failed: {len(failures)} check(s) require attention.")
        return 1
    print(f"Sensitivity route completed: {len(checks)} checks verified, 0 failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
