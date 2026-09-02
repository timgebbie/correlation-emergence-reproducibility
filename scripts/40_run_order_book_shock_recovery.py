"""Generate and verify the v2.1.0 fixed-time order-book shock recovery."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
import uuid

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib-cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

from functions.events import (
    EVENT_MARKET_ORDER,
    OrderEvent,
    fixed_time_order_book_shock_recovery,
)
from functions.figure_io import (
    atomic_savefig,
    remove_orphaned_figure_staging_files,
    sync_completed_file,
)
from functions.integrity import accepted_input_errors
from functions.io_utils import (
    OUTPUT_STAGING_DIRECTORY,
    remove_orphaned_output_staging_files,
    write_csv,
)
from functions.operational import (
    OperationalSolverSpec,
    OperationalSource,
    TranslationModeCoupling,
    apply_spatial_boundary,
    extract_reaction_boundary,
    operational_sibuya_kernel,
    operational_source_density,
    stationary_density,
)


VERSION = "2.1.0"
CONFIG_PATH = PROJECT_ROOT / "config" / "config-v2.1.0.json"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "figure-12-order-book-shock-checks-v2.1.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "figure-12-order-book-shock-summary-v2.1.csv"
ARCHIVE_PATH = PROJECT_ROOT / "outputs" / "figure-12-order-book-shock-recovery-v2.1.npz"
FIGURE_STEM = PROJECT_ROOT / "figures" / "figure-12-order-book-shock-recovery-v2"


def _configuration() -> dict[str, object]:
    result = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if result.get("schema_version") != VERSION:
        raise ValueError("Figure 12 configuration version mismatch")
    return result


def _model(configuration: dict[str, object]):
    model = configuration["model"]
    grid = np.linspace(
        float(model["grid_lower"]),
        float(model["grid_upper"]),
        int(model["grid_points"]),
    )
    delta_x = float(grid[1] - grid[0])
    diffusion = tuple(float(value) for value in model["diffusion"])
    transport = float(model["transport_probability"])
    lattice_delta_u = transport * delta_x**2 / (2.0 * diffusion[0])
    delta_u = float(model["operational_step_model_units"])
    if not np.isclose(lattice_delta_u, delta_u):
        raise ValueError("declared operational step does not match the fixed lattice")
    sources = tuple(
        OperationalSource(
            float(model["source_lambda"][book]),
            float(model["source_mu"][book]),
        )
        for book in range(2)
    )
    cancellation = tuple(float(value) for value in model["cancellation_rates"])
    initial = np.stack(
        [
            apply_spatial_boundary(
                stationary_density(
                    grid,
                    np.asarray(operational_source_density(grid, 0.0, sources[book])),
                    diffusion=diffusion[book],
                    cancellation_rate=cancellation[book],
                    boundary_condition="dirichlet_zero",
                )
            )
            for book in range(2)
        ]
    )
    kernels = tuple(
        operational_sibuya_kernel(
            float(model["operational_orders"][book]),
            int(model["kernel_terms"][book]),
        )
        for book in range(2)
    )
    specification = OperationalSolverSpec(
        delta_u=delta_u,
        transport_probability=transport,
        cancellation_rates=cancellation,
        minimum_abs_boundary_slope=float(model["minimum_abs_boundary_slope"]),
    )
    rates = model["ordered_coupling_rates_per_model_time_unit"]
    couplings = (
        (None, TranslationModeCoupling(float(rates[0]))),
        (TranslationModeCoupling(float(rates[1])), None),
    )
    return grid, sources, initial, kernels, specification, couplings


def _save_archive(**arrays: np.ndarray) -> None:
    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_STAGING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_STAGING_DIRECTORY / (
        f"{ARCHIVE_PATH.stem}-{uuid.uuid4().hex}.tmp{ARCHIVE_PATH.suffix}"
    )
    try:
        with temporary.open("wb") as handle:
            np.savez_compressed(handle, **arrays)
        sync_completed_file(temporary)
        os.replace(temporary, ARCHIVE_PATH)
    finally:
        temporary.unlink(missing_ok=True)
        try:
            OUTPUT_STAGING_DIRECTORY.rmdir()
        except OSError:
            pass


def _check(
    identifier: str,
    claim: str,
    observed: object,
    criterion: str,
    passed: bool,
) -> dict[str, object]:
    if isinstance(observed, np.ndarray):
        observed = observed.tolist()
    return {
        "check_id": identifier,
        "claim": claim,
        "observed": observed,
        "criterion": criterion,
        "status": "Verified" if passed else "Failed",
        "software_version": VERSION,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _plot(result, configuration: dict[str, object]) -> None:
    figure_config = configuration["figure"]
    displayed = int(configuration["experiment"]["displayed_book"])
    density_colour = figure_config["density_colour"]
    arrival_colour = figure_config["arrival_colour"]
    removal_colour = figure_config["removal_colour"]
    impulse_colour = figure_config["impulse_colour"]
    grid = result.price_grid
    delta_x = float(grid[1] - grid[0])
    boundary_window = np.asarray(
        figure_config["boundary_window_relative_to_pre_event"], dtype=float
    )
    if boundary_window.shape != (2,) or boundary_window[0] >= boundary_window[1]:
        raise ValueError("Figure 12 boundary window must contain two increasing values")
    boundary_centre = float(result.prices[0, displayed])
    view_lower = boundary_centre + float(boundary_window[0])
    view_upper = boundary_centre + float(boundary_window[1])
    zoom_mask = (grid >= view_lower) & (grid <= view_upper)
    if np.count_nonzero(zoom_mask) < 5:
        raise ValueError("Figure 12 boundary window must contain at least five grid cells")

    fig, axes = plt.subplots(3, 3, figsize=tuple(figure_config["canvas_inches"]))
    panel_labels = tuple("abcdefghi")
    titles = ("event $0^{-}$", "event $0^{+}$") + tuple(
        f"{value:g} s" for value in result.snapshot_lag_seconds[2:]
    )
    for panel, (axis, title) in enumerate(zip(axes.flat, titles)):
        density = result.densities[panel, displayed]
        arrivals = result.arrival_contributions[panel, displayed]
        removals = result.cancellation_contributions[panel, displayed]
        impulse = result.impulse_contributions[panel, displayed]
        axis.plot(
            grid,
            density,
            color=density_colour,
            lw=1.35,
            marker=".",
            markersize=2.2,
            markevery=4,
            label=r"$\varphi_1$",
        )
        axis.plot(
            grid,
            arrivals,
            color=arrival_colour,
            lw=1.0,
            marker=".",
            markersize=2.0,
            markevery=4,
            zorder=4,
            label="Arrivals",
        )
        axis.plot(
            grid,
            removals,
            color=removal_colour,
            lw=1.0,
            marker=".",
            markersize=2.0,
            markevery=4,
            zorder=3,
            label="Removals",
        )
        axis.plot(
            grid,
            impulse,
            color=impulse_colour,
            lw=1.0,
            marker=".",
            markersize=2.0,
            markevery=4,
            zorder=2,
            label="Market order",
        )
        marker_label = r"$p_1$" if result.price_is_registered[panel, displayed] else r"$p_1^{-}$"
        axis.scatter(
            [result.prices[panel, displayed]],
            [0.0],
            s=31,
            color=density_colour,
            edgecolor="black",
            linewidth=0.7,
            zorder=5,
            label=marker_label,
        )

        if not bool(result.price_is_registered[panel, displayed]):
            near_zero = np.flatnonzero(
                np.isclose(density[1:-1], 0.0, rtol=0.0, atol=1e-14)
            ) + 1
            runs = np.split(near_zero, np.flatnonzero(np.diff(near_zero) > 1) + 1)
            cleared_runs = [run for run in runs if run.size >= 2]
            if cleared_runs:
                cleared = max(cleared_runs, key=lambda run: run.size)
                axis.axvspan(
                    float(grid[cleared[0]] - 0.5 * delta_x),
                    float(grid[cleared[-1]] + 0.5 * delta_x),
                    color=impulse_colour,
                    alpha=0.16,
                    linewidth=0.0,
                    zorder=0,
                )
                axis.text(
                    float(np.mean(grid[cleared])),
                    0.06,
                    "cleared interval",
                    color="#7A3E87",
                    fontsize=6.5,
                    ha="center",
                    va="bottom",
                )

        values = np.concatenate(
            (
                density[zoom_mask],
                arrivals[zoom_mask],
                removals[zoom_mask],
                impulse[zoom_mask],
                np.asarray([0.0]),
            )
        )
        lower = float(np.min(values))
        upper = float(np.max(values))
        span = max(upper - lower, 1e-6)
        axis.set_ylim(lower - 0.10 * span, upper + 0.10 * span)
        axis.set_xlim(view_lower, view_upper)
        axis.axhline(0.0, color="black", lw=0.45, alpha=0.55)
        axis.grid(True, color="#D9D9D9", linewidth=0.5, alpha=0.65)
        axis.set_title(title, fontsize=10)
        axis.set_xlabel("Boundary-region log-price $x$", fontsize=9)
        axis.set_ylabel("Density contribution", fontsize=9)
        axis.tick_params(labelsize=8)
        axis.set_box_aspect(1)
        axis.text(
            0.02,
            0.98,
            f"({panel_labels[panel]})",
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontsize=10,
        )
        price_prefix = r"$p_1$" if result.price_is_registered[panel, displayed] else r"$p_1^{-}$"
        axis.text(
            0.98,
            0.04,
            f"{price_prefix} = {result.prices[panel, displayed]:.3f}\n"
            + rf"$\Delta x$ = {delta_x:.1f}",
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            fontsize=8,
            bbox={
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.82,
                "pad": 1.5,
            },
        )
        axis.legend(
            loc="lower left",
            fontsize=6.8,
            frameon=True,
            fancybox=False,
            framealpha=0.95,
            borderpad=0.35,
            handlelength=1.6,
            labelspacing=0.25,
        )

        if bool(figure_config["full_profile_inset"]):
            context = axis.inset_axes([0.64, 0.70, 0.33, 0.24])
            context.plot(grid, density, color=density_colour, lw=0.8)
            context.axhline(0.0, color="black", lw=0.3, alpha=0.5)
            context.axvspan(
                view_lower,
                view_upper,
                color="#BDBDBD",
                alpha=0.25,
                linewidth=0.0,
            )
            context.axvline(
                float(result.prices[panel, displayed]),
                color=density_colour,
                lw=0.6,
                alpha=0.9,
            )
            context.set_xlim(float(grid[0]), float(grid[-1]))
            context.set_ylim(float(np.min(density)) * 1.08, float(np.max(density)) * 1.08)
            context.set_xticks([float(grid[0]), 0.0, float(grid[-1])])
            context.set_yticks([])
            context.tick_params(axis="x", labelsize=5.5, length=2)
            context.set_title("full profile", fontsize=6, pad=1.5)
            context.grid(False)

    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.055, top=0.975, wspace=0.28, hspace=0.30)
    atomic_savefig(fig, FIGURE_STEM.with_suffix(".pdf"), facecolor="white")
    atomic_savefig(
        fig,
        FIGURE_STEM.with_suffix(".png"),
        dpi=int(figure_config["png_dpi"]),
        facecolor="white",
    )
    plt.close(fig)


def main() -> int:
    remove_orphaned_figure_staging_files()
    remove_orphaned_output_staging_files()
    configuration = _configuration()
    grid, sources, initial, kernels, specification, couplings = _model(configuration)
    experiment = configuration["experiment"]
    event = OrderEvent(
        event_id="figure-12-book-1-buy",
        event_type=EVENT_MARKET_ORDER,
        book_index=int(experiment["event_book"]),
        operational_step=int(experiment["event_operational_step"]),
        side=int(experiment["event_side"]),
        quantity=float(experiment["event_quantity"]),
    )
    result = fixed_time_order_book_shock_recovery(
        grid,
        initial,
        (0.0, 0.0),
        sources,
        couplings,
        kernels,
        specification,
        event,
        pre_event_steps=int(experiment["pre_event_steps"]),
        evolved_snapshot_lag_steps=experiment["evolved_snapshot_lag_steps"],
        seconds_per_model_time_unit=float(
            configuration["model"]["seconds_per_model_time_unit"]
        ),
    )

    _save_archive(
        price_grid=result.price_grid,
        snapshot_lag_steps=result.snapshot_lag_steps,
        snapshot_lag_seconds=result.snapshot_lag_seconds,
        snapshot_kinds=result.snapshot_kinds,
        densities=result.densities,
        prices=result.prices,
        price_is_registered=result.price_is_registered,
        contribution_price_inputs=result.contribution_price_inputs,
        arrival_contributions=result.arrival_contributions,
        cancellation_contributions=result.cancellation_contributions,
        impulse_contributions=result.impulse_contributions,
        coupling_contributions=result.coupling_contributions,
        history_contributions=result.history_contributions,
        boundary_corrections=result.boundary_corrections,
        ledger_errors=result.ledger_errors,
        control_densities=result.control_densities,
        control_prices=result.control_prices,
        affected_grid_indices=np.asarray(result.event_application.affected_grid_indices),
        execution_log_price=np.asarray([result.event_application.execution_log_price]),
        event_filled_quantity=np.asarray([result.event_application.filled_quantity]),
        event_density_delta=result.event_application.density_delta,
    )
    _plot(result, configuration)

    displayed = int(experiment["displayed_book"])
    dx = float(grid[1] - grid[0])
    expected_lags = np.asarray([0.0, 0.0, 0.5, 2.0, 5.0, 10.0, 20.0, 40.0, 80.0])
    source_errors = []
    for panel in range(9):
        expected = specification.delta_u * np.asarray(
            operational_source_density(
                grid,
                result.contribution_price_inputs[panel, displayed],
                sources[displayed],
            )
        )
        source_errors.append(
            float(np.max(np.abs(expected - result.arrival_contributions[panel, displayed])))
        )
    source_error = max(source_errors)
    event_integral = dx * float(np.sum(np.abs(result.event_application.density_delta)))
    event_support = grid[np.asarray(result.event_application.affected_grid_indices, dtype=int)]
    zero_interval_cells = int(
        np.sum(
            np.isclose(
                result.densities[1, displayed, 1:-1],
                0.0,
                rtol=0.0,
                atol=1e-14,
            )
        )
    )
    control_state_error = float(
        np.max(np.abs(result.control_densities - result.control_densities[0]))
    )
    late_own_displacement = float(result.prices[-1, displayed] - result.control_prices[-1, displayed])
    initial_own_response = float(result.prices[2, displayed] - result.control_prices[2, displayed])
    maximum_ledger_error = float(np.max(result.ledger_errors[2:]))
    maximum_cancellation = float(np.max(np.abs(result.cancellation_contributions)))
    maximum_book_two_impulse = float(np.max(np.abs(result.impulse_contributions[:, 1])))
    maximum_late_coupling = float(np.max(np.abs(result.coupling_contributions[3:])))
    registered_evolved = bool(np.all(result.price_is_registered[2:]))
    accepted_records = [
        record
        for record in configuration["accepted_inputs"]
        if record.get("role") != "doi_bearing_public_readme"
    ]
    accepted_errors = accepted_input_errors(accepted_records)

    checks = [
        _check("F12-01", "accepted inputs", len(accepted_errors), "zero errors", not accepted_errors),
        _check("F12-02", "fixed uniform grid", [grid[0], grid[-1], grid.size, dx], "[-10,10], 201 points, dx=0.1", grid.size == 201 and np.isclose(dx, 0.1)),
        _check("F12-03", "fixed operational step", specification.delta_u, "0.005 model-time units", np.isclose(specification.delta_u, 0.005)),
        _check("F12-04", "nine snapshot states", result.densities.shape, "(9,2,201)", result.densities.shape == (9, 2, 201)),
        _check("F12-05", "registered snapshot lags", result.snapshot_lag_seconds, expected_lags.tolist(), np.array_equal(result.snapshot_lag_seconds, expected_lags)),
        _check("F12-06", "event step", result.event_state_index, "301", result.event_state_index == 301),
        _check("F12-07", "full market-order fill", result.event_application.filled_quantity, experiment["event_quantity"], np.isclose(result.event_application.filled_quantity, float(experiment["event_quantity"]), rtol=0.0, atol=1e-14)),
        _check("F12-08", "event-density integral", event_integral, experiment["event_quantity"], np.isclose(event_integral, float(experiment["event_quantity"]), rtol=0.0, atol=1e-14)),
        _check("F12-09", "buy event uses ask-side support", event_support.tolist(), "all x>p^-", bool(np.all(event_support > result.prices[0, displayed]))),
        _check("F12-10", "event delta has buy sign", float(np.min(result.event_application.density_delta)), ">=0", bool(np.min(result.event_application.density_delta) >= 0.0)),
        _check("F12-11", "event affects only book 1", maximum_book_two_impulse, "0", maximum_book_two_impulse == 0.0),
        _check("F12-12", "execution proxy on aggressor side", result.event_application.execution_log_price, ">p^-", float(result.event_application.execution_log_price) > result.prices[0, displayed]),
        _check("F12-13", "pre-event stationary identity", result.pre_event_identity_error, "<=2e-12", result.pre_event_identity_error <= 2e-12),
        _check("F12-14", "matched control remains stationary", control_state_error, "<=2e-12", control_state_error <= 2e-12),
        _check("F12-15", "corrected source contribution", source_error, "<=2e-15", source_error <= 2e-15),
        _check("F12-16", "zero-cancellation contribution", maximum_cancellation, "exactly 0", maximum_cancellation == 0.0),
        _check("F12-17", "event impulse appears once", int(np.sum(np.any(result.impulse_contributions != 0.0, axis=(1, 2)))), "one panel", int(np.sum(np.any(result.impulse_contributions != 0.0, axis=(1, 2)))) == 1),
        _check("F12-18", "post-event cleared interval", zero_interval_cells, ">=3 interior zero cells", zero_interval_cells >= 3),
        _check("F12-19", "post-event simple-boundary status", bool(result.price_is_registered[1, displayed]), "false; p^- retained", not bool(result.price_is_registered[1, displayed])),
        _check("F12-20", "evolved boundaries registered", registered_evolved, "all true", registered_evolved),
        _check("F12-21", "positive initial buy response", initial_own_response, ">0", initial_own_response > 0.0),
        _check("F12-22", "translation-mode coupling active after spread", maximum_late_coupling, ">0", maximum_late_coupling > 0.0),
        _check("F12-23", "complete density ledger", maximum_ledger_error, "<=5e-15", maximum_ledger_error <= 5e-15),
        _check("F12-24", "outer boundary condition", float(np.max(np.abs(result.densities[:, :, [0, -1]]))), "<=1e-14", float(np.max(np.abs(result.densities[:, :, [0, -1]]))) <= 1e-14),
        _check("F12-25", "unique evolved zero crossings", [extract_reaction_boundary(grid, result.densities[panel, book], selection="nearest_previous", previous_price=float(result.prices[panel, book]), minimum_abs_slope=specification.minimum_abs_boundary_slope).candidate_count for panel in range(2, 9) for book in range(2)], "all one", all(extract_reaction_boundary(grid, result.densities[panel, book], selection="nearest_previous", previous_price=float(result.prices[panel, book]), minimum_abs_slope=specification.minimum_abs_boundary_slope).candidate_count == 1 for panel in range(2, 9) for book in range(2))),
        _check("F12-26", "late displacement is computed, not predeclared", late_own_displacement, "finite", math.isfinite(late_own_displacement)),
        _check("F12-27", "legacy executable excluded", configuration["scientific_boundary"]["legacy_executable_used"], "false", configuration["scientific_boundary"]["legacy_executable_used"] is False),
        _check("F12-28", "pointwise replication excluded", configuration["scientific_boundary"]["pointwise_replication_claimed"], "false", configuration["scientific_boundary"]["pointwise_replication_claimed"] is False),
        _check("F12-29", "frozen target paper", _sha256(PROJECT_ROOT / "source/source-v1/CATG-RD2Epps-v3-arXiv.tex"), "accepted hash", _sha256(PROJECT_ROOT / "source/source-v1/CATG-RD2Epps-v3-arXiv.tex") == "48eea98a6fb084d6ecc397bede4c107a44cae947e16271d66a7041e2997afb5a"),
        _check("F12-30", "frozen v2.0.0 supplement", _sha256(PROJECT_ROOT / "SUPPLEMENTARY-MATERIAL-v2.0.0.tex"), "accepted hash", _sha256(PROJECT_ROOT / "SUPPLEMENTARY-MATERIAL-v2.0.0.tex") == "960400980ae7224eca072f71ec9e69ead8bc0c9cc11024a4d48a66d55f403bf4"),
        _check("F12-31", "machine-readable archive", ARCHIVE_PATH.is_file(), "present", ARCHIVE_PATH.is_file()),
        _check("F12-32", "vector figure", FIGURE_STEM.with_suffix(".pdf").is_file(), "present", FIGURE_STEM.with_suffix(".pdf").is_file()),
    ]

    with Image.open(FIGURE_STEM.with_suffix(".png")) as image:
        png_size = image.size
        png_mode = image.mode
        png_dpi = image.info.get("dpi", (0.0, 0.0))
    checks.extend(
        [
            _check("F12-33", "PNG dimensions", png_size, "4500x3600", png_size == tuple(configuration["figure"]["png_pixels"])),
            _check("F12-34", "PNG colour mode", png_mode, "RGB or RGBA", png_mode in {"RGB", "RGBA"}),
            _check("F12-35", "PNG resolution metadata", png_dpi, "approximately 300 dpi", all(abs(float(value) - 300.0) <= 0.1 for value in png_dpi)),
            _check("F12-36", "three-by-three boundary-zoom visual contract", [configuration["figure"]["layout"], configuration["figure"]["boundary_window_relative_to_pre_event"], configuration["figure"]["full_profile_inset"]], "[3,3], boundary window [-0.8,1.2], full-profile inset", configuration["figure"]["layout"] == [3, 3] and configuration["figure"]["boundary_window_relative_to_pre_event"] == [-0.8, 1.2] and configuration["figure"]["full_profile_inset"] is True),
            _check("F12-37", "fixed semantic palette", [configuration["figure"][key] for key in ("density_colour", "arrival_colour", "removal_colour", "impulse_colour")], ["#009BFA", "#3EA44D", "#AD8F1B", "#C371D3"], [configuration["figure"][key] for key in ("density_colour", "arrival_colour", "removal_colour", "impulse_colour")] == ["#009BFA", "#3EA44D", "#AD8F1B", "#C371D3"]),
        ]
    )

    failures = [row for row in checks if row["status"] != "Verified"]
    write_csv(
        CHECK_PATH,
        ["check_id", "claim", "observed", "criterion", "status", "software_version"],
        checks,
    )
    summary = [
        {
            "result_label": "figure_12_order_book_shock_recovery_verified" if not failures else "figure_12_order_book_shock_recovery_failed",
            "verified_checks": len(checks) - len(failures),
            "failed_checks": len(failures),
            "event_quantity": result.event_application.filled_quantity,
            "execution_log_price": result.event_application.execution_log_price,
            "initial_own_price_response": initial_own_response,
            "late_own_price_displacement": late_own_displacement,
            "maximum_ledger_error": maximum_ledger_error,
            "maximum_cancellation_contribution": maximum_cancellation,
            "post_event_simple_boundary_registered": bool(result.price_is_registered[1, displayed]),
            "post_event_boundary_marker": "last_registered_pre_event_boundary",
            "positive_cancellation_sensitivity_run": False,
        }
    ]
    write_csv(SUMMARY_PATH, list(summary[0]), summary)
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['claim']}")
    if failures:
        print(f"Figure 12 recovery failed: {len(failures)} check(s) require attention.")
        return 1
    print(f"Figure 12 recovery completed: {len(checks)} checks verified, 0 failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
