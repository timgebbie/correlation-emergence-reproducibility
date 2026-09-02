"""Generate and verify the v2.1.0 current-model stylised-facts recovery."""

from __future__ import annotations

import csv
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
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from pypdf._page import PageObject

from functions.events import (
    EVENT_MARKET_ORDER,
    OrderEvent,
    operational_translation_event_tape_path,
    quote_midpoint_sign,
    tick_rule_signs,
)
from functions.figure_io import (
    STAGING_DIRECTORY,
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
from functions.observation import (
    poisson_refresh_path_from_uniforms,
    subordinate_two_book_previous_refresh,
)
from functions.operational import (
    OperationalSolverSpec,
    OperationalSource,
    TranslationModeCoupling,
    TwoBookInnovationPolicy,
    apply_spatial_boundary,
    operational_sibuya_kernel,
    operational_source_density,
    stationary_density,
)
from functions.stylised_facts import (
    aggregate_book_members,
    curve_difference,
    fixed_histogram,
    fixed_normal_qq,
    histogram_total_variation,
    member_autocorrelations,
    standardize_sample,
)
from functions.representative import (
    stable_nearest_median_index,
    validated_predeclared_nearest_median_index,
)


VERSION = "2.1.0"
CONFIG_PATH = PROJECT_ROOT / "config/config-v2.1.0-figure-13.json"
PANEL_CONFIG_DIRECTORY = PROJECT_ROOT / "config/figure-13-panels"
CHECK_PATH = PROJECT_ROOT / "diagnostics/figure-13-stylised-facts-checks-v2.1.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs/figure-13-summary-v2.1.csv"
SAMPLING_PATH = PROJECT_ROOT / "outputs/figure-13-sampling-audit-v2.1.csv"
STABILITY_PATH = PROJECT_ROOT / "outputs/figure-13-stability-audit-v2.1.csv"
SENSITIVITY_PATH = PROJECT_ROOT / "outputs/figure-13-order-flow-sensitivities-v2.1.csv"
ARCHIVE_PATH = PROJECT_ROOT / "outputs/figure-13-stylised-facts-recovery-v2.1.npz"
PANEL_MANIFEST_PATH = PROJECT_ROOT / "outputs/figure-13-panel-manifest-v2.1.csv"
FIGURE_STEM = PROJECT_ROOT / "figures/figure-13-stylised-facts-recovery-v2"
REPRESENTATIVE_POLICY_PATH = (
    PROJECT_ROOT / "config/config-v2.1.0-representative-paths.json"
)
DOMAINS = ("uniform_operational", "previous_refresh_calendar")
CONVENTIONS = ("ground_truth_aggressor", "quote_midpoint", "legacy_tick_rule")
LAYOUT_RESULTS: dict[str, tuple[bool, int]] = {}


def _scientific_accepted_inputs(configuration: dict[str, object]) -> list[dict[str, object]]:
    """Exclude the mutable reader-facing README from scientific input checks."""

    return [
        record
        for record in configuration["accepted_inputs"]
        if record.get("role") != "doi_bearing_public_readme"
    ]


def _load_configuration() -> dict[str, object]:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if configuration.get("schema_version") != VERSION:
        raise ValueError("Figure 13 configuration version mismatch")
    if configuration["scientific_boundary"]["row_meaning"] != list(DOMAINS):
        raise ValueError("Figure 13 row meaning differs from the accepted R6 gate")
    return configuration


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
    delta_u = transport * delta_x**2 / (2.0 * diffusion[0])
    if not np.isclose(delta_u, float(model["operational_step_model_units"])):
        raise ValueError("declared operational step does not match fixed lattice")
    sources = tuple(
        OperationalSource(
            float(model["source_lambda"][book]),
            float(model["source_mu"][book]),
        )
        for book in range(2)
    )
    stationary = np.stack(
        [
            apply_spatial_boundary(
                stationary_density(
                    grid,
                    np.asarray(operational_source_density(grid, 0.0, sources[book])),
                    diffusion=diffusion[book],
                    cancellation_rate=float(model["cancellation_rates"][book]),
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
    solver = OperationalSolverSpec(
        delta_u=delta_u,
        transport_probability=transport,
        cancellation_rates=tuple(float(value) for value in model["cancellation_rates"]),
        minimum_abs_boundary_slope=float(model["minimum_abs_boundary_slope"]),
    )
    rates = model["ordered_coupling_rates_per_model_time_unit"]
    couplings = (
        (None, TranslationModeCoupling(float(rates[0]))),
        (TranslationModeCoupling(float(rates[1])), None),
    )
    innovation_policy = TwoBookInnovationPolicy(
        float(model["innovation_sigma"][0]),
        float(model["innovation_sigma"][1]),
        float(model["microscopic_innovation_correlation"]),
    )
    return grid, diffusion, sources, stationary, kernels, solver, couplings, innovation_policy


def _master_inputs(configuration: dict[str, object]) -> np.ndarray:
    experiment = configuration["master_experiment"]
    primitive_paths = int(experiment["primitive_random_paths"])
    steps = int(experiment["total_operational_steps"])
    seed = int(experiment["operational_seed"])
    block_steps = 1400

    def whiten(raw: np.ndarray) -> np.ndarray:
        flat = raw.reshape(-1, 2)
        first = flat[:, 0]
        second = flat[:, 1]
        first -= np.mean(first)
        second -= np.mean(second)
        first *= np.sqrt(first.size / np.dot(first, first))
        second -= first * np.dot(first, second) / np.dot(first, first)
        second *= np.sqrt(second.size / np.dot(second, second))
        return np.stack((first, second), axis=1).reshape(raw.shape)

    primitive = np.empty((primitive_paths, steps, 2), dtype=float)
    accepted_raw = np.random.default_rng(seed).standard_normal((4, block_steps, 2))
    primitive[:4, :block_steps] = whiten(accepted_raw)
    additional_raw = np.random.default_rng(
        np.random.SeedSequence([seed, 210, 0])
    ).standard_normal((primitive_paths - 4, block_steps, 2))
    primitive[4:, :block_steps] = whiten(additional_raw)
    for block in range(1, steps // block_steps):
        raw = np.random.default_rng(
            np.random.SeedSequence([seed, 210, block])
        ).standard_normal((primitive_paths, block_steps, 2))
        primitive[:, block * block_steps : (block + 1) * block_steps] = whiten(raw)
    if steps % block_steps:
        raise ValueError("Figure 13 master horizon must be an integer number of 1400-step blocks")
    result = np.concatenate((primitive, -primitive), axis=0)
    result.setflags(write=False)
    return result


def _arrival_and_sign_grids(
    configuration: dict[str, object], steps: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    experiment = configuration["master_experiment"]
    primitive_paths = int(experiment["primitive_random_paths"])
    start = int(experiment["event_start_operational_step"])
    last = steps - int(experiment["terminal_event_margin_steps"])
    probability = float(experiment["arrival_probability_per_step"])
    repeat_probability = float(experiment["declared_sign_repeat_probability"])
    primitive_arrivals = np.zeros((primitive_paths, 2, steps + 1), dtype=bool)
    primitive_signs = np.zeros((primitive_paths, 2, steps + 1), dtype=np.int8)
    for path in range(primitive_paths):
        for book in range(2):
            arrival_rng = np.random.default_rng(
                np.random.SeedSequence(
                    [int(experiment["arrival_seed"]), 701, path, book]
                )
            )
            primitive_arrivals[path, book, start : last + 1] = (
                arrival_rng.random(last - start + 1) < probability
            )
            event_steps = np.flatnonzero(primitive_arrivals[path, book])
            if event_steps.size < 2:
                raise RuntimeError("Figure 13 arrival stream has insufficient events")
            sign_rng = np.random.default_rng(
                np.random.SeedSequence(
                    [int(experiment["sign_seed"]), 701, path, book]
                )
            )
            event_signs = np.empty(event_steps.size, dtype=np.int8)
            event_signs[0] = 1 if sign_rng.random() >= 0.5 else -1
            repeats = sign_rng.random(event_steps.size - 1) < repeat_probability
            for event in range(1, event_steps.size):
                event_signs[event] = (
                    event_signs[event - 1]
                    if repeats[event - 1]
                    else -event_signs[event - 1]
                )
            primitive_signs[path, book, event_steps] = event_signs
    arrivals = np.concatenate((primitive_arrivals, primitive_arrivals), axis=0)
    signs = np.concatenate((primitive_signs, -primitive_signs), axis=0)
    return arrivals, signs, primitive_arrivals


def _events_for_path(
    path_index: int,
    arrivals: np.ndarray,
    signs: np.ndarray,
    quantity: float,
) -> tuple[tuple[OrderEvent, ...], tuple[np.ndarray, np.ndarray]]:
    records = []
    event_steps = []
    for book in range(2):
        steps = np.flatnonzero(arrivals[path_index, book])
        event_steps.append(steps)
        for event_index, operational_step in enumerate(steps):
            records.append(
                OrderEvent(
                    event_id=f"fig13-p{path_index:02d}-b{book + 1}-e{event_index + 1:03d}",
                    event_type=EVENT_MARKET_ORDER,
                    book_index=book,
                    operational_step=int(operational_step),
                    side=int(signs[path_index, book, operational_step]),
                    quantity=quantity,
                )
            )
    records.sort(key=lambda event: (event.operational_step, event.book_index, event.event_id))
    return tuple(records), (event_steps[0], event_steps[1])


def _master_refresh_pairs(configuration: dict[str, object], horizon_seconds: float):
    experiment = configuration["master_experiment"]
    primitive_paths = int(experiment["primitive_random_paths"])
    count = int(experiment["clock_uniforms_per_book_path"])
    primitive = np.random.default_rng(int(experiment["clock_seed"])).random(
        (primitive_paths, 2, count)
    )
    rates = tuple(float(value) for value in experiment["book_refresh_rates_per_second"])
    pairs = []
    for path in range(2 * primitive_paths):
        source = primitive[path] if path < primitive_paths else primitive[path - primitive_paths, ::-1]
        pairs.append(
            tuple(
                poisson_refresh_path_from_uniforms(
                    source[book],
                    rates[book],
                    horizon_seconds,
                    stream_id=f"v2.1.0-figure13-path-{path:02d}-book-{book + 1}",
                )
                for book in range(2)
            )
        )
    return tuple(pairs)


def _run_master(
    configuration: dict[str, object],
    *,
    steps: int,
) -> dict[str, np.ndarray | float]:
    experiment = configuration["master_experiment"]
    paths = int(experiment["paths"])
    quantity = float(experiment["event_quantity"])
    step_seconds = float(configuration["model"]["operational_step_seconds"])
    times = np.arange(steps + 1, dtype=float) * step_seconds
    grid, diffusion, sources, stationary, kernels, solver, couplings, innovation_policy = _model(configuration)
    inputs = _master_inputs(configuration)[:, :steps]
    arrivals, declared_signs, primitive_arrivals = _arrival_and_sign_grids(
        configuration, steps
    )
    refresh_pairs = _master_refresh_pairs(configuration, float(times[-1]))

    operational_prices = np.empty((paths, steps + 1, 2), dtype=float)
    calendar_prices = np.empty_like(operational_prices)
    calendar_indices = np.empty((paths, steps + 1, 2), dtype=np.int64)
    quote_signs = np.zeros_like(declared_signs)
    tick_signs = np.zeros_like(declared_signs)
    operational_cumulative_flows = np.empty((paths, len(CONVENTIONS), steps + 1, 2))
    calendar_cumulative_flows = np.empty_like(operational_cumulative_flows)
    maximum_mass_error = 0.0
    minimum_edge_distance = math.inf
    maximum_boundary_candidates = 0
    minimum_execution_side_product = math.inf
    immediate_moves: list[float] = []
    background_increments: list[float] = []

    for path in range(paths):
        events, event_steps = _events_for_path(
            path, arrivals, declared_signs, quantity
        )
        result = operational_translation_event_tape_path(
            grid,
            stationary,
            (0.0, 0.0),
            sources,
            couplings,
            kernels,
            inputs[path],
            innovation_policy,
            diffusion,
            solver,
            events,
        )
        operational_prices[path] = result.prices
        minimum_edge_distance = min(
            minimum_edge_distance, float(np.min(result.boundary_edge_distances))
        )
        maximum_boundary_candidates = max(
            maximum_boundary_candidates, int(np.max(result.boundary_candidate_counts))
        )
        applications_by_book: list[list[object]] = [[], []]
        for application in result.event_applications:
            applications_by_book[application.event.book_index].append(application)
            mass = float((grid[1] - grid[0]) * np.sum(np.abs(application.density_delta)))
            maximum_mass_error = max(maximum_mass_error, abs(mass - quantity))
            minimum_execution_side_product = min(
                minimum_execution_side_product,
                application.event.side
                * (
                    float(application.execution_log_price)
                    - application.pre_event_mid_log_price
                ),
            )
        for book in range(2):
            book_applications = sorted(
                applications_by_book[book], key=lambda item: item.event.operational_step
            )
            book_steps = event_steps[book]
            execution_prices = np.asarray(
                [float(item.execution_log_price) for item in book_applications]
            )
            quote_signs[path, book, book_steps] = np.asarray(
                [quote_midpoint_sign(item) for item in book_applications], dtype=np.int8
            )
            tick_signs[path, book, book_steps] = tick_rule_signs(
                execution_prices
            ).astype(np.int8)
            signed_moves = declared_signs[path, book, book_steps] * (
                result.prices[book_steps, book]
                - result.prices[book_steps - 1, book]
            )
            immediate_moves.extend(signed_moves.tolist())

        increments = np.diff(result.prices, axis=0)
        event_free = ~np.any(arrivals[path, :, 1:], axis=0)
        background_increments.extend(increments[event_free].ravel().tolist())

        subordinated = subordinate_two_book_previous_refresh(
            times, result.prices, refresh_pairs[path], times
        )
        calendar_prices[path] = subordinated.prices
        calendar_indices[path] = subordinated.operational_indices
        convention_signs = np.stack(
            (
                declared_signs[path].T,
                quote_signs[path].T,
                tick_signs[path].T,
            ),
            axis=0,
        )
        for convention in range(len(CONVENTIONS)):
            cumulative = np.cumsum(convention_signs[convention], axis=0)
            operational_cumulative_flows[path, convention] = cumulative
            for book in range(2):
                calendar_cumulative_flows[path, convention, :, book] = cumulative[
                    calendar_indices[path, :, book], book
                ]
        print(
            f"  completed Figure 13 {steps}-step path {path + 1}/{paths}",
            flush=True,
        )

    return {
        "inputs": inputs,
        "arrivals": arrivals,
        "primitive_arrivals": primitive_arrivals,
        "declared_signs": declared_signs,
        "quote_signs": quote_signs,
        "tick_signs": tick_signs,
        "times": times,
        "operational_prices": operational_prices,
        "calendar_prices": calendar_prices,
        "calendar_indices": calendar_indices,
        "operational_cumulative_flows": operational_cumulative_flows,
        "calendar_cumulative_flows": calendar_cumulative_flows,
        "maximum_mass_error": maximum_mass_error,
        "minimum_edge_distance": minimum_edge_distance,
        "maximum_boundary_candidates": maximum_boundary_candidates,
        "minimum_execution_side_product": minimum_execution_side_product,
        "immediate_moves": np.asarray(immediate_moves),
        "background_increments": np.asarray(background_increments),
    }


def _path_indices(paths: int, primitive_paths: int) -> np.ndarray:
    half = paths // 2
    return np.concatenate((np.arange(half), primitive_paths + np.arange(half))).astype(int)


def _analyse_design(
    design: dict[str, object],
    master: dict[str, np.ndarray | float],
    configuration: dict[str, object],
) -> dict[str, object]:
    experiment = configuration["master_experiment"]
    distribution = configuration["distribution"]
    paths = int(design["paths"])
    steps = int(design["operational_steps"])
    maximum_lag = int(experiment["autocorrelation_maximum_lag"])
    stride = int(experiment["price_diagnostic_stride_steps"])
    start = int(experiment["price_diagnostic_start_operational_step"])
    indices = np.arange(start, steps + 1, stride, dtype=int)
    selected_paths = _path_indices(paths, int(experiment["primitive_random_paths"]))

    operational_prices = np.asarray(master["operational_prices"])[selected_paths, : steps + 1]
    calendar_prices = np.asarray(master["calendar_prices"])[selected_paths, : steps + 1]
    returns = np.stack(
        (
            np.diff(operational_prices[:, indices, :], axis=1),
            np.diff(calendar_prices[:, indices, :], axis=1),
        ),
        axis=0,
    )
    operational_flows = np.asarray(master["operational_cumulative_flows"])[
        selected_paths, :, : steps + 1
    ]
    calendar_flows = np.asarray(master["calendar_cumulative_flows"])[
        selected_paths, :, : steps + 1
    ]
    binned_flows = np.stack(
        (
            np.diff(operational_flows[:, :, indices, :], axis=2),
            np.diff(calendar_flows[:, :, indices, :], axis=2),
        ),
        axis=0,
    )

    return_members = np.empty((2, paths, 2, maximum_lag + 1))
    absolute_members = np.empty_like(return_members)
    flow_members = np.empty((2, len(CONVENTIONS), paths, 2, maximum_lag + 1))
    return_path_curves = np.empty((2, paths, maximum_lag + 1))
    absolute_path_curves = np.empty_like(return_path_curves)
    return_mean = np.empty((2, maximum_lag + 1))
    return_se = np.empty_like(return_mean)
    absolute_mean = np.empty_like(return_mean)
    absolute_se = np.empty_like(return_mean)
    flow_path_curves = np.empty((2, len(CONVENTIONS), paths, maximum_lag + 1))
    flow_mean = np.empty((2, len(CONVENTIONS), maximum_lag + 1))
    flow_se = np.empty_like(flow_mean)
    for domain in range(2):
        return_members[domain] = member_autocorrelations(returns[domain], maximum_lag)
        absolute_members[domain] = member_autocorrelations(
            np.abs(returns[domain]), maximum_lag
        )
        (
            return_path_curves[domain],
            return_mean[domain],
            return_se[domain],
        ) = aggregate_book_members(return_members[domain])
        (
            absolute_path_curves[domain],
            absolute_mean[domain],
            absolute_se[domain],
        ) = aggregate_book_members(absolute_members[domain])
        for convention in range(len(CONVENTIONS)):
            flow_members[domain, convention] = member_autocorrelations(
                binned_flows[domain, :, convention], maximum_lag
            )
            (
                flow_path_curves[domain, convention],
                flow_mean[domain, convention],
                flow_se[domain, convention],
            ) = aggregate_book_members(flow_members[domain, convention])

    standardized = []
    sample_means = []
    sample_standard_deviations = []
    histogram_edges = []
    histogram_centres = []
    histogram_density = []
    normal_density = []
    probabilities = []
    normal_quantiles = []
    sample_quantiles = []
    for domain in range(2):
        values, mean, standard_deviation = standardize_sample(returns[domain].ravel())
        edges, centres, density, normal = fixed_histogram(
            values,
            lower=float(distribution["histogram_lower_by_domain"][domain]),
            upper=float(distribution["histogram_upper_by_domain"][domain]),
            bins=int(distribution["histogram_bins"]),
        )
        probability, normal_q, sample_q = fixed_normal_qq(
            values,
            lower_probability=float(distribution["qq_probability_lower"]),
            upper_probability=float(distribution["qq_probability_upper"]),
            count=int(distribution["qq_probability_count"]),
        )
        standardized.append(values)
        sample_means.append(mean)
        sample_standard_deviations.append(standard_deviation)
        histogram_edges.append(edges)
        histogram_centres.append(centres)
        histogram_density.append(density)
        normal_density.append(normal)
        probabilities.append(probability)
        normal_quantiles.append(normal_q)
        sample_quantiles.append(sample_q)

    operational_rms = np.sqrt(np.mean(returns[0] ** 2, axis=(1, 2)))
    median_rms = float(np.median(operational_rms))
    representative_policy = json.loads(
        REPRESENTATIVE_POLICY_PATH.read_text(encoding="utf-8")
    )
    tolerance_ulps = int(representative_policy["distance_tolerance_ulps"])
    if str(design["design_id"]) == "extended_both":
        predeclared_master_index = int(
            representative_policy["figure_13"]["predeclared_master_path_index"]
        )
        local_matches = np.flatnonzero(selected_paths == predeclared_master_index)
        if local_matches.size != 1:
            raise ValueError(
                "predeclared Figure 13 path is absent from the production ensemble"
            )
        local_representative = validated_predeclared_nearest_median_index(
            operational_rms,
            predeclared_index=int(local_matches[0]),
            distance_tolerance_ulps=tolerance_ulps,
        )
    else:
        local_representative = stable_nearest_median_index(
            operational_rms, distance_tolerance_ulps=tolerance_ulps
        )
    input_subset = np.asarray(master["inputs"])[selected_paths, :steps]
    input_correlation = float(np.corrcoef(input_subset.reshape(-1, 2).T)[0, 1])
    selected_arrivals = np.asarray(master["arrivals"])[selected_paths, :, : steps + 1]
    event_counts = np.sum(selected_arrivals, axis=2)
    last_events = [
        int(np.max(np.flatnonzero(selected_arrivals[path, book])))
        for path in range(paths)
        for book in range(2)
    ]
    terminal_margin = int(experiment["terminal_event_margin_steps"])
    minimum_actual_event_margin = steps - max(last_events)

    return {
        "design_id": design["design_id"],
        "paths": paths,
        "steps": steps,
        "minimum_events_per_path_book": int(np.min(event_counts)),
        "mean_events_per_path_book": float(np.mean(event_counts)),
        "maximum_events_per_path_book": int(np.max(event_counts)),
        "path_indices": selected_paths,
        "sample_indices": indices,
        "operational_prices": operational_prices,
        "calendar_prices": calendar_prices,
        "returns": returns,
        "binned_flows": binned_flows,
        "return_members": return_members,
        "absolute_members": absolute_members,
        "flow_members": flow_members,
        "return_path_curves": return_path_curves,
        "absolute_path_curves": absolute_path_curves,
        "flow_path_curves": flow_path_curves,
        "return_mean": return_mean,
        "return_se": return_se,
        "absolute_mean": absolute_mean,
        "absolute_se": absolute_se,
        "flow_mean": flow_mean,
        "flow_se": flow_se,
        "standardized": np.asarray(standardized),
        "sample_means": np.asarray(sample_means),
        "sample_standard_deviations": np.asarray(sample_standard_deviations),
        "histogram_edges": np.asarray(histogram_edges),
        "histogram_centres": np.asarray(histogram_centres),
        "histogram_density": np.asarray(histogram_density),
        "normal_density": np.asarray(normal_density),
        "probabilities": np.asarray(probabilities),
        "normal_quantiles": np.asarray(normal_quantiles),
        "sample_quantiles": np.asarray(sample_quantiles),
        "representative_local_index": local_representative,
        "representative_master_index": int(selected_paths[local_representative]),
        "representative_rms": float(operational_rms[local_representative]),
        "median_rms": median_rms,
        "input_correlation": input_correlation,
        "terminal_margin": terminal_margin,
        "minimum_actual_event_margin": minimum_actual_event_margin,
        "effective_pairs_at_maximum_lag": int(indices.size - 1 - maximum_lag),
    }


def _leave_one_out_maximum(path_curves: np.ndarray) -> float:
    values = np.asarray(path_curves, dtype=float)
    full = np.mean(values, axis=0)
    maximum = 0.0
    for path in range(values.shape[0]):
        reduced = np.mean(np.delete(values, path, axis=0), axis=0)
        maximum = max(maximum, float(np.max(np.abs(reduced[1:] - full[1:]))))
    return maximum


def _stability_rows(
    designs: dict[str, dict[str, object]], configuration: dict[str, object]
) -> tuple[list[dict[str, object]], dict[str, bool]]:
    policy = configuration["stability"]
    extension_2_used = "extended_2_both" in designs
    extension_used = "extended_both" in designs
    reference_id = (
        "extended_2_both"
        if extension_2_used
        else "extended_both"
        if extension_used
        else "both_doubled"
    )
    reference = designs[reference_id]
    rows: list[dict[str, object]] = []
    candidate_ids = (
        ("extended_2_horizon", "extended_2_both")
        if extension_2_used
        else ("extended_horizon", "extended_both")
        if extension_used
        else ("longer_paths", "both_doubled")
    )
    candidate_pass = {design_id: True for design_id in candidate_ids}

    def add(
        comparison: str,
        domain: str,
        observable: str,
        metric: str,
        observed: float,
        threshold: float,
    ) -> None:
        passed = observed <= threshold
        rows.append(
            {
                "reference_design": reference_id,
                "comparison_design": comparison,
                "measurement_domain": domain,
                "observable": observable,
                "metric": metric,
                "observed": observed,
                "criterion": f"<= {threshold}",
                "status": "Verified" if passed else "Failed",
                "software_version": VERSION,
            }
        )
        if comparison in candidate_pass:
            candidate_pass[comparison] = candidate_pass[comparison] and passed

    comparison_ids = (
        ("extended_2_horizon", "extended_both")
        if extension_2_used
        else ("extended_horizon", "both_doubled")
        if extension_used
        else ("longer_paths", "more_paths")
    )
    for comparison_id in comparison_ids:
        comparison = designs[comparison_id]
        for domain, domain_name in enumerate(DOMAINS):
            width = float(reference["histogram_edges"][domain, 1] - reference["histogram_edges"][domain, 0])
            tv = histogram_total_variation(
                reference["histogram_density"][domain],
                comparison["histogram_density"][domain],
                width,
            )
            add(
                comparison_id,
                domain_name,
                "standardized_return_density",
                "total_variation",
                tv,
                float(policy["maximum_histogram_total_variation"]),
            )
            probabilities = np.asarray(reference["probabilities"][domain])
            difference = np.abs(
                np.asarray(reference["sample_quantiles"][domain])
                - np.asarray(comparison["sample_quantiles"][domain])
            )
            central = (probabilities >= 0.05) & (probabilities <= 0.95)
            add(
                comparison_id,
                domain_name,
                "normal_qq",
                "maximum_central_difference",
                float(np.max(difference[central])),
                float(policy["maximum_central_qq_difference"]),
            )
            add(
                comparison_id,
                domain_name,
                "normal_qq",
                "maximum_tail_difference",
                float(np.max(difference[~central])),
                float(policy["maximum_tail_qq_difference"]),
            )
            for observable, reference_curve, comparison_curve in (
                ("log_mid_increment_acf", reference["return_mean"][domain, 1:], comparison["return_mean"][domain, 1:]),
                ("absolute_increment_acf", reference["absolute_mean"][domain, 1:], comparison["absolute_mean"][domain, 1:]),
                ("signed_flow_acf", reference["flow_mean"][domain, 0, 1:], comparison["flow_mean"][domain, 0, 1:]),
            ):
                rmse, maximum = curve_difference(reference_curve, comparison_curve)
                add(
                    comparison_id,
                    domain_name,
                    observable,
                    "rmse",
                    rmse,
                    float(policy["maximum_acf_rmse"]),
                )
                add(
                    comparison_id,
                    domain_name,
                    observable,
                    "maximum_absolute_difference",
                    maximum,
                    float(policy["maximum_acf_difference"]),
                )

    if extension_used:
        historical_pairs = [("both_doubled", "more_paths")]
        if extension_2_used:
            historical_pairs.append(("extended_both", "both_doubled"))
        for initial_reference_id, comparison_id in historical_pairs:
            initial_reference = designs[initial_reference_id]
            comparison = designs[comparison_id]
            for domain, domain_name in enumerate(DOMAINS):
                probabilities = np.asarray(initial_reference["probabilities"][domain])
                qq_difference = np.abs(
                    np.asarray(initial_reference["sample_quantiles"][domain])
                    - np.asarray(comparison["sample_quantiles"][domain])
                )
                central = (probabilities >= 0.05) & (probabilities <= 0.95)
                for metric, observed, threshold in (
                    ("maximum_central_difference", float(np.max(qq_difference[central])), float(policy["maximum_central_qq_difference"])),
                    ("maximum_tail_difference", float(np.max(qq_difference[~central])), float(policy["maximum_tail_qq_difference"])),
                ):
                    if observed > threshold:
                        rows.append(
                            {
                                "reference_design": initial_reference_id,
                                "comparison_design": comparison_id,
                                "measurement_domain": domain_name,
                                "observable": "normal_qq",
                                "metric": f"{metric}_extension_trigger",
                                "observed": observed,
                                "criterion": "recorded; geometric horizon extension required",
                                "status": "ExtensionTriggered",
                                "software_version": VERSION,
                            }
                        )
                for observable, reference_curve, comparison_curve in (
                    ("log_mid_increment_acf", initial_reference["return_mean"][domain, 1:], comparison["return_mean"][domain, 1:]),
                    ("absolute_increment_acf", initial_reference["absolute_mean"][domain, 1:], comparison["absolute_mean"][domain, 1:]),
                    ("signed_flow_acf", initial_reference["flow_mean"][domain, 0, 1:], comparison["flow_mean"][domain, 0, 1:]),
                ):
                    rmse, maximum = curve_difference(reference_curve, comparison_curve)
                    if rmse > float(policy["maximum_acf_rmse"]) or maximum > float(policy["maximum_acf_difference"]):
                        rows.append(
                            {
                                "reference_design": initial_reference_id,
                                "comparison_design": comparison_id,
                                "measurement_domain": domain_name,
                                "observable": observable,
                                "metric": "initial_four_design_extension_trigger",
                                "observed": max(rmse, maximum),
                                "criterion": "recorded; geometric horizon extension required",
                                "status": "ExtensionTriggered",
                                "software_version": VERSION,
                            }
                        )

    for design_id in candidate_ids:
        design = designs[design_id]
        maximum = 0.0
        for domain in range(2):
            maximum = max(
                maximum,
                _leave_one_out_maximum(design["return_path_curves"][domain]),
                _leave_one_out_maximum(design["absolute_path_curves"][domain]),
                _leave_one_out_maximum(design["flow_path_curves"][domain, 0]),
            )
        passed = maximum <= float(policy["maximum_leave_one_path_out_acf_difference"])
        rows.append(
            {
                "reference_design": design_id,
                "comparison_design": "leave_one_path_out",
                "measurement_domain": "both",
                "observable": "all_primary_acfs",
                "metric": "maximum_absolute_difference",
                "observed": maximum,
                "criterion": f"<= {policy['maximum_leave_one_path_out_acf_difference']}",
                "status": "Verified" if passed else "Failed",
                "software_version": VERSION,
            }
        )
        candidate_pass[design_id] = candidate_pass[design_id] and passed
    return rows, candidate_pass


def _select_production_design(
    designs: dict[str, dict[str, object]],
    candidate_pass: dict[str, bool],
    configuration: dict[str, object],
) -> str:
    policy = configuration["stability"]
    candidate_ids = (
        ("extended_2_both",)
        if "extended_2_both" in designs
        else ("extended_both",)
        if "extended_both" in designs
        else ("both_doubled",)
    )
    for design_id in candidate_ids:
        design = designs[design_id]
        sufficient = (
            int(design["effective_pairs_at_maximum_lag"])
            >= int(policy["minimum_pairs_per_book_at_maximum_lag"])
            and int(design["paths"]) >= int(policy["minimum_independent_paths"])
            and all(
                int(np.sum(np.abs(design["standardized"][domain]) > 3.0))
                >= int(policy["minimum_extreme_tail_observations"])
                for domain in range(2)
            )
        )
        if sufficient and candidate_pass[design_id]:
            return design_id
    raise RuntimeError("no registered Figure 13 sampling design satisfies the stability gate")


def _atomic_save_npz(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_STAGING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_STAGING_DIRECTORY / f"{path.stem}-{uuid.uuid4().hex}.tmp{path.suffix}"
    try:
        with temporary.open("wb") as handle:
            np.savez_compressed(handle, **arrays)
        sync_completed_file(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
        try:
            OUTPUT_STAGING_DIRECTORY.rmdir()
        except OSError:
            pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _panel_paths(panel: dict[str, object]) -> tuple[Path, Path, Path]:
    stem = PROJECT_ROOT / str(panel["output_stem"])
    return stem.with_suffix(".pdf"), stem.with_suffix(".png"), PROJECT_ROOT / str(panel["data_path"])


def _style_axis(axis) -> None:
    axis.grid(alpha=0.18, linewidth=0.5)
    axis.tick_params(labelsize=7.0)


def _axis_text_boxes(axis, renderer):
    artists = [
        *axis.get_xticklabels(),
        *axis.get_yticklabels(),
        axis.xaxis.label,
        axis.yaxis.label,
    ]
    return [
        artist.get_window_extent(renderer)
        for artist in artists
        if artist.get_visible() and artist.get_text()
    ]


def _record_layout(panel_id: str, figure, axes: list[object]) -> None:
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    canvas = figure.bbox
    groups = [_axis_text_boxes(axis, renderer) for axis in axes]
    in_bounds = all(
        box.x0 >= canvas.x0
        and box.y0 >= canvas.y0
        and box.x1 <= canvas.x1
        and box.y1 <= canvas.y1
        for group in groups
        for box in group
    )
    collisions = 0
    for first in range(len(groups)):
        for second in range(first + 1, len(groups)):
            collisions += sum(
                first_box.overlaps(second_box)
                for first_box in groups[first]
                for second_box in groups[second]
            )
    LAYOUT_RESULTS[panel_id] = (in_bounds, collisions)


def _plot_price_panel(
    panel: dict[str, object],
    domain: int,
    production: dict[str, object],
    master: dict[str, np.ndarray | float],
    configuration: dict[str, object],
) -> None:
    figure_config = configuration["figure"]
    primary = figure_config["primary_colour"]
    representative = int(production["representative_local_index"])
    book = int(configuration["master_experiment"]["displayed_book"])
    prices = (
        production["operational_prices"] if domain == 0 else production["calendar_prices"]
    )[representative, :, book]
    times = np.asarray(master["times"])[: int(production["steps"]) + 1]
    returns = production["returns"][domain, representative, :, book]
    return_times = times[np.asarray(production["sample_indices"])][1:]

    figure = plt.figure(figsize=tuple(figure_config["standalone_canvas_inches"]))
    axis = figure.add_axes([0.18, 0.15, 0.72, 0.72])
    axis.plot(times, prices, color=primary, lw=0.80)
    axis.set_xlabel("Time [s]", fontsize=8.0)
    axis.set_ylabel("Log-mid price", fontsize=8.0)
    _style_axis(axis)
    inset = figure.add_axes([0.51, 0.56, 0.38, 0.27], facecolor="white")
    inset.plot(return_times, returns, color=primary, lw=0.62)
    inset.axhline(0.0, color="#555555", lw=0.45)
    inset.set_xlabel("Time [s]", fontsize=6.0)
    inset.set_ylabel("Log returns", fontsize=6.0)
    inset.tick_params(labelsize=5.5)
    inset.grid(alpha=0.16, linewidth=0.35)
    _record_layout(str(panel["panel_id"]), figure, [axis, inset])
    pdf, png, data = _panel_paths(panel)
    metadata = {"Creator": "correlation-emergence-v2.1.0", "CreationDate": None, "ModDate": None}
    atomic_savefig(figure, pdf, metadata=metadata)
    atomic_savefig(figure, png, dpi=int(figure_config["png_dpi"]))
    plt.close(figure)
    sample_lookup = {int(index): float(value) for index, value in zip(production["sample_indices"][1:], returns)}
    rows = [
        {
            "measurement_domain": DOMAINS[domain],
            "representative_master_path_index": production["representative_master_index"],
            "displayed_book_index": book,
            "operational_step": step,
            "time_seconds": times[step],
            "log_mid_price": prices[step],
            "five_second_log_mid_increment": sample_lookup.get(step, ""),
            "software_version": VERSION,
        }
        for step in range(prices.size)
    ]
    write_csv(data, list(rows[0]), rows)


def _plot_distribution_panel(
    panel: dict[str, object],
    domain: int,
    production: dict[str, object],
    configuration: dict[str, object],
) -> None:
    figure_config = configuration["figure"]
    primary = figure_config["primary_colour"]
    normal_colour = figure_config["normal_reference_colour"]
    identity_colour = figure_config["identity_colour"]
    edges = production["histogram_edges"][domain]
    centres = production["histogram_centres"][domain]
    density = production["histogram_density"][domain]
    normal = production["normal_density"][domain]
    normal_q = production["normal_quantiles"][domain]
    sample_q = production["sample_quantiles"][domain]

    figure = plt.figure(figsize=tuple(figure_config["standalone_canvas_inches"]))
    axis = figure.add_axes([0.18, 0.15, 0.72, 0.72])
    axis.stairs(density, edges, color=primary, fill=True, alpha=0.72, lw=0.8, label="Returns")
    axis.plot(centres, normal, color=normal_colour, lw=1.2, label=r"Fixed $N(0,1)$")
    axis.set_xlim(float(edges[0]), float(edges[-1]))
    axis.set_xlabel("Standardized log return", fontsize=8.0)
    axis.set_ylabel("Density", fontsize=8.0)
    axis.legend(frameon=False, fontsize=6.0, loc="upper left")
    _style_axis(axis)
    inset = figure.add_axes([0.51, 0.56, 0.38, 0.27], facecolor="white")
    lower = float(min(np.min(normal_q), np.min(sample_q)))
    upper = float(max(np.max(normal_q), np.max(sample_q)))
    padding = 0.06 * (upper - lower)
    limits = (lower - padding, upper + padding)
    inset.plot(limits, limits, color=identity_colour, lw=0.8)
    inset.plot(normal_q, sample_q, color=primary, marker="o", markersize=1.8, lw=0.75)
    inset.set_xlim(*limits)
    inset.set_ylim(*limits)
    inset.set_xlabel("Theoretical quantiles", fontsize=6.0)
    inset.set_ylabel("Sample quantiles", fontsize=6.0)
    inset.tick_params(labelsize=5.5)
    inset.grid(alpha=0.16, linewidth=0.35)
    _record_layout(str(panel["panel_id"]), figure, [axis, inset])
    pdf, png, data = _panel_paths(panel)
    metadata = {"Creator": "correlation-emergence-v2.1.0", "CreationDate": None, "ModDate": None}
    atomic_savefig(figure, pdf, metadata=metadata)
    atomic_savefig(figure, png, dpi=int(figure_config["png_dpi"]))
    plt.close(figure)
    rows = []
    for index, centre in enumerate(centres):
        rows.append(
            {
                "measurement_domain": DOMAINS[domain],
                "object": "density",
                "index": index,
                "x": centre,
                "y": density[index],
                "reference_x": centre,
                "reference_y": normal[index],
                "sample_count": production["standardized"][domain].size,
                "software_version": VERSION,
            }
        )
    for index, probability in enumerate(production["probabilities"][domain]):
        rows.append(
            {
                "measurement_domain": DOMAINS[domain],
                "object": "qq",
                "index": index,
                "x": normal_q[index],
                "y": sample_q[index],
                "reference_x": normal_q[index],
                "reference_y": normal_q[index],
                "sample_count": production["standardized"][domain].size,
                "software_version": VERSION,
            }
        )
    write_csv(data, list(rows[0]), rows)


def _acf_stem(axis, lags, mean, se, configuration: dict[str, object], title: str | None) -> None:
    figure_config = configuration["figure"]
    primary = figure_config["primary_colour"]
    upper = mean + 1.96 * se
    lower = mean - 1.96 * se
    axis.vlines(lags, 0.0, mean, color=primary, lw=0.7)
    axis.plot(lags, mean, color=primary, marker="o", markersize=1.7, lw=0.55)
    axis.plot(lags, upper, color=figure_config["upper_band_colour"], ls=":", lw=0.65)
    axis.plot(lags, lower, color=figure_config["lower_band_colour"], ls=":", lw=0.65)
    axis.axhline(0.0, color="#555555", lw=0.45)
    axis.set_ylim(min(-0.20, float(np.min(lower[1:])) - 0.05), 1.05)
    if title is not None:
        axis.set_title(title)
    axis.grid(alpha=0.16, linewidth=0.35)


def _plot_acf_panel(
    panel: dict[str, object],
    domain: int,
    production: dict[str, object],
    configuration: dict[str, object],
) -> None:
    figure_config = configuration["figure"]
    interval = (
        int(configuration["master_experiment"]["price_diagnostic_stride_steps"])
        * float(configuration["model"]["operational_step_seconds"])
    )
    lags = np.arange(production["return_mean"].shape[-1]) * interval
    figure = plt.figure(figsize=tuple(figure_config["standalone_canvas_inches"]))
    axis = figure.add_axes([0.18, 0.15, 0.72, 0.72])
    _acf_stem(
        axis,
        lags,
        production["return_mean"][domain],
        production["return_se"][domain],
        configuration,
        None,
    )
    axis.set_xlabel("Lag [s]", fontsize=8.0)
    axis.set_ylabel("ACF log returns", fontsize=8.0)
    _style_axis(axis)
    absolute_axis = figure.add_axes([0.34, 0.35, 0.55, 0.48], facecolor="white")
    _acf_stem(
        absolute_axis,
        lags,
        production["absolute_mean"][domain],
        production["absolute_se"][domain],
        configuration,
        None,
    )
    absolute_axis.tick_params(labelsize=5.5)
    absolute_axis.set_ylabel("ACF absolute log returns", fontsize=6.2)
    flow_axis = figure.add_axes([0.54, 0.54, 0.33, 0.27], facecolor="white")
    _acf_stem(
        flow_axis,
        lags,
        production["flow_mean"][domain, 0],
        production["flow_se"][domain, 0],
        configuration,
        None,
    )
    flow_axis.tick_params(labelsize=5.5)
    flow_axis.set_ylabel("ACF signed order flow", fontsize=6.0)
    _record_layout(str(panel["panel_id"]), figure, [axis, absolute_axis, flow_axis])
    pdf, png, data = _panel_paths(panel)
    metadata = {"Creator": "correlation-emergence-v2.1.0", "CreationDate": None, "ModDate": None}
    atomic_savefig(figure, pdf, metadata=metadata)
    atomic_savefig(figure, png, dpi=int(figure_config["png_dpi"]))
    plt.close(figure)
    rows = []
    for observable, mean, se in (
        ("log_mid_increment", production["return_mean"][domain], production["return_se"][domain]),
        ("absolute_log_mid_increment", production["absolute_mean"][domain], production["absolute_se"][domain]),
        ("declared_aggressor_signed_flow", production["flow_mean"][domain, 0], production["flow_se"][domain, 0]),
    ):
        for lag_index, lag_seconds in enumerate(lags):
            rows.append(
                {
                    "measurement_domain": DOMAINS[domain],
                    "observable": observable,
                    "lag_index": lag_index,
                    "lag_seconds": lag_seconds,
                    "mean_autocorrelation": mean[lag_index],
                    "standard_error_across_paths": se[lag_index],
                    "normal_95_lower": mean[lag_index] - 1.96 * se[lag_index],
                    "normal_95_upper": mean[lag_index] + 1.96 * se[lag_index],
                    "effective_pairs_per_book_member": production["returns"].shape[2] - lag_index,
                    "software_version": VERSION,
                }
            )
    write_csv(data, list(rows[0]), rows)


def _load_panel_configurations() -> list[dict[str, object]]:
    paths = sorted(PANEL_CONFIG_DIRECTORY.glob("figure-13?.json"))
    panels = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if [panel["panel_id"] for panel in panels] != list("abcdef"):
        raise ValueError("Figure 13 requires panel configurations a through f")
    return panels


def _atomic_save_png(image: Image.Image, target: Path, dpi: int) -> None:
    STAGING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary = STAGING_DIRECTORY / f"{target.stem}-{uuid.uuid4().hex}.tmp{target.suffix}"
    try:
        image.save(temporary, format="PNG", dpi=(dpi, dpi))
        sync_completed_file(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
        try:
            STAGING_DIRECTORY.rmdir()
        except OSError:
            pass


def _atomic_write_pdf(writer: PdfWriter, target: Path) -> None:
    STAGING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary = STAGING_DIRECTORY / f"{target.stem}-{uuid.uuid4().hex}.tmp{target.suffix}"
    try:
        with temporary.open("wb") as handle:
            writer.write(handle)
        sync_completed_file(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
        try:
            STAGING_DIRECTORY.rmdir()
        except OSError:
            pass


def _assemble_png(panels: list[dict[str, object]], configuration: dict[str, object]) -> None:
    figure_config = configuration["figure"]
    panel_width, panel_height = tuple(figure_config["standalone_png_pixels"])
    canvas = Image.new("RGB", tuple(figure_config["assembled_png_pixels"]), "white")
    for index, panel in enumerate(panels):
        _, png, _ = _panel_paths(panel)
        with Image.open(png) as source:
            if source.size != (panel_width, panel_height):
                raise ValueError("standalone panel PNG has unexpected dimensions")
            canvas.paste(source.convert("RGB"), ((index % 3) * panel_width, (index // 3) * panel_height))
    draw = ImageDraw.Draw(canvas)
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    font = ImageFont.truetype(str(font_path), 42) if font_path.is_file() else ImageFont.load_default()
    for index, panel in enumerate(panels):
        draw.text(
            ((index % 3) * panel_width + 18, (index // 3) * panel_height + 12),
            f"({panel['panel_id']})",
            fill="black",
            font=font,
        )
    _atomic_save_png(canvas, FIGURE_STEM.with_suffix(".png"), int(figure_config["png_dpi"]))


def _assemble_pdf(panels: list[dict[str, object]], configuration: dict[str, object]) -> None:
    figure_config = configuration["figure"]
    width_points = float(figure_config["assembled_canvas_inches"][0]) * 72.0
    height_points = float(figure_config["assembled_canvas_inches"][1]) * 72.0
    panel_width = float(figure_config["standalone_canvas_inches"][0]) * 72.0
    panel_height = float(figure_config["standalone_canvas_inches"][1]) * 72.0
    page = PageObject.create_blank_page(width=width_points, height=height_points)
    for index, panel in enumerate(panels):
        pdf, _, _ = _panel_paths(panel)
        source = PdfReader(str(pdf)).pages[0]
        x = (index % 3) * panel_width
        y = height_points - (index // 3 + 1) * panel_height
        page.merge_translated_page(source, x, y, over=True)

    overlay_figure = plt.figure(figsize=tuple(figure_config["assembled_canvas_inches"]))
    overlay_figure.patch.set_alpha(0.0)
    for index, panel in enumerate(panels):
        x = ((index % 3) * 4.0 + 0.18) / 12.0
        y = 1.0 - ((index // 3) * 4.0 + 0.18) / 8.0
        overlay_figure.text(x, y, f"({panel['panel_id']})", fontsize=11.0, fontweight="bold", va="top")
    STAGING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    overlay_path = STAGING_DIRECTORY / f"figure-13-labels-{uuid.uuid4().hex}.pdf"
    try:
        overlay_figure.savefig(overlay_path, format="pdf", transparent=True)
        plt.close(overlay_figure)
        page.merge_page(PdfReader(str(overlay_path)).pages[0], over=True)
        writer = PdfWriter()
        writer.add_page(page)
        writer.add_metadata({"/Creator": "correlation-emergence-v2.1.0"})
        _atomic_write_pdf(writer, FIGURE_STEM.with_suffix(".pdf"))
    finally:
        plt.close(overlay_figure)
        overlay_path.unlink(missing_ok=True)
        try:
            STAGING_DIRECTORY.rmdir()
        except OSError:
            pass


def _render_panels(
    production: dict[str, object],
    master: dict[str, np.ndarray | float],
    configuration: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    panels = _load_panel_configurations()
    for panel in panels:
        domain = 0 if panel["measurement_domain"] == DOMAINS[0] else 1
        if panel["panel_type"] == "price_returns":
            _plot_price_panel(panel, domain, production, master, configuration)
        elif panel["panel_type"] == "distribution_qq":
            _plot_distribution_panel(panel, domain, production, configuration)
        elif panel["panel_type"] == "acf_nested":
            _plot_acf_panel(panel, domain, production, configuration)
        else:
            raise ValueError(f"unknown Figure 13 panel type: {panel['panel_type']}")
    _assemble_png(panels, configuration)
    _assemble_pdf(panels, configuration)
    manifest = []
    for panel in panels:
        pdf, png, data = _panel_paths(panel)
        config_path = PANEL_CONFIG_DIRECTORY / f"figure-13{panel['panel_id']}.json"
        manifest.append(
            {
                "panel_id": panel["panel_id"],
                "measurement_domain": panel["measurement_domain"],
                "panel_type": panel["panel_type"],
                "source_config": str(config_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "source_config_sha256": _sha256(config_path),
                "data_path": str(data.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "data_sha256": _sha256(data),
                "pdf_path": str(pdf.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "pdf_sha256": _sha256(pdf),
                "png_path": str(png.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "png_sha256": _sha256(png),
                "software_version": VERSION,
            }
        )
    write_csv(PANEL_MANIFEST_PATH, list(manifest[0]), manifest)
    return panels, manifest


def _write_scientific_outputs(
    designs: dict[str, dict[str, object]],
    production_id: str,
    stability_rows: list[dict[str, object]],
    master: dict[str, np.ndarray | float],
    configuration: dict[str, object],
) -> None:
    production = designs[production_id]
    maximum_lag = int(configuration["master_experiment"]["autocorrelation_maximum_lag"])
    interval = (
        int(configuration["master_experiment"]["price_diagnostic_stride_steps"])
        * float(configuration["model"]["operational_step_seconds"])
    )
    sampling_rows = []
    for design in designs.values():
        for domain, domain_name in enumerate(DOMAINS):
            tail_count = int(np.sum(np.abs(design["standardized"][domain]) > 3.0))
            sampling_rows.append(
                {
                    "design_id": design["design_id"],
                    "measurement_domain": domain_name,
                    "paths": design["paths"],
                    "operational_steps": design["steps"],
                    "minimum_events_per_path_book": design["minimum_events_per_path_book"],
                    "mean_events_per_path_book": design["mean_events_per_path_book"],
                    "maximum_events_per_path_book": design["maximum_events_per_path_book"],
                    "terminal_event_margin_steps": design["terminal_margin"],
                    "five_second_return_count": design["standardized"][domain].size,
                    "maximum_lag": maximum_lag,
                    "effective_pairs_per_book_at_maximum_lag": design["effective_pairs_at_maximum_lag"],
                    "extreme_tail_count_abs_z_gt_3": tail_count,
                    "extreme_tail_claim": "eligible" if tail_count >= int(configuration["stability"]["minimum_extreme_tail_observations"]) else "omitted_insufficient_count",
                    "operational_input_correlation": design["input_correlation"],
                    "selected_for_production": design["design_id"] == production_id,
                    "software_version": VERSION,
                }
            )
    write_csv(SAMPLING_PATH, list(sampling_rows[0]), sampling_rows)
    write_csv(STABILITY_PATH, list(stability_rows[0]), stability_rows)

    sensitivity_rows = []
    for domain, domain_name in enumerate(DOMAINS):
        for convention, convention_name in enumerate(CONVENTIONS):
            for lag in range(maximum_lag + 1):
                sensitivity_rows.append(
                    {
                        "measurement_domain": domain_name,
                        "sign_convention": convention_name,
                        "lag_index": lag,
                        "lag_seconds": lag * interval,
                        "mean_signed_flow_autocorrelation": production["flow_mean"][domain, convention, lag],
                        "standard_error_across_paths": production["flow_se"][domain, convention, lag],
                        "primary_figure_convention": convention == 0,
                        "software_version": VERSION,
                    }
                )
    write_csv(SENSITIVITY_PATH, list(sensitivity_rows[0]), sensitivity_rows)

    summary_rows = [
        {
            "result_label": "figure_13_current_model_stylised_facts_verified",
            "production_design": production_id,
            "paths": production["paths"],
            "operational_steps": production["steps"],
            "minimum_events_per_path_book": production["minimum_events_per_path_book"],
            "mean_events_per_path_book": production["mean_events_per_path_book"],
            "maximum_events_per_path_book": production["maximum_events_per_path_book"],
            "representative_master_path_index": production["representative_master_index"],
            "displayed_book_index": int(configuration["master_experiment"]["displayed_book"]),
            "row_1": DOMAINS[0],
            "row_2": DOMAINS[1],
            "return_estimand": "five_second_log_mid_increment",
            "micro_price_constructed": False,
            "primary_order_flow": "five_second_declared_aggressor_signed_market_order_count",
            "order_sign_persistence_status": "declared_finite_markov_input_not_endogenous_result",
            "empirical_row_claimed": False,
            "model_parameter_refit": False,
            "maximum_market_order_mass_error": master["maximum_mass_error"],
            "minimum_execution_side_product": master["minimum_execution_side_product"],
            "software_version": VERSION,
        }
    ]
    write_csv(SUMMARY_PATH, list(summary_rows[0]), summary_rows)
    path_indices = np.asarray(production["path_indices"])
    steps = int(production["steps"])
    _atomic_save_npz(
        ARCHIVE_PATH,
        master_path_indices=path_indices,
        operational_times_seconds=np.asarray(master["times"])[: steps + 1],
        operational_prices=np.asarray(production["operational_prices"]),
        calendar_prices=np.asarray(production["calendar_prices"]),
        calendar_operational_indices=np.asarray(master["calendar_indices"])[path_indices, : steps + 1],
        declared_event_arrivals=np.asarray(master["arrivals"])[path_indices, :, : steps + 1],
        declared_ground_truth_signs_by_step=np.asarray(master["declared_signs"])[path_indices, :, : steps + 1],
        quote_midpoint_signs_by_step=np.asarray(master["quote_signs"])[path_indices, :, : steps + 1],
        legacy_tick_rule_signs_by_step=np.asarray(master["tick_signs"])[path_indices, :, : steps + 1],
        diagnostic_sample_indices=np.asarray(production["sample_indices"]),
        five_second_log_mid_increments=np.asarray(production["returns"]),
        five_second_signed_flows=np.asarray(production["binned_flows"]),
        return_autocorrelation_members=np.asarray(production["return_members"]),
        absolute_return_autocorrelation_members=np.asarray(production["absolute_members"]),
        signed_flow_autocorrelation_members=np.asarray(production["flow_members"]),
        standardized_returns=np.asarray(production["standardized"]),
        histogram_edges=np.asarray(production["histogram_edges"]),
        histogram_density=np.asarray(production["histogram_density"]),
        normal_density=np.asarray(production["normal_density"]),
        qq_probabilities=np.asarray(production["probabilities"]),
        normal_quantiles=np.asarray(production["normal_quantiles"]),
        sample_quantiles=np.asarray(production["sample_quantiles"]),
        representative_local_index=np.asarray([production["representative_local_index"]]),
        representative_master_index=np.asarray([production["representative_master_index"]]),
    )


def _check(identifier: str, claim: str, observed: object, criterion: str, passed: bool) -> dict[str, object]:
    if isinstance(observed, (dict, list, tuple, np.ndarray)):
        observed = json.dumps(np.asarray(observed).tolist() if isinstance(observed, np.ndarray) else observed, sort_keys=True)
    return {
        "check_id": identifier,
        "claim": claim,
        "observed": observed,
        "criterion": criterion,
        "status": "Verified" if passed else "Failed",
        "software_version": VERSION,
    }


def _verification_rows(
    designs: dict[str, dict[str, object]],
    production_id: str,
    stability_rows: list[dict[str, object]],
    panels: list[dict[str, object]],
    manifest: list[dict[str, object]],
    master: dict[str, np.ndarray | float],
    configuration: dict[str, object],
) -> list[dict[str, object]]:
    checks = []
    add = lambda claim, observed, criterion, passed: checks.append(
        _check(f"F13-{len(checks) + 1:02d}", claim, observed, criterion, passed)
    )
    scientific_inputs = _scientific_accepted_inputs(configuration)
    add("accepted inputs", accepted_input_errors(scientific_inputs), "no errors", not accepted_input_errors(scientific_inputs))
    add("master path count", np.asarray(master["operational_prices"]).shape[0], "16", np.asarray(master["operational_prices"]).shape[0] == 16)
    add("market-order mass error", master["maximum_mass_error"], "<= 1e-14", float(master["maximum_mass_error"]) <= 1e-14)
    add("execution price side", master["minimum_execution_side_product"], "> 0", float(master["minimum_execution_side_product"]) > 0.0)
    add("boundary candidates", master["maximum_boundary_candidates"], "1", int(master["maximum_boundary_candidates"]) == 1)
    add("minimum boundary edge", master["minimum_edge_distance"], "> 7", float(master["minimum_edge_distance"]) > 7.0)
    experiment = configuration["master_experiment"]
    start = int(experiment["event_start_operational_step"])
    last = int(np.asarray(master["operational_prices"]).shape[1] - 1) - int(
        experiment["terminal_event_margin_steps"]
    )
    primitive = np.asarray(master["primitive_arrivals"])
    active = primitive[:, :, start : last + 1]
    active_seconds = active.shape[-1] * float(
        configuration["model"]["operational_step_seconds"]
    )
    realised_rate = float(np.sum(active) / (primitive.shape[0] * 2 * active_seconds))
    target_rate = float(experiment["arrival_probability_per_step"]) / float(
        configuration["model"]["operational_step_seconds"]
    )
    usable = active.shape[-1] - active.shape[-1] % 10
    binned = active[:, :, :usable].reshape(-1, 10).sum(axis=1)
    fano = float(np.var(binned, ddof=1) / np.mean(binned))
    move_ratio = float(
        np.median(np.asarray(master["immediate_moves"]))
        / np.std(np.asarray(master["background_increments"]), ddof=1)
    )
    add("background event quantity", experiment["event_quantity"], "0.00020", float(experiment["event_quantity"]) == 0.00020)
    add("pooled realised arrival rate", realised_rate, "within 5% of 0.1 s^-1", abs(realised_rate / target_rate - 1.0) <= 0.05)
    add("five-second arrival-count Fano factor", fano, "within [0.75,1.15]", 0.75 <= fano <= 1.15)
    add("event move to background innovation scale", move_ratio, "within [0.5,2.0]", 0.5 <= move_ratio <= 2.0)
    production = designs[production_id]
    for domain, name in enumerate(DOMAINS):
        curve = np.asarray(production["return_mean"])[domain]
        maximum = float(np.max(np.abs(curve[2:9])))
        even = float(np.mean(curve[[2, 4, 6, 8]]))
        odd = float(np.mean(curve[[3, 5, 7]]))
        add(f"{name} return ACF lags 2-8", maximum, "maximum <= 0.15", maximum <= 0.15)
        add(f"{name} even/odd alias difference", abs(even - odd), "<= 0.10", abs(even - odd) <= 0.10)
    calendar_indices = np.asarray(master["calendar_indices"])
    query = np.arange(calendar_indices.shape[1])[None, :, None]
    add("previous-refresh observation never looks ahead", int(np.max(calendar_indices - query)), "<= 0", int(np.max(calendar_indices - query)) <= 0)
    for design_id, design in designs.items():
        expected_count = int(design["paths"]) * 2 * (np.asarray(design["sample_indices"]).size - 1)
        add(f"{design_id} pooled return count", design["standardized"][0].size, str(expected_count), design["standardized"][0].size == expected_count)
        add(f"{design_id} terminal event margin", design["terminal_margin"], "149", int(design["terminal_margin"]) == 149)
        add(f"{design_id} input correlation", design["input_correlation"], "absolute <= 0.05", abs(float(design["input_correlation"])) <= 0.05)
        for domain in range(2):
            values = np.asarray(design["standardized"][domain])
            add(f"{design_id} {DOMAINS[domain]} standardized mean", float(np.mean(values)), "absolute <= 1e-14", abs(float(np.mean(values))) <= 1e-14)
            add(f"{design_id} {DOMAINS[domain]} standardized variance", float(np.var(values, ddof=1)), "within 1e-14 of 1", abs(float(np.var(values, ddof=1)) - 1.0) <= 1e-14)
            width = float(design["histogram_edges"][domain, 1] - design["histogram_edges"][domain, 0])
            mass = float(np.sum(design["histogram_density"][domain]) * width)
            add(f"{design_id} {DOMAINS[domain]} histogram mass", mass, "within 1e-14 of 1", abs(mass - 1.0) <= 1e-14)
            add(f"{design_id} {DOMAINS[domain]} QQ monotonic", bool(np.all(np.diff(design["sample_quantiles"][domain]) >= 0)), "true", bool(np.all(np.diff(design["sample_quantiles"][domain]) >= 0)))
            add(f"{design_id} {DOMAINS[domain]} return ACF C0", design["return_mean"][domain, 0], "1", abs(float(design["return_mean"][domain, 0]) - 1.0) <= 1e-15)
            add(f"{design_id} {DOMAINS[domain]} absolute-return ACF C0", design["absolute_mean"][domain, 0], "1", abs(float(design["absolute_mean"][domain, 0]) - 1.0) <= 1e-15)
            add(f"{design_id} {DOMAINS[domain]} signed-flow ACF C0", design["flow_mean"][domain, 0, 0], "1", abs(float(design["flow_mean"][domain, 0, 0]) - 1.0) <= 1e-15)
    add("registered stability comparisons", sum(row["status"] == "Failed" for row in stability_rows), "0 failures; extension triggers retained", all(row["status"] in {"Verified", "ExtensionTriggered"} for row in stability_rows))
    add("production design", production_id, "registered sufficient design", production_id in {"longer_paths", "both_doubled", "extended_horizon", "extended_both", "extended_2_horizon", "extended_2_both"})
    add("standalone panel count", len(panels), "6", len(panels) == 6)
    add("unique panel identities", len({row["panel_id"] for row in manifest}), "6", len({row["panel_id"] for row in manifest}) == 6)
    for field in ("source_config_sha256", "data_sha256", "pdf_sha256", "png_sha256"):
        add(f"unique {field}", len({row[field] for row in manifest}), "6", len({row[field] for row in manifest}) == 6)
    for panel in panels:
        pdf, png, data = _panel_paths(panel)
        with Image.open(png) as image:
            size = image.size
        add(f"panel {panel['panel_id']} PNG dimensions", size, "1200 x 1200", size == (1200, 1200))
        reader = PdfReader(str(pdf))
        media = reader.pages[0].mediabox
        dimensions = (round(float(media.width)), round(float(media.height)))
        add(f"panel {panel['panel_id']} PDF page", dimensions, "288 x 288 points", len(reader.pages) == 1 and dimensions == (288, 288))
        add(f"panel {panel['panel_id']} data", data.is_file(), "present", data.is_file())
        layout = LAYOUT_RESULTS[str(panel["panel_id"])]
        add(f"panel {panel['panel_id']} text lies inside canvas", layout[0], "true", bool(layout[0]))
        add(f"panel {panel['panel_id']} inter-axis text collisions", layout[1], "0", int(layout[1]) == 0)
    with Image.open(FIGURE_STEM.with_suffix(".png")) as image:
        assembled_size = image.size
    add("assembled PNG dimensions", assembled_size, "3600 x 2400", assembled_size == (3600, 2400))
    reader = PdfReader(str(FIGURE_STEM.with_suffix(".pdf")))
    media = reader.pages[0].mediabox
    assembled_pdf = (round(float(media.width)), round(float(media.height)))
    add("assembled PDF page", assembled_pdf, "864 x 576 points", len(reader.pages) == 1 and assembled_pdf == (864, 576))
    add("legacy raster used as data", configuration["scientific_boundary"]["legacy_raster_used_as_data"], "false", not configuration["scientific_boundary"]["legacy_raster_used_as_data"])
    add("empirical row claimed", configuration["scientific_boundary"]["empirical_row_claimed"], "false", not configuration["scientific_boundary"]["empirical_row_claimed"])
    add("micro-price constructed", configuration["scientific_boundary"]["micro_price_constructed"], "false", not configuration["scientific_boundary"]["micro_price_constructed"])
    add("model parameter refit", configuration["scientific_boundary"]["model_parameter_refit"], "false", not configuration["scientific_boundary"]["model_parameter_refit"])
    scientific_inputs = _scientific_accepted_inputs(configuration)
    add("accepted inputs unchanged after run", accepted_input_errors(scientific_inputs), "no errors", not accepted_input_errors(scientific_inputs))
    return checks


def main() -> int:
    remove_orphaned_figure_staging_files()
    remove_orphaned_output_staging_files()
    configuration = _load_configuration()
    errors = accepted_input_errors(_scientific_accepted_inputs(configuration))
    if errors:
        raise RuntimeError(f"accepted Figure 13 inputs changed: {errors}")
    horizons = sorted(
        {int(design["operational_steps"]) for design in configuration["designs"]}
    )
    masters = {
        steps: _run_master(configuration, steps=steps)
        for steps in horizons
    }
    designs = {
        str(design["design_id"]): _analyse_design(
            design, masters[int(design["operational_steps"])], configuration
        )
        for design in configuration["designs"]
    }
    stability_rows, candidate_pass = _stability_rows(designs, configuration)
    production_id = _select_production_design(designs, candidate_pass, configuration)
    production_master = masters[int(designs[production_id]["steps"])]
    _write_scientific_outputs(
        designs, production_id, stability_rows, production_master, configuration
    )
    panels, manifest = _render_panels(
        designs[production_id], production_master, configuration
    )
    checks = _verification_rows(
        designs,
        production_id,
        stability_rows,
        panels,
        manifest,
        production_master,
        configuration,
    )
    write_csv(CHECK_PATH, list(checks[0]), checks)
    failures = [row for row in checks if row["status"] != "Verified"]
    print(
        f"Figure 13 checks: {len(checks) - len(failures)}/{len(checks)} verified; "
        f"production design {production_id}."
    )
    if failures:
        for row in failures:
            print(f"  FAILED {row['check_id']}: {row['claim']} ({row['observed']})")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
