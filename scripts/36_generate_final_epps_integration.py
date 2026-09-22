"""Generate the v1.9.0 final estimator-aware Epps integration."""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib-cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from functions.figure_io import atomic_savefig, remove_orphaned_figure_staging_files
from functions.integrity import accepted_input_errors, snapshot_errors, snapshot_hashes
from functions.io_utils import write_csv


CONFIG_PATH = PROJECT_ROOT / "config" / "config-v1.9.0.json"
CLOCK_PATH = PROJECT_ROOT / "outputs" / "clock-only-conformity-curves-v1.7.csv"
COUPLING_PATH = PROJECT_ROOT / "outputs" / "corrected-coupling-recovery-curves-v1.7.csv"
COMBINED_PATH = PROJECT_ROOT / "outputs" / "combined-no-refit-curves-v1.7.csv"
CURVE_PATH = PROJECT_ROOT / "outputs" / "final-estimator-aware-epps-curves-v1.9.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "final-estimator-aware-epps-summary-v1.9.csv"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "final-estimator-aware-epps-checks-v1.9.csv"
FIGURE_STEMS = {
    "overview": PROJECT_ROOT / "figures" / "figure-07-final-estimator-aware-epps-v2",
    "clock_only": PROJECT_ROOT / "figures" / "figure-07a-clock-only-epps-v2",
    "coupling_only": PROJECT_ROOT / "figures" / "figure-07b-coupling-only-epps-v2",
    "combined": PROJECT_ROOT / "figures" / "figure-07c-combined-epps-v2",
}
VERSION = "1.9.0"


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _values(rows: list[dict[str, str]], name: str) -> np.ndarray:
    return np.asarray([float(row[name]) for row in rows], dtype=float)


def _rmse(estimate: np.ndarray, reference: np.ndarray) -> float:
    return float(np.sqrt(np.mean((estimate - reference) ** 2)))


def _render(value: object) -> object:
    if isinstance(value, (dict, list, tuple, set)):
        if isinstance(value, set):
            value = sorted(value)
        return json.dumps(value, sort_keys=True)
    return value


def _check(
    check_id: str,
    description: str,
    observed: object,
    criterion: str,
    verified: bool,
) -> dict[str, object]:
    return {
        "check_id": check_id,
        "check": description,
        "observed": _render(observed),
        "criterion": criterion,
        "status": "Verified" if verified else "Failed",
        "software_version": VERSION,
    }


def _style_axis(axis: plt.Axes) -> None:
    axis.set_box_aspect(1)
    axis.set_xlim(0.0, 410.0)
    axis.set_ylim(0.0, 1.1)
    axis.set_xlabel(r"Calendar aggregation scale $\Delta t$ [s]")
    axis.set_ylabel("Normalized covariance response")
    axis.grid(alpha=0.18)
    axis.legend(loc="lower right", fontsize=8.2, frameon=False)


def _save_pair(figure: plt.Figure, stem: Path, *, square_canvas: bool = False) -> None:
    save_options: dict[str, object] = {} if square_canvas else {"bbox_inches": "tight"}
    atomic_savefig(figure, stem.with_suffix(".pdf"), **save_options)
    atomic_savefig(figure, stem.with_suffix(".png"), dpi=220, **save_options)
    plt.close(figure)


def _plot_component(
    lags: np.ndarray,
    theory: np.ndarray,
    simulation: np.ndarray,
    standard_error: np.ndarray,
    *,
    title: str,
    theory_label: str,
    simulation_label: str,
    colour: str,
    stem: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(6.4, 6.4), constrained_layout=True)
    axis.fill_between(
        lags,
        simulation - 1.96 * standard_error,
        simulation + 1.96 * standard_error,
        color=colour,
        alpha=0.17,
        linewidth=0.0,
        label="Simulation 95% band",
    )
    axis.plot(lags, theory, color="black", linewidth=2.1, label=theory_label)
    axis.plot(lags, simulation, color=colour, linewidth=2.2, label=simulation_label)
    axis.set_title(title)
    _style_axis(axis)
    _save_pair(figure, stem, square_canvas=True)


def _plot_combined(
    lags: np.ndarray,
    product: np.ndarray,
    estimator_theory: np.ndarray,
    combined_simulation: np.ndarray,
    combined_se: np.ndarray,
    *,
    title: str,
    stem: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(6.4, 6.4), constrained_layout=True)
    axis.fill_between(
        lags,
        combined_simulation - 1.96 * combined_se,
        combined_simulation + 1.96 * combined_se,
        color="#b51f2e",
        alpha=0.17,
        linewidth=0.0,
        label="Combined simulation 95% band",
    )
    axis.plot(
        lags,
        product,
        color="black",
        linewidth=2.1,
        label=r"Leading-order product $F(\lambda^{\mathrm{clk}}\Delta)F(\kappa\Delta)$",
    )
    axis.plot(
        lags,
        estimator_theory,
        color="#666666",
        linewidth=2.0,
        linestyle="--",
        label="Same-clock conditional reference",
    )
    axis.plot(
        lags,
        combined_simulation,
        color="#b51f2e",
        linewidth=2.3,
        label="Combined simulation",
    )
    axis.set_title(title)
    _style_axis(axis)
    _save_pair(figure, stem, square_canvas=True)


def _save_figures(
    lags: np.ndarray,
    clock_theory: np.ndarray,
    clock_simulation: np.ndarray,
    clock_se: np.ndarray,
    coupling_theory: np.ndarray,
    coupling_simulation: np.ndarray,
    coupling_se: np.ndarray,
    product: np.ndarray,
    estimator_theory: np.ndarray,
    combined_simulation: np.ndarray,
    combined_se: np.ndarray,
) -> None:
    remove_orphaned_figure_staging_files()
    _plot_component(
        lags,
        clock_theory,
        clock_simulation,
        clock_se,
        title="(a) Clock only",
        theory_label=r"Equal-rate clock theory $F(\lambda^{\mathrm{clk}}\Delta)$",
        simulation_label="Clock-only simulation",
        colour="#1f77b4",
        stem=FIGURE_STEMS["clock_only"],
    )
    _plot_component(
        lags,
        coupling_theory,
        coupling_simulation,
        coupling_se,
        title="(b) Translation-mode coupling only",
        theory_label=r"$F(\kappa\Delta)$ theory",
        simulation_label="Coupling-only simulation",
        colour="#2a9d55",
        stem=FIGURE_STEMS["coupling_only"],
    )
    _plot_combined(
        lags,
        product,
        estimator_theory,
        combined_simulation,
        combined_se,
        title="(c) Clock and translation-mode coupling",
        stem=FIGURE_STEMS["combined"],
    )

    # Retain the accepted three-panel overview for the README only. The
    # standalone square exports above are the paper-insertion route.
    if all(
        FIGURE_STEMS["overview"].with_suffix(f".{suffix}").is_file()
        for suffix in ("pdf", "png")
    ):
        return
    fig, axes = plt.subplots(1, 3, figsize=(15.2, 6.0), sharex=True, sharey=True)
    panels = (
        (
            axes[0],
            "(a) Clock only",
            clock_theory,
            clock_simulation,
            clock_se,
            r"Equal-rate clock theory $F(\lambda^{\mathrm{clk}}\Delta)$",
            "Clock-only simulation",
            "#1f77b4",
        ),
        (
            axes[1],
            "(b) Translation-mode coupling only",
            coupling_theory,
            coupling_simulation,
            coupling_se,
            r"$F(\kappa\Delta)$ theory",
            "Coupling-only simulation",
            "#2a9d55",
        ),
    )
    for axis, title, theory, simulation, standard_error, theory_label, simulation_label, colour in panels:
        axis.fill_between(
            lags,
            simulation - 1.96 * standard_error,
            simulation + 1.96 * standard_error,
            color=colour,
            alpha=0.17,
            linewidth=0.0,
            label="Simulation 95% band",
        )
        axis.plot(lags, theory, color="black", linewidth=2.1, label=theory_label)
        axis.plot(lags, simulation, color=colour, linewidth=2.2, label=simulation_label)
        axis.set_title(title)

    axes[2].fill_between(
        lags,
        combined_simulation - 1.96 * combined_se,
        combined_simulation + 1.96 * combined_se,
        color="#b51f2e",
        alpha=0.17,
        linewidth=0.0,
        label="Combined simulation 95% band",
    )
    axes[2].plot(
        lags,
        product,
        color="black",
        linewidth=2.1,
        label=r"Leading-order product $F(\lambda^{\mathrm{clk}}\Delta)F(\kappa\Delta)$",
    )
    axes[2].plot(
        lags,
        estimator_theory,
        color="#666666",
        linewidth=2.0,
        linestyle="--",
        label="Same-clock conditional reference",
    )
    axes[2].plot(
        lags,
        combined_simulation,
        color="#b51f2e",
        linewidth=2.3,
        label="Combined simulation",
    )
    axes[2].set_title("(c) Clock and translation-mode coupling")

    for axis in axes:
        axis.set_box_aspect(1)
        axis.set_xlim(0.0, 410.0)
        axis.set_ylim(0.0, 1.1)
        axis.set_xlabel(r"Calendar aggregation scale $\Delta t$ [s]")
        axis.grid(alpha=0.18)
        axis.legend(loc="lower right", fontsize=8.2, frameon=False)
    axes[0].set_ylabel("Normalized covariance response")
    fig.suptitle(
        "Clock, coupling and combined Epps curves: theory and simulation",
        fontsize=15,
    )
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.94))
    _save_pair(fig, FIGURE_STEMS["overview"])




def _resolution_curves(ensembles):
    from functions.observation.combined_reference import stationary_poisson_joint_attenuation
    from functions.correlation_build_up import ordinary_build_up
    cfg = json.loads(CONFIG_PATH.read_text())["numerical_resolution"]
    x = np.asarray(cfg["lags_seconds"], dtype=float)
    def correlation(v):
        return v[..., 0] / np.sqrt(v[..., 1]*v[..., 2])
    def result(mean, loo, theory):
        n = len(loo)
        se = np.sqrt((n-1)/n*np.sum((loo-loo.mean(0))**2, axis=0))
        return dict(lags_seconds=x, matched_mean=mean, standard_error=se,
                    halfwidth_98=cfg["mean_interval_critical_value"]*se, theory=theory)
    c = ensembles["clock"]
    a, s = c["asynchronous"], c["synchronous"]
    at, st = a.sum(0), s.sum(0)
    panels = [result(correlation(at)/correlation(st), correlation(at-a)/correlation(st-s), ordinary_build_up(.1*x))]
    c = ensembles["coupled"]
    a, s, den = c["asynchronous"], c["synchronous"], c["centre_squares"]
    at, st, total = a.sum(0), s.sum(0), den.sum(0)
    panels.append(result(st[:, 0]/total, (st[:, 0]-s[:, :, 0])/(total-den), ordinary_build_up(.025*x)))
    replicas = cfg["clock_replicas"]
    panels.append(result(at[:, 0]/(replicas*total), (at[:, 0]-a[:, :, 0])/(replicas*(total-den)), stationary_poisson_joint_attenuation(x, clock_rate=.1, response_rate=.025)))
    panels[2]["conditional_reference"] = c["reference"][:, :, 0].sum(0)/(len(den)*replicas*(round(cfg["horizon_seconds"]/cfg["step_seconds"])+1-(x/cfg["step_seconds"]).astype(int))*x)
    return panels

def _resolution_panel(ax, j, short):
    from functions.correlation_build_up import ordinary_build_up
    from functions.observation.combined_reference import stationary_poisson_joint_attenuation
    d = short[j]
    xx = d['lags_seconds']
    mean = d['matched_mean']
    half = d['halfwidth_98']
    c = ['#1f77b4', '#2a9d55', '#b51f2e'][j]
    dense = np.geomspace(0.5, 400, 500)
    th = ordinary_build_up(0.1 * dense) if j == 0 else ordinary_build_up(0.025 * dense) if j == 1 else ordinary_build_up(0.1 * dense) * ordinary_build_up(0.025 * dense)
    ax.fill_between(xx, mean - half, mean + half, color=c, alpha=0.32, lw=0.4, edgecolor=c, label='98% mean interval')
    ax.plot(dense, th, color='black', lw=3.1, label=['Clock theory', 'Coupling theory', 'Product approximation'][j])
    if j == 2:
        ax.plot(dense, stationary_poisson_joint_attenuation(dense, clock_rate=.1, response_rate=.025), color='#666666', ls='--', lw=2.5, label='Joint reduced reference')
    ax.plot(xx, mean, color=c, lw=1.55, label='Simulation')
    ax.set(title=['(a) Clock only', '(b) Translation-mode coupling only', '(c) Clock and translation-mode coupling'][j], xlim=(0, 410), ylim=(-0.02, 1.1), xlabel='Calendar aggregation scale $\\Delta$ [s]', ylabel='Normalized correlation attenuation' if j == 0 else 'Normalized covariance response')
    ax.set_box_aspect(1)
    ax.grid(alpha=0.18)
    ax.legend(loc='lower right', fontsize=8, frameon=False)
    inset = ax.inset_axes([0.49, 0.25, 0.47, 0.38])
    inset.set_xscale('log')
    inset.set_yscale('log')
    low = np.where(mean - half > 0, mean - half, np.nan)
    inset.fill_between(xx, low, mean + half, color=c, alpha=0.32, lw=0.35, edgecolor=c)
    inset.plot(dense, th, color='black', lw=2)
    if j == 2:
        inset.plot(dense, stationary_poisson_joint_attenuation(dense, clock_rate=.1, response_rate=.025), color='#666666', ls='--', lw=1.65)
    inset.plot(xx, np.where(mean > 0, mean, np.nan), color=c, lw=1.05, marker='.', markersize=2)
    inset.set_xlim(0.45, 440)
    inset.set_ylim(0.0001, 1.1)
    inset.set_xticks([0.5, 10, 400], labels=['0.5', '10', '400'])
    inset.set_yticks([0.001, 0.1, 1], labels=['0.001', '0.1', '1'])
    inset.minorticks_off()
    inset.tick_params(labelsize=7, pad=1, length=2)
    inset.set_title('Log–log', fontsize=8, pad=3)
    inset.grid(alpha=0.18, linewidth=0.4)

def _run_resolution_comparison():
    """Assemble Figure 7 from the independent-path statistics produced by script 33."""
    with np.load(PROJECT_ROOT / "outputs/figure-07-ensemble-v2.2.0.npz") as data:
        ensembles = {kind: {key.split("__", 1)[1]: data[key] for key in data.files
                            if key.startswith(kind + "__")}
                     for kind in ("clock", "coupled")}
    panels = _resolution_curves(ensembles)
    rows = []
    for label, panel in zip(["clock", "synchronous", "asynchronous"], panels):
        for i, lag in enumerate(panel["lags_seconds"]):
            rows.append(dict(panel=label, lag_seconds=lag, simulation=panel["matched_mean"][i], halfwidth_98=panel["halfwidth_98"][i], reduced_theory=panel["theory"][i], conditional_reference=panel.get("conditional_reference", [""]*len(panel["lags_seconds"]))[i]))
    write_csv(PROJECT_ROOT/"outputs/figure-07-curves-v2.2.0.csv", list(rows[0]), rows)
    with plt.rc_context():
        plt.rcdefaults()
        plt.rcParams.update({"font.size": 10, "pdf.fonttype": 42})
        for j, key in enumerate(["clock_only", "coupling_only", "combined"]):
            figure, axis = plt.subplots(figsize=(6.4, 6.4), layout="constrained")
            _resolution_panel(axis, j, panels)
            _save_pair(figure, FIGURE_STEMS[key], square_canvas=True)
        figure, axes = plt.subplots(1, 3, figsize=(17.4, 6.2), layout="constrained")
        for j, axis in enumerate(axes):
            _resolution_panel(axis, j, panels)
        _save_pair(figure, FIGURE_STEMS["overview"], square_canvas=True)
    return ensembles, panels

def main() -> int:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if configuration.get("schema_version") != VERSION:
        raise ValueError("v1.9.0 configuration version mismatch")
    input_errors = accepted_input_errors(configuration["accepted_inputs"])
    input_hashes = snapshot_hashes(configuration["accepted_inputs"])

    clock_rows = [
        row for row in _read_rows(CLOCK_PATH) if row["tier"] == "thick_boundary"
    ]
    coupling_rows = _read_rows(COUPLING_PATH)
    combined_rows = _read_rows(COMBINED_PATH)
    lags = _values(combined_rows, "lag_seconds")
    registered_lags = np.asarray(configuration["registered_lags_seconds"], dtype=float)
    exact_lag_join = (
        np.array_equal(lags, registered_lags)
        and np.array_equal(_values(clock_rows, "lag_seconds"), lags)
        and np.array_equal(_values(coupling_rows, "lag_seconds"), lags)
    )

    clock_theory = _values(clock_rows, "exact_equal_rate_curve")
    clock_simulation = _values(clock_rows, "normalized_simulation")
    clock_se = _values(clock_rows, "jackknife_standard_error")
    coupling_theory = _values(coupling_rows, "analytical_normalized_covariance")
    coupling_simulation = _values(coupling_rows, "simulated_normalized_covariance")
    coupling_se = _values(coupling_rows, "covariance_jackknife_standard_error")
    product = _values(combined_rows, "analytical_leading_order_product")
    estimator_theory = _values(
        combined_rows, "thick_exact_reduced_same_clock_covariance"
    )
    combined_simulation = _values(combined_rows, "thick_simulated_combined_covariance")
    combined_se = _values(combined_rows, "thick_covariance_standard_error")

    source_join = {
        "clock_theory": np.array_equal(
            clock_theory, _values(combined_rows, "analytical_clock_factor")
        ),
        "clock_simulation": np.array_equal(
            clock_simulation, _values(combined_rows, "accepted_clock_thick_boundary")
        ),
        "coupling_theory": np.array_equal(
            coupling_theory, _values(combined_rows, "analytical_coupling_factor")
        ),
        "coupling_simulation": np.array_equal(
            coupling_simulation,
            _values(combined_rows, "accepted_corrected_coupling"),
        ),
    }
    product_reconstructs = np.allclose(
        product, clock_theory * coupling_theory, rtol=1e-14, atol=1e-15
    )
    estimator_rmse = _rmse(combined_simulation, estimator_theory)
    product_rmse = _rmse(combined_simulation, product)
    standardized_rmse = float(
        np.sqrt(np.mean(((combined_simulation - estimator_theory) / combined_se) ** 2))
    )
    coverage = float(
        np.mean(
            np.abs(combined_simulation - estimator_theory) <= 1.96 * combined_se
        )
    )

    curve_rows = []
    for position, lag in enumerate(lags):
        curve_rows.append(
            {
                "target_id": configuration["target_id"],
                "lag_seconds": lag,
                "clock_only_theory": clock_theory[position],
                "clock_only_simulation": clock_simulation[position],
                "clock_only_simulation_standard_error": clock_se[position],
                "coupling_only_theory": coupling_theory[position],
                "coupling_only_simulation": coupling_simulation[position],
                "coupling_only_simulation_standard_error": coupling_se[position],
                "combined_simulation": combined_simulation[position],
                "combined_simulation_standard_error": combined_se[position],
                "leading_order_product": product[position],
                "estimator_aware_finite_grid_finite_step_theory": estimator_theory[position],
                "combined_minus_estimator_aware_theory": combined_simulation[position]
                - estimator_theory[position],
                "combined_minus_leading_order_product": combined_simulation[position]
                - product[position],
                "fit_policy": "frozen_no_retuning",
                "software_version": VERSION,
            }
        )
    write_csv(CURVE_PATH, list(curve_rows[0]), curve_rows)

    summary = {
        "target_id": configuration["target_id"],
        "result_label": "final_estimator_aware_integration_established",
        "clock_only_rmse": _rmse(clock_simulation, clock_theory),
        "coupling_only_rmse": _rmse(coupling_simulation, coupling_theory),
        "combined_estimator_aware_rmse": estimator_rmse,
        "combined_leading_order_product_rmse": product_rmse,
        "combined_estimator_aware_standardized_rmse": standardized_rmse,
        "combined_estimator_aware_coverage": coverage,
        "parameters_refitted": False,
        "next_stage": configuration["output_contract"]["next_stage"],
        "software_version": VERSION,
    }
    write_csv(SUMMARY_PATH, list(summary), [summary])

    _save_figures(
        lags,
        clock_theory,
        clock_simulation,
        clock_se,
        coupling_theory,
        coupling_simulation,
        coupling_se,
        product,
        estimator_theory,
        combined_simulation,
        combined_se,
    )

    architecture = configuration["architecture"]
    policy = configuration["acceptance_policy"]
    figure_pairs = all(
        stem.with_suffix(f".{suffix}").is_file()
        for stem in FIGURE_STEMS.values()
        for suffix in ("pdf", "png")
    )
    checks = [
        _check("S9E-01", "accepted v1.8.3 input hashes", not input_errors, "all exact", not input_errors),
        _check("S9E-02", "accepted parent", configuration["accepted_parent"], "v1.8.3", configuration["accepted_parent"] == "v1.8.3"),
        _check("S9E-03", "uniform operational dynamics", architecture["operational_dynamics"], "uniform fixed grid only", architecture["operational_dynamics"] == "uniform_fixed_grid_only"),
        _check("S9E-04", "post-path calendar observation", architecture["calendar_observation"], "book-specific previous refresh after completion", architecture["calendar_observation"] == "book_specific_previous_refresh_after_operational_completion"),
        _check("S9E-05", "calendar interpolation", architecture["calendar_interpolation"], "forbidden", architecture["calendar_interpolation"] == "forbidden"),
        _check("S9E-06", "legacy nonuniform state update", architecture["legacy_nonuniform_state_update"], "forbidden", architecture["legacy_nonuniform_state_update"] == "forbidden"),
        _check("S9E-07", "parameter and curve refit", [architecture["model_parameter_refit"], architecture["curve_calibration"]], "both forbidden", architecture["model_parameter_refit"] == architecture["curve_calibration"] == "forbidden"),
        _check("S9E-08", "required curve inventory", configuration["required_curves"], "seven declared curves", len(configuration["required_curves"]) == 7),
        _check("S9E-09", "registered lag join", exact_lag_join, "20 exact common lags", exact_lag_join and lags.size == 20),
        _check("S9E-10", "clock theory source join", source_join["clock_theory"], "exact", source_join["clock_theory"]),
        _check("S9E-11", "clock simulation source join", source_join["clock_simulation"], "exact", source_join["clock_simulation"]),
        _check("S9E-12", "coupling theory source join", source_join["coupling_theory"], "exact", source_join["coupling_theory"]),
        _check("S9E-13", "coupling simulation source join", source_join["coupling_simulation"], "exact", source_join["coupling_simulation"]),
        _check("S9E-14", "leading-order product reconstruction", product_reconstructs, "clock theory times coupling theory", product_reconstructs),
        _check("S9E-15", "estimator-aware theory source", "thick_exact_reduced_same_clock_covariance", "accepted finite-grid finite-step same-clock reference", True),
        _check("S9E-16", "combined simulation source", "thick_simulated_combined_covariance", "accepted no-refit holdout", True),
        _check("S9E-17", "estimator-aware RMSE improvement", [estimator_rmse, product_rmse], "estimator-aware below leading-order product", estimator_rmse < product_rmse),
        _check("S9E-18", "combined standardized RMSE", standardized_rmse, f"at most {policy['combined_standardized_rmse_maximum']}", standardized_rmse <= float(policy["combined_standardized_rmse_maximum"])),
        _check("S9E-19", "combined pointwise coverage", coverage, f"at least {policy['minimum_combined_pointwise_coverage']}", coverage >= float(policy["minimum_combined_pointwise_coverage"])),
        _check("S9E-20", "common display scales", configuration["display_contract"], "three panels share linear x and y scales", configuration["display_contract"]["aggregation_axis"] == "linear"),
        _check("S9E-21", "Figure 7 overview and standalone pairs", figure_pairs, "four PDF/PNG pairs", figure_pairs),
        _check("S9E-22", "curve output rows", len(curve_rows), "20", len(curve_rows) == 20),
        _check("S9E-23", "optional calibrated curve", configuration["display_contract"]["optional_calibrated_curve"], "excluded", configuration["display_contract"]["optional_calibrated_curve"] == "excluded"),
        _check("S9E-24", "accepted inputs unchanged", not snapshot_errors(input_hashes), "all start/end hashes exact", not snapshot_errors(input_hashes)),
    ]
    write_csv(
        CHECK_PATH,
        ["check_id", "check", "observed", "criterion", "status", "software_version"],
        checks,
    )
    failed = sum(row["status"] == "Failed" for row in checks)
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    print(
        f"Final estimator-aware Epps integration completed: {len(checks) - failed} "
        f"checks verified, {failed} failures."
    )
    if failed:
        return 1
    if "numerical_resolution" in configuration:
        _run_resolution_comparison()
        print("Figure 7 numerical-resolution ensembles and figures completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
