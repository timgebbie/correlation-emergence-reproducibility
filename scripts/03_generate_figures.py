"""Generate the six frozen scientific figures and their machine-readable data."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib-cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from functions.correlation_build_up import (
    combined_build_up,
    exponential_memory,
    fractional_build_up,
    ordinary_build_up,
    rate_elasticity,
)
from functions.coupling_moment import (
    analytic_half_line_moment,
    discrete_selected_moment,
    response_rate_total,
)
from functions.io_utils import PROJECT_ROOT, ensure_output_directories, load_config, write_csv


FIGURE_NAMES = {
    "F1": "figure-01-ordinary-epps-components-v1",
    "F2": "figure-02-ordinary-epps-sensitivity-v1",
    "F3": "figure-03-fractional-epps-sensitivity-v1",
    "F4": "figure-04-boundary-to-epps-propagation-v1",
    "F5": "figure-05-finite-grid-epps-distortion-v1",
    "F6": "figure-06-calendar-time-epps-memory-v1",
}


def _grid(config: dict) -> np.ndarray:
    spec = config["aggregation_grid"]
    return np.geomspace(spec["minimum"], spec["maximum"], spec["points"])


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9.0,
            "axes.titlesize": 9.5,
            "axes.labelsize": 9.0,
            "legend.fontsize": 7.5,
            "xtick.labelsize": 8.0,
            "ytick.labelsize": 8.0,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.6,
            "grid.alpha": 0.22,
            "grid.linewidth": 0.55,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _save(fig: plt.Figure, stem: str, config: dict, *, square_canvas: bool = False) -> None:
    fig.tight_layout(pad=0.8, w_pad=1.0, h_pad=0.9)
    metadata = {"Creator": "correlation-emergence-v1.0.0", "CreationDate": None, "ModDate": None}
    save_options = {} if square_canvas else {"bbox_inches": "tight"}
    fig.savefig(PROJECT_ROOT / "figures" / f"{stem}.pdf", metadata=metadata, **save_options)
    fig.savefig(
        PROJECT_ROOT / "figures" / f"{stem}.png",
        dpi=config["figures"]["dpi"],
        **save_options,
    )
    plt.close(fig)


def figure_1(config: dict, delta: np.ndarray) -> list[dict[str, object]]:
    ordinary = config["ordinary"]
    clock_rate = ordinary["clock_rate"]
    clock = np.asarray(ordinary_build_up(clock_rate * delta))
    ratios = ordinary["coupling_rate_ratios"]
    fig, axes = plt.subplots(1, len(ratios), figsize=(10.8, 3.55), sharex=True, sharey=True)
    rows: list[dict[str, object]] = []
    colors = {"clock": "#222222", "coupling": "#2166ac", "combined": "#b2182b"}

    for axis, ratio in zip(axes, ratios):
        response_rate = clock_rate * ratio
        coupling = np.asarray(ordinary_build_up(response_rate * delta))
        combined = np.asarray(combined_build_up(clock, coupling))
        curves = {"clock": clock, "coupling": coupling, "combined": combined}
        labels = {"clock": "clock", "coupling": "coupling", "combined": "combined product"}
        for mechanism, curve in curves.items():
            axis.plot(delta, curve, color=colors[mechanism], label=labels[mechanism])
            for scale, value in zip(delta, curve):
                rows.append(
                    {
                        "figure_id": "F1",
                        "aggregation_scale": scale,
                        "aggregation_unit": config["aggregation_grid"]["unit"],
                        "curve_type": "analytic",
                        "mechanism": mechanism,
                        "scenario": f"response_to_clock_rate_{ratio:g}",
                        "normalized_correlation": value,
                        "absolute_correlation": value * ordinary["rho_inf"],
                        "uncertainty": "",
                        "uncertainty_type": "not_applicable_deterministic",
                        "clock_rate": clock_rate,
                        "response_rate": response_rate,
                        "alpha_clock": 1.0,
                        "alpha_response": 1.0,
                        "parameter_profile": f"lambda=1;kappa={response_rate:g};rho_inf={ordinary['rho_inf']:g}",
                        "software_version": config["project"]["version"],
                    }
                )
        axis.set_xscale("log")
        axis.set_xlim(delta[0], delta[-1])
        axis.set_ylim(0.0, 1.02)
        axis.grid(True, which="both")
        axis.set_title(rf"$\kappa/\lambda_{{12}}={ratio:g}$")
        axis.set_xlabel(r"Aggregation scale $\lambda_{12}\Delta$")
    axes[0].set_ylabel(r"Normalised correlation $\rho_\Delta/\rho_\infty$")
    axes[0].legend(loc="lower right", frameon=False)
    fig.suptitle("Ordinary Epps components under separated clock and coupling timescales", y=1.02)
    _save(fig, FIGURE_NAMES["F1"], config)
    write_csv(PROJECT_ROOT / "outputs" / "figure-01-ordinary-epps-components-data-v1.csv", list(rows[0]), rows)
    overlay_fields = [
        "figure_id",
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
        "scenario",
        "clock_rate",
        "response_rate",
        "alpha_clock",
        "alpha_response",
    ]
    write_csv(PROJECT_ROOT / "outputs" / "epps-overlay-v1.csv", overlay_fields, rows)
    return rows


def figure_2(config: dict, delta: np.ndarray) -> list[dict[str, object]]:
    ordinary = config["ordinary"]
    clock_rate = ordinary["clock_rate"]
    ratios = ordinary["coupling_rate_ratios"]
    clock_sensitivity = np.asarray(rate_elasticity(clock_rate * delta))
    fig, axes = plt.subplots(1, len(ratios), figsize=(10.8, 3.55), sharex=True, sharey=True)
    rows: list[dict[str, object]] = []

    for axis, ratio in zip(axes, ratios):
        response_rate = clock_rate * ratio
        response_sensitivity = np.asarray(rate_elasticity(response_rate * delta))
        common_scale_sensitivity = clock_sensitivity + response_sensitivity
        series = (
            ("clock_rate", "clock partial", clock_sensitivity, "#222222", "-"),
            ("response_rate", "response partial", response_sensitivity, "#2166ac", "-"),
            ("common_rate_scale", "combined, both rates", common_scale_sensitivity, "#b2182b", "--"),
        )
        for parameter, label, values, color, linestyle in series:
            axis.plot(delta, values, color=color, linestyle=linestyle, label=label)
            for scale, value in zip(delta, values):
                rows.append(
                    {
                        "figure_id": "F2",
                        "aggregation_scale": scale,
                        "aggregation_unit": config["aggregation_grid"]["unit"],
                        "scenario": f"response_to_clock_rate_{ratio:g}",
                        "mechanism": "combined" if parameter == "common_rate_scale" else parameter.replace("_rate", ""),
                        "sensitivity_parameter": parameter,
                        "local_elasticity": value,
                        "clock_rate": clock_rate,
                        "response_rate": response_rate,
                        "software_version": config["project"]["version"],
                    }
                )
        axis.set_xscale("log")
        axis.set_xlim(delta[0], delta[-1])
        axis.set_ylim(0.0, 2.04)
        axis.grid(True, which="both")
        axis.set_title(rf"$\kappa/\lambda_{{12}}={ratio:g}$")
        axis.set_xlabel(r"Aggregation scale $\lambda_{12}\Delta$")
    axes[0].set_ylabel("Local log-elasticity")
    axes[0].legend(loc="upper right", frameon=False)
    fig.suptitle("Aggregation-scale sensitivity of ordinary Epps components", y=1.02)
    _save(fig, FIGURE_NAMES["F2"], config)
    write_csv(PROJECT_ROOT / "outputs" / "figure-02-ordinary-epps-sensitivity-data-v1.csv", list(rows[0]), rows)
    return rows


def figure_3(config: dict, delta: np.ndarray) -> list[dict[str, object]]:
    fractional = config["fractional"]
    order_pairs = [tuple(pair) for pair in fractional["order_pairs"]]
    kwargs = {
        "series_switch": fractional["series_switch"],
        "quadrature_order": fractional["quadrature_order_per_segment"],
        "quadrature_log_limit": fractional["quadrature_log_limit"],
    }
    rows: list[dict[str, object]] = []
    curves: dict[tuple[float, float], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for alpha_clock, alpha_response in order_pairs:
        clock = np.asarray(
            fractional_build_up(delta, alpha_clock, fractional["clock_characteristic_time"], **kwargs)
        )
        response = np.asarray(
            fractional_build_up(delta, alpha_response, fractional["response_characteristic_time"], **kwargs)
        )
        combined = np.asarray(combined_build_up(clock, response))
        curves[(alpha_clock, alpha_response)] = (clock, response, combined)
        for mechanism, values in zip(("clock", "coupling", "combined"), (clock, response, combined)):
            for scale, value in zip(delta, values):
                rows.append(
                    {
                        "figure_id": "F3",
                        "aggregation_scale": scale,
                        "aggregation_unit": config["aggregation_grid"]["unit"],
                        "curve_type": "analytic_fractional",
                        "mechanism": mechanism,
                        "alpha_clock": alpha_clock,
                        "alpha_response": alpha_response,
                        "alpha_sum": alpha_clock + alpha_response,
                        "clock_characteristic_time": fractional["clock_characteristic_time"],
                        "response_characteristic_time": fractional["response_characteristic_time"],
                        "normalized_correlation": value,
                        "software_version": config["project"]["version"],
                    }
                )

    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.55), sharex=True, sharey=True)
    palette = {1.0: "#222222", 0.8: "#2166ac", 0.6: "#b2182b"}
    seen_clock: set[float] = set()
    seen_response: set[float] = set()
    for pair, (clock, response, combined) in curves.items():
        alpha_clock, alpha_response = pair
        if alpha_clock not in seen_clock:
            axes[0].plot(delta, clock, color=palette[alpha_clock], label=rf"$\alpha_c={alpha_clock:g}$")
            seen_clock.add(alpha_clock)
        if alpha_response not in seen_response:
            axes[1].plot(delta, response, color=palette[alpha_response], label=rf"$\alpha_r={alpha_response:g}$")
            seen_response.add(alpha_response)
    pair_colors = ("#222222", "#2166ac", "#b2182b", "#7b3294")
    for color, (pair, (_, _, combined)) in zip(pair_colors, curves.items()):
        axes[2].plot(delta, combined, color=color, label=rf"$({pair[0]:g},{pair[1]:g})$")
    for axis, title in zip(axes, ("Clock component", "Response component", "Combined product")):
        axis.set_xscale("log")
        axis.set_xlim(delta[0], delta[-1])
        axis.set_ylim(0.0, 1.02)
        axis.grid(True, which="both")
        axis.set_title(title)
        axis.set_xlabel(r"Aggregation scale $\Delta/\tau_c$")
        axis.legend(loc="lower right", frameon=False)
    axes[0].set_ylabel(r"Normalised correlation $\rho_\Delta/\rho_\infty$")
    fig.suptitle("Fractional Epps curves and short-scale exponent sensitivity", y=1.02)
    _save(fig, FIGURE_NAMES["F3"], config)
    write_csv(PROJECT_ROOT / "outputs" / "figure-03-fractional-epps-sensitivity-data-v1.csv", list(rows[0]), rows)
    return rows


def figure_4(config: dict, delta: np.ndarray) -> list[dict[str, object]]:
    boundary = config["boundary"]
    clock = np.asarray(ordinary_build_up(boundary["clock_rate"] * delta))
    factors = boundary["perturbation_factors"]
    parameters = (
        ("coupling_strength", r"Coupling strength $\gamma_{jk}$"),
        ("source_amplitude", r"Source amplitude $a_j$"),
        ("source_width", r"Source width $\mu_j$"),
        ("front_slope_abs", r"Front slope $|L_j|$"),
    )
    fig, axes = plt.subplots(2, 2, figsize=(10.8, 6.8), sharex=True, sharey=True)
    axes_flat = axes.ravel()
    colors = {0.5: "#2166ac", 1.0: "#222222", 2.0: "#b2182b"}
    rows: list[dict[str, object]] = []

    for axis, (parameter, title) in zip(axes_flat, parameters):
        for factor in factors:
            values = {
                "coupling_strength": boundary["coupling_strength"],
                "source_amplitude": boundary["source_amplitude"],
                "source_width": boundary["source_width"],
                "front_slope_abs": boundary["front_slope_abs"],
            }
            values[parameter] *= factor
            response_rate = response_rate_total(books=boundary["books"], **values)
            coupling = np.asarray(ordinary_build_up(response_rate * delta))
            combined = np.asarray(combined_build_up(clock, coupling))
            axis.plot(delta, coupling, color=colors[factor], label=rf"$\times{factor:g}$ coupling")
            axis.plot(delta, combined, color=colors[factor], linestyle="--", label=rf"$\times{factor:g}$ combined")
            for mechanism, curve in (("coupling", coupling), ("combined", combined)):
                for scale, value in zip(delta, curve):
                    rows.append(
                        {
                            "figure_id": "F4",
                            "aggregation_scale": scale,
                            "aggregation_unit": config["aggregation_grid"]["unit"],
                            "mechanism": mechanism,
                            "varied_parameter": parameter,
                            "perturbation_factor": factor,
                            "clock_rate": boundary["clock_rate"],
                            "response_rate": response_rate,
                            "coupling_strength": values["coupling_strength"],
                            "source_amplitude": values["source_amplitude"],
                            "source_width": values["source_width"],
                            "front_slope_abs": values["front_slope_abs"],
                            "normalized_correlation": value,
                            "software_version": config["project"]["version"],
                        }
                    )
        axis.set_xscale("log")
        axis.set_xlim(delta[0], delta[-1])
        axis.set_ylim(0.0, 1.02)
        axis.grid(True, which="both")
        axis.set_title(title)
        axis.set_xlabel(r"Aggregation scale $\lambda_{12}\Delta$")
    axes[0, 0].set_ylabel(r"Normalised correlation")
    axes[1, 0].set_ylabel(r"Normalised correlation")
    handles, labels = axes_flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("Conditional propagation of reaction-boundary structure into the Epps curve", y=1.01)
    fig.subplots_adjust(bottom=0.14)
    _save(fig, FIGURE_NAMES["F4"], config)
    write_csv(PROJECT_ROOT / "outputs" / "figure-04-boundary-to-epps-data-v1.csv", list(rows[0]), rows)
    return rows


def figure_5(config: dict, delta: np.ndarray) -> list[dict[str, object]]:
    discrete = config["discrete_representation"]
    boundary = config["boundary"]
    analytic = analytic_half_line_moment(boundary["source_amplitude"], boundary["source_width"])
    scenario_specs = (
        ("centred_full", 0.0, discrete["full_domain_halfwidth"]),
        ("half_cell_shifted_full", 0.5, discrete["full_domain_halfwidth"]),
        ("centred_truncated", 0.0, discrete["truncated_domain_halfwidth"]),
    )
    moment_rows: list[dict[str, object]] = []
    ratios_by_scenario: dict[str, dict[float, list[float]]] = {
        name: {float(resolution): [] for resolution in discrete["selector_resolution_ratios"]}
        for name, _, _ in scenario_specs
    }
    all_effective_rates: list[float] = []

    for dx in discrete["lattice_spacings"]:
        for resolution in discrete["selector_resolution_ratios"]:
            epsilon = (resolution * dx) ** 2
            for scenario, offset_cells, halfwidth in scenario_specs:
                moment, realised_halfwidth, nodes = discrete_selected_moment(
                    boundary["source_amplitude"],
                    boundary["source_width"],
                    discrete["directed_spread"],
                    epsilon,
                    dx,
                    halfwidth,
                    selector_shift=offset_cells * dx,
                )
                moment_ratio = moment / analytic
                effective_rate = response_rate_total(
                    books=boundary["books"],
                    coupling_strength=boundary["coupling_strength"],
                    source_amplitude=boundary["source_amplitude"],
                    source_width=boundary["source_width"],
                    front_slope_abs=boundary["front_slope_abs"],
                    moment_ratio=moment_ratio,
                )
                ratios_by_scenario[scenario][float(resolution)].append(moment_ratio)
                all_effective_rates.append(effective_rate)
                moment_rows.append(
                    {
                        "figure_id": "F5",
                        "panel": "moment_ratio",
                        "scenario": scenario,
                        "selector_resolution_ratio_sqrt_epsilon_over_dx": resolution,
                        "epsilon": epsilon,
                        "lattice_spacing": dx,
                        "alignment_offset_cells": offset_cells,
                        "requested_domain_halfwidth": halfwidth,
                        "realised_domain_halfwidth": realised_halfwidth,
                        "grid_nodes": nodes,
                        "moment_ratio": moment_ratio,
                        "effective_response_rate": effective_rate,
                        "aggregation_scale": "",
                        "mechanism": "boundary_moment",
                        "normalized_correlation": "",
                        "lower_envelope": "",
                        "upper_envelope": "",
                        "software_version": config["project"]["version"],
                    }
                )

    clock = np.asarray(ordinary_build_up(boundary["clock_rate"] * delta))
    baseline_rate = response_rate_total(
        books=boundary["books"],
        coupling_strength=boundary["coupling_strength"],
        source_amplitude=boundary["source_amplitude"],
        source_width=boundary["source_width"],
        front_slope_abs=boundary["front_slope_abs"],
    )
    baseline_coupling = np.asarray(ordinary_build_up(baseline_rate * delta))
    baseline_combined = np.asarray(combined_build_up(clock, baseline_coupling))
    coupling_stack = np.vstack([np.asarray(ordinary_build_up(rate * delta)) for rate in all_effective_rates])
    combined_stack = coupling_stack * clock[None, :]
    envelope_rows: list[dict[str, object]] = []
    for mechanism, baseline, stack in (
        ("coupling", baseline_coupling, coupling_stack),
        ("combined", baseline_combined, combined_stack),
    ):
        lower = stack.min(axis=0)
        upper = stack.max(axis=0)
        for scale, base, low, high in zip(delta, baseline, lower, upper):
            envelope_rows.append(
                {
                    "figure_id": "F5",
                    "panel": "epps_envelope",
                    "scenario": "all_discrete_representation_profiles",
                    "selector_resolution_ratio_sqrt_epsilon_over_dx": "",
                    "epsilon": "",
                    "lattice_spacing": "",
                    "alignment_offset_cells": "",
                    "requested_domain_halfwidth": "",
                    "realised_domain_halfwidth": "",
                    "grid_nodes": "",
                    "moment_ratio": "",
                    "effective_response_rate": baseline_rate,
                    "aggregation_scale": scale,
                    "mechanism": mechanism,
                    "normalized_correlation": base,
                    "lower_envelope": low,
                    "upper_envelope": high,
                    "software_version": config["project"]["version"],
                }
            )

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.25))
    x_values = np.asarray(discrete["selector_resolution_ratios"], dtype=float)
    display = {
        "centred_full": ("centred, full domain", "#222222"),
        "half_cell_shifted_full": ("half-cell shifted", "#b2182b"),
        "centred_truncated": ("centred, truncated", "#2166ac"),
    }
    for scenario, (label, color) in display.items():
        lower = np.asarray([min(ratios_by_scenario[scenario][value]) for value in x_values])
        upper = np.asarray([max(ratios_by_scenario[scenario][value]) for value in x_values])
        centre = 0.5 * (lower + upper)
        axes[0].plot(x_values, centre, color=color, marker="o", markersize=3.2, label=label)
        axes[0].fill_between(x_values, lower, upper, color=color, alpha=0.14)
    axes[0].axhline(1.0, color="0.45", linewidth=0.8, linestyle=":")
    axes[0].set_xscale("log", base=2)
    axes[0].set_xlabel(r"Selector resolution $\sqrt{\varepsilon}/\Delta x$")
    axes[0].set_ylabel(r"Discrete/continuum moment $M_{\rm disc}/M^+$")
    axes[0].set_title("Boundary-moment representation")
    axes[0].grid(True, which="both")
    axes[0].legend(frameon=False, loc="lower right")

    coupling_lower = coupling_stack.min(axis=0)
    coupling_upper = coupling_stack.max(axis=0)
    combined_lower = combined_stack.min(axis=0)
    combined_upper = combined_stack.max(axis=0)
    axes[1].fill_between(delta, coupling_lower, coupling_upper, color="#2166ac", alpha=0.18, label="coupling envelope")
    axes[1].plot(delta, baseline_coupling, color="#2166ac", label="continuum coupling")
    axes[1].fill_between(delta, combined_lower, combined_upper, color="#b2182b", alpha=0.18, label="combined envelope")
    axes[1].plot(delta, baseline_combined, color="#b2182b", label="continuum combined")
    axes[1].set_xscale("log")
    axes[1].set_xlim(delta[0], delta[-1])
    axes[1].set_ylim(0.0, 1.02)
    axes[1].set_xlabel(r"Aggregation scale $\lambda_{12}\Delta$")
    axes[1].set_ylabel(r"Normalised correlation")
    axes[1].set_title("Induced Epps-curve envelope")
    axes[1].grid(True, which="both")
    axes[1].legend(frameon=False, loc="lower right")
    fig.suptitle("Finite-grid boundary representation and induced Epps-curve distortion", y=1.02)
    _save(fig, FIGURE_NAMES["F5"], config)
    rows = moment_rows + envelope_rows
    write_csv(PROJECT_ROOT / "outputs" / "figure-05-finite-grid-epps-data-v1.csv", list(rows[0]), rows)
    return rows


def figure_6(config: dict, _: np.ndarray) -> list[dict[str, object]]:
    """Plot a calendar-time Epps bridge with analytical memory diagnostics."""

    bridge = config["calendar_bridge"]
    clock_rate = float(bridge["clock_rate_per_second"])
    response_rate = clock_rate * float(bridge["response_to_clock_rate_ratio"])
    rho_inf = float(bridge["rho_inf"])
    delta_seconds = np.linspace(
        float(bridge["minimum_seconds"]),
        float(bridge["maximum_seconds"]),
        int(bridge["points"]),
    )
    lag_seconds = np.linspace(0.0, float(bridge["inset_maximum_lag_seconds"]), int(bridge["inset_points"]))

    clock = np.asarray(ordinary_build_up(clock_rate * delta_seconds))
    coupling = np.asarray(ordinary_build_up(response_rate * delta_seconds))
    combined = np.asarray(combined_build_up(clock, coupling))
    clock_memory = np.asarray(exponential_memory(lag_seconds, clock_rate))
    response_memory = np.asarray(exponential_memory(lag_seconds, response_rate))

    fig, axis = plt.subplots(figsize=(6.6, 6.6))
    axis.axhline(
        1.0,
        color="#666666",
        linestyle=":",
        linewidth=1.05,
        label="limiting correlation",
        zorder=1,
    )
    axis.plot(delta_seconds, clock, color="#222222", linewidth=1.35, label="clock component")
    axis.plot(delta_seconds, coupling, color="#2166ac", linewidth=1.35, label="coupling component")
    axis.plot(delta_seconds, combined, color="#b2182b", linewidth=1.9, label="combined curve")
    axis.set_xlim(delta_seconds[0], delta_seconds[-1])
    axis.set_ylim(0.0, 1.02)
    axis.set_xlabel(r"Calendar-time aggregation lag $\Delta t$ [s]", fontsize=18.0)
    axis.set_ylabel(r"Normalised correlation $\rho_{\Delta t}/\rho_\infty$", fontsize=18.0)
    axis.set_title("Calendar-time Epps curve", fontsize=18.0)
    axis.set_box_aspect(1)
    axis.grid(True)
    axis.legend(
        frameon=False,
        fontsize=15.0,
        loc="center right",
        bbox_to_anchor=(0.96, 0.62),
    )

    inset = axis.inset_axes([0.4967, 0.12, 0.4773, 0.387])
    inset.plot(lag_seconds, clock_memory, color="#222222", linewidth=1.15, label=r"$e^{-\lambda_{12}u}$")
    inset.plot(lag_seconds, response_memory, color="#2166ac", linewidth=1.15, label=r"$e^{-\kappa u}$")
    inset.set_xlim(lag_seconds[0], lag_seconds[-1])
    inset.set_ylim(0.0, 1.02)
    inset.set_xlabel(r"Lag $u$ [s]", fontsize=18.0, labelpad=4.0)
    inset.set_ylabel("Memory", fontsize=18.0, labelpad=4.0)
    inset.tick_params(axis="both", labelsize=8.0)
    inset.grid(True)
    inset.legend(frameon=False, fontsize=15.0, loc="upper right")

    _save(fig, FIGURE_NAMES["F6"], config, square_canvas=True)

    rows: list[dict[str, object]] = []
    common = {
        "figure_id": "F6",
        "clock_rate_per_second": clock_rate,
        "response_rate_per_second": response_rate,
        "clock_characteristic_time_seconds": 1.0 / clock_rate,
        "response_characteristic_time_seconds": 1.0 / response_rate,
        "rho_inf": rho_inf,
        "scenario": "calendar_reference_slow_response",
        "profile_status": bridge["status"],
        "software_version": config["project"]["version"],
    }
    for mechanism, values in (
        ("limiting_correlation", np.ones_like(delta_seconds)),
        ("clock", clock),
        ("coupling", coupling),
        ("combined", combined),
    ):
        for scale, value in zip(delta_seconds, values):
            rows.append(
                {
                    **common,
                    "panel": "calendar_epps_curve",
                    "abscissa": scale,
                    "abscissa_unit": "second",
                    "mechanism": mechanism,
                    "ordinate": value,
                    "ordinate_quantity": "normalized_correlation",
                    "absolute_correlation": rho_inf * value,
                }
            )
    for mechanism, values in (("clock_no_refresh_survival", clock_memory), ("coupling_relaxation_survival", response_memory)):
        for lag, value in zip(lag_seconds, values):
            rows.append(
                {
                    **common,
                    "panel": "memory_diagnostic",
                    "abscissa": lag,
                    "abscissa_unit": "second",
                    "mechanism": mechanism,
                    "ordinate": value,
                    "ordinate_quantity": "normalized_survival_or_memory",
                    "absolute_correlation": "",
                }
            )
    write_csv(PROJECT_ROOT / "outputs" / "figure-06-calendar-time-epps-memory-data-v1.csv", list(rows[0]), rows)
    return rows


def main() -> int:
    ensure_output_directories()
    _style()
    config = load_config()
    delta = _grid(config)
    generators = (figure_1, figure_2, figure_3, figure_4, figure_5, figure_6)
    for index, generator in enumerate(generators, start=1):
        rows = generator(config, delta)
        print(f"Figure {index}: generated with {len(rows)} machine-readable rows.")
    print("Six frozen scientific figures generated as PDF and PNG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
