"""Run the v2.1.0 long-memory clock and paired-impact extension."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib-cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from functions.figure_io import atomic_savefig
from functions.io_utils import write_csv
from functions.observation import (
    mittag_leffler_refresh_path_from_uniforms,
    mittag_leffler_wait_laplace,
    mittag_leffler_waits_from_uniforms,
    subordinate_two_book_previous_refresh,
    tempered_mittag_leffler_mean_wait,
    tempered_mittag_leffler_refresh_path_from_uniforms,
    tempered_mittag_leffler_wait_laplace,
    tempered_mittag_leffler_waits_from_uniforms,
)
from functions.stylised_facts import (
    aggregate_book_members,
    fixed_histogram,
    fixed_normal_qq,
    member_autocorrelations,
    standardize_sample,
)
from functions.path_diagnostics import increment_autocorrelation


VERSION = "2.1.0"
CONFIG_PATH = PROJECT_ROOT / "config/config-v2.1.0-clock-impact.json"
DOMAIN_IDS = (
    "operational_gaussian",
    "poisson_previous_refresh",
    "mittag_leffler_previous_refresh",
    "tempered_mittag_leffler_previous_refresh",
)
DOMAIN_SHORT = ("Operational", "Poisson", "Mittag-Leffler", "Tempered ML")
DOMAIN_COLOURS = ("#225ea8", "#d95f0e", "#756bb1", "#238b45")
FROZEN_SOURCE_V1_SHA256 = "48eea98a6fb084d6ecc397bede4c107a44cae947e16271d66a7041e2997afb5a"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_module(name: str, relative_path: str):
    path = PROJECT_ROOT / relative_path
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _open_uniforms(rng: np.random.Generator, shape: tuple[int, ...]) -> np.ndarray:
    values = rng.random(shape)
    return np.clip(values, np.nextafter(0.0, 1.0), np.nextafter(1.0, 0.0))


def _renewal_pairs(
    row: dict[str, object],
    *,
    paths: int,
    horizon: float,
    candidates: int,
    seed: int,
    purpose: str,
):
    clock_type = str(row["clock"])
    if clock_type not in {"mittag_leffler", "tempered_mittag_leffler"}:
        raise ValueError("renewal-pair construction requires a Mittag-Leffler row")
    pairs = []
    for path in range(paths):
        pair = []
        for book in range(2):
            law_code = 31 if clock_type == "mittag_leffler" else 37
            rng = np.random.default_rng(
                np.random.SeedSequence([seed, law_code, path, book])
            )
            streams = _open_uniforms(rng, (4, candidates))
            common = {
                "beta": float(row["beta"]),
                "scale_seconds": float(row["scale_seconds"]),
                "horizon": horizon,
                "stream_id": f"v21-{purpose}-{clock_type}-p{path:02d}-b{book + 1}",
            }
            if clock_type == "mittag_leffler":
                clock = mittag_leffler_refresh_path_from_uniforms(
                    streams[0], streams[1], streams[2], **common
                )
            else:
                clock = tempered_mittag_leffler_refresh_path_from_uniforms(
                    streams[0],
                    streams[1],
                    streams[2],
                    streams[3],
                    tempering_rate_per_second=float(row["tempering_rate_per_second"]),
                    **common,
                )
            pair.append(clock)
        pairs.append(tuple(pair))
    return tuple(pairs)


def _clock_rows(pairs_by_domain: dict[str, tuple[tuple[object, object], ...]]):
    rows: list[dict[str, object]] = []
    for domain, pairs in pairs_by_domain.items():
        for path, pair in enumerate(pairs):
            for book, clock in enumerate(pair):
                waits = np.asarray(clock.waiting_intervals)
                rows.append(
                    {
                        "measurement_domain": domain,
                        "path_index": path,
                        "book_index": book,
                        "stream_id": clock.stream_id,
                        "retained_waits": waits.size,
                        "realised_mean_wait_seconds": float(np.mean(waits)),
                        "realised_median_wait_seconds": float(np.median(waits)),
                        "realised_q95_wait_seconds": float(np.quantile(waits, 0.95)),
                        "realised_max_wait_seconds": float(np.max(waits)),
                        "supported_horizon_seconds": float(clock.supported_horizon),
                        "software_version": VERSION,
                    }
                )
    return rows


def _acf_summary(series: np.ndarray, maximum_lag: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Aggregate defined path/book ACFs without inventing values for constants."""

    values = np.asarray(series, dtype=float)
    members = np.full((values.shape[0], 2, maximum_lag + 1), np.nan)
    for path in range(values.shape[0]):
        for book in range(2):
            vector = values[path, :, book]
            if np.std(vector) <= 0.0:
                continue
            members[path, book, 0] = 1.0
            for lag in range(1, maximum_lag + 1):
                left = vector[:-lag]
                right = vector[lag:]
                left = left - np.mean(left)
                right = right - np.mean(right)
                scale = float(np.sqrt(np.dot(left, left) * np.dot(right, right)))
                if scale > 0.0:
                    members[path, book, lag] = float(np.dot(left, right) / scale)
    path_curves = np.nanmean(members, axis=1)
    support = np.sum(np.isfinite(path_curves), axis=0)
    if np.any(support < 2):
        raise ValueError("fewer than two independent path ACFs are defined")
    mean = np.nanmean(path_curves, axis=0)
    se = np.nanstd(path_curves, axis=0, ddof=1) / np.sqrt(support)
    return mean, se, support


def _figure13(configuration: dict[str, object], fig13_module):
    base_path = PROJECT_ROOT / str(configuration["figure_13_base_configuration"])
    base = json.loads(base_path.read_text(encoding="utf-8"))
    base["master_experiment"]["sign_process"] = configuration["figure_13"][
        "sign_process"
    ]
    steps = int(base["master_experiment"]["total_operational_steps"])
    master = fig13_module._run_master(base, steps=steps)
    operational_times = np.asarray(master["times"])
    operational_prices = np.asarray(master["operational_prices"])
    operational_flows = np.asarray(master["operational_cumulative_flows"])
    paths = operational_prices.shape[0]
    rows = configuration["figure_13"]["rows"]
    candidates = int(configuration["figure_13"]["clock_candidates_per_book_path"])
    seed = int(configuration["figure_13"]["clock_seed"])
    renewal = {
        DOMAIN_IDS[index]: _renewal_pairs(
            rows[index],
            paths=paths,
            horizon=float(operational_times[-1]),
            candidates=candidates,
            seed=seed,
            purpose="stylised",
        )
        for index in (2, 3)
    }

    price_domains = np.empty((4,) + operational_prices.shape, dtype=float)
    price_domains[0] = operational_prices
    price_domains[1] = np.asarray(master["calendar_prices"])
    index_domains = np.empty((4, paths, operational_times.size, 2), dtype=np.int64)
    direct = np.arange(operational_times.size, dtype=np.int64)
    index_domains[0] = np.broadcast_to(direct[None, :, None], index_domains[0].shape)
    index_domains[1] = np.asarray(master["calendar_indices"])

    flow_domains = np.empty((4,) + operational_flows.shape, dtype=float)
    flow_domains[0] = operational_flows
    flow_domains[1] = np.asarray(master["calendar_cumulative_flows"])
    for domain in (2, 3):
        pairs = renewal[DOMAIN_IDS[domain]]
        for path in range(paths):
            sampled = subordinate_two_book_previous_refresh(
                operational_times,
                operational_prices[path],
                pairs[path],
                operational_times,
            )
            price_domains[domain, path] = sampled.prices
            index_domains[domain, path] = sampled.operational_indices
            for convention in range(operational_flows.shape[1]):
                cumulative = operational_flows[path, convention]
                for book in range(2):
                    flow_domains[domain, path, convention, :, book] = cumulative[
                        sampled.operational_indices[:, book], book
                    ]

    experiment = base["master_experiment"]
    start = int(experiment["price_diagnostic_start_operational_step"])
    stride = int(experiment["price_diagnostic_stride_steps"])
    sample_indices = np.arange(start, steps + 1, stride, dtype=int)
    returns = np.diff(price_domains[:, :, sample_indices, :], axis=2)
    binned_flows = np.diff(flow_domains[:, :, 0, sample_indices, :], axis=2)
    maximum_lag = int(experiment["autocorrelation_maximum_lag"])

    return_mean = np.empty((4, maximum_lag + 1))
    return_se = np.empty_like(return_mean)
    absolute_mean = np.empty_like(return_mean)
    absolute_se = np.empty_like(return_mean)
    flow_mean = np.empty_like(return_mean)
    flow_se = np.empty_like(return_mean)
    standardized: list[np.ndarray] = []
    histogram_centres: list[np.ndarray] = []
    histogram_density: list[np.ndarray] = []
    normal_density: list[np.ndarray] = []
    normal_quantiles: list[np.ndarray] = []
    sample_quantiles: list[np.ndarray] = []
    for domain in range(4):
        return_mean[domain], return_se[domain], _ = _acf_summary(
            returns[domain], maximum_lag
        )
        absolute_mean[domain], absolute_se[domain], _ = _acf_summary(
            np.abs(returns[domain]), maximum_lag
        )
        flow_mean[domain], flow_se[domain], _ = _acf_summary(
            binned_flows[domain], maximum_lag
        )
        values, _, _ = standardize_sample(returns[domain].ravel())
        support = configuration["figure_13"]["histogram_supports"][domain]
        _, centres, density, normal = fixed_histogram(
            values,
            lower=float(support[0]),
            upper=float(support[1]),
            bins=int(configuration["figure_13"]["histogram_bins"]),
        )
        _, normal_q, sample_q = fixed_normal_qq(
            values, lower_probability=0.01, upper_probability=0.99, count=51
        )
        standardized.append(values)
        histogram_centres.append(centres)
        histogram_density.append(density)
        normal_density.append(normal)
        normal_quantiles.append(normal_q)
        sample_quantiles.append(sample_q)

    representative = int(configuration["figure_13"]["representative_path_index"])
    observed_times = operational_times[sample_indices]
    figure, axes = plt.subplots(4, 3, figsize=(13.2, 15.2))
    panel_letters = iter("abcdefghijkl")
    panel_files: list[tuple[str, str, str, str]] = []

    def draw_price(axis, domain: int) -> None:
        for book, colour in enumerate(("#2166ac", "#b2182b")):
            axis.plot(
                observed_times,
                price_domains[domain, representative, sample_indices, book],
                color=colour,
                lw=1.0,
                label=f"Book {book + 1}",
            )
        axis.set_xlabel("Time [s]")
        axis.set_ylabel("Log-mid displacement")
        axis.legend(frameon=False, fontsize=7, ncol=2)

    def draw_distribution(axis, domain: int) -> None:
        axis.plot(
            histogram_centres[domain],
            histogram_density[domain],
            color=DOMAIN_COLOURS[domain],
            lw=1.6,
            label="Model",
        )
        axis.plot(
            histogram_centres[domain],
            normal_density[domain],
            color="#444444",
            lw=1.0,
            ls="--",
            label="Normal",
        )
        axis.set_yscale("log")
        axis.set_ylim(
            2e-4,
            max(
                2.0,
                1.6
                * float(
                    max(
                        np.max(histogram_density[domain]),
                        np.max(normal_density[domain]),
                    )
                ),
            ),
        )
        axis.set_xlabel("Standardised 5 s return")
        axis.set_ylabel("Density")
        axis.legend(frameon=False, fontsize=7, loc="lower left")
        inset = axis.inset_axes([0.57, 0.53, 0.39, 0.40])
        inset.plot(normal_quantiles[domain], sample_quantiles[domain], color=DOMAIN_COLOURS[domain], lw=1.1)
        low = min(float(np.min(normal_quantiles[domain])), float(np.min(sample_quantiles[domain])))
        high = max(float(np.max(normal_quantiles[domain])), float(np.max(sample_quantiles[domain])))
        inset.plot([low, high], [low, high], color="#777777", ls=":", lw=0.8)
        inset.text(
            0.03,
            0.96,
            "Normal Q-Q",
            transform=inset.transAxes,
            fontsize=7,
            va="top",
        )
        inset.tick_params(labelsize=6)

    def draw_acf(axis, domain: int) -> None:
        lags = np.arange(maximum_lag + 1)
        axis.plot(lags[1:], return_mean[domain, 1:], color="#2166ac", lw=1.35, label="Returns")
        axis.plot(lags[1:], absolute_mean[domain, 1:], color="#b2182b", lw=1.35, label="|Returns|")
        axis.plot(lags[1:], flow_mean[domain, 1:], color="#238b45", lw=1.5, label="Order flow")
        axis.axhline(0.0, color="#777777", lw=0.7)
        axis.set_xlabel("Lag [5 s bins]")
        axis.set_ylabel("Autocorrelation")
        axis.legend(frameon=False, fontsize=7)

    drawing = (draw_price, draw_distribution, draw_acf)
    panel_kinds = ("price-returns", "distribution-qq", "acf")
    for domain in range(4):
        for column in range(3):
            axis = axes[domain, column]
            letter = next(panel_letters)
            drawing[column](axis, domain)
            axis.grid(alpha=0.17, linewidth=0.5)
            axis.set_title(f"({letter}) {DOMAIN_SHORT[domain]}: {panel_kinds[column].replace('-', ' ')}", loc="left", fontsize=10)

            standalone, standalone_axis = plt.subplots(figsize=(4.8, 4.3))
            drawing[column](standalone_axis, domain)
            standalone_axis.grid(alpha=0.17, linewidth=0.5)
            standalone_axis.set_title(f"({letter}) {DOMAIN_SHORT[domain]}: {panel_kinds[column].replace('-', ' ')}", loc="left", fontsize=10)
            standalone.tight_layout()
            stem = PROJECT_ROOT / "figures" / f"figure-13{letter}-{DOMAIN_IDS[domain].replace('_', '-')}-{panel_kinds[column]}-v2"
            atomic_savefig(standalone, stem.with_suffix(".png"), dpi=300)
            atomic_savefig(standalone, stem.with_suffix(".pdf"), metadata={"CreationDate": None, "ModDate": None})
            plt.close(standalone)
            panel_files.append((letter, DOMAIN_IDS[domain], panel_kinds[column], stem.relative_to(PROJECT_ROOT).as_posix()))

    figure.suptitle(
        "Operational long-memory input and observation-clock morphology",
        fontsize=14,
        y=0.995,
    )
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.985))
    stem = PROJECT_ROOT / str(configuration["figure_13"]["output_stem"])
    atomic_savefig(figure, stem.with_suffix(".png"), dpi=300)
    atomic_savefig(figure, stem.with_suffix(".pdf"), metadata={"CreationDate": None, "ModDate": None})
    plt.close(figure)

    archive_path = PROJECT_ROOT / str(configuration["figure_13"]["archive"])
    np.savez_compressed(
        archive_path,
        operational_times_seconds=operational_times,
        sample_indices=sample_indices,
        domain_ids=np.asarray(DOMAIN_IDS),
        prices=price_domains,
        operational_indices=index_domains,
        returns=returns,
        declared_order_flow=binned_flows,
        return_acf_mean=return_mean,
        return_acf_se=return_se,
        absolute_return_acf_mean=absolute_mean,
        absolute_return_acf_se=absolute_se,
        order_flow_acf_mean=flow_mean,
        order_flow_acf_se=flow_se,
        declared_signs=np.asarray(master["declared_signs"]),
    )

    manifest_rows = []
    config_relative = "config/config-v2.1.0-clock-impact.json"
    config_hash = _sha256(PROJECT_ROOT / config_relative)
    archive_relative = archive_path.relative_to(PROJECT_ROOT).as_posix()
    archive_hash = _sha256(archive_path)
    for letter, domain, kind, panel_stem in panel_files:
        manifest_rows.append(
            {
                "panel_id": letter,
                "measurement_domain": domain,
                "panel_type": kind,
                "source_config": config_relative,
                "source_config_sha256": config_hash,
                "data_path": archive_relative,
                "data_sha256": archive_hash,
                "pdf_path": panel_stem + ".pdf",
                "pdf_sha256": _sha256(PROJECT_ROOT / (panel_stem + ".pdf")),
                "png_path": panel_stem + ".png",
                "png_sha256": _sha256(PROJECT_ROOT / (panel_stem + ".png")),
                "software_version": VERSION,
            }
        )
    write_csv(
        PROJECT_ROOT / "outputs/figure-13-observation-clock-panel-manifest-v2.1.csv",
        list(manifest_rows[0]),
        manifest_rows,
    )

    event_sign_acfs = []
    declared = np.asarray(master["declared_signs"])
    arrivals = np.asarray(master["arrivals"])
    for path in range(paths):
        for book in range(2):
            signs = declared[path, book, arrivals[path, book]]
            event_sign_acfs.append(increment_autocorrelation(signs, maximum_lag))
    event_sign_acf = np.mean(np.asarray(event_sign_acfs), axis=0)
    positive = np.flatnonzero(event_sign_acf[3:31] > 0.0) + 3
    slope = float(np.polyfit(np.log(positive), np.log(event_sign_acf[positive]), 1)[0])
    exact = all(
        np.array_equal(
            price_domains[domain, path, :, book],
            operational_prices[path, index_domains[domain, path, :, book], book],
        )
        for domain in range(4)
        for path in range(paths)
        for book in range(2)
    )
    zero_fractions = np.mean(np.isclose(returns, 0.0), axis=(1, 2, 3))
    return {
        "renewal_pairs": renewal,
        "event_sign_acf": event_sign_acf,
        "event_sign_slope": slope,
        "previous_refresh_exact": exact,
        "zero_return_fractions": zero_fractions,
        "representative_path": representative,
    }


def _impact_members(response: np.ndarray, impact_type: str) -> np.ndarray:
    if impact_type == "own":
        pair = np.stack((response[:, 0, :, :, :, 0], response[:, 1, :, :, :, 1]))
    else:
        pair = np.stack((response[:, 0, :, :, :, 1], response[:, 1, :, :, :, 0]))
    return np.mean(pair, axis=(0, 2))


def _meta_members(response: np.ndarray, impact_type: str) -> np.ndarray:
    if impact_type == "own":
        pair = np.stack((response[:, :, 0, :, :, :, 0], response[:, :, 1, :, :, :, 1]))
    else:
        pair = np.stack((response[:, :, 0, :, :, :, 1], response[:, :, 1, :, :, :, 0]))
    return np.mean(pair, axis=(0, 3))


def _extend_impacts(configuration: dict[str, object], single_module, meta_module):
    rows = configuration["figure_13"]["rows"]
    impact_cfg = configuration["figure_14"]
    candidates = int(impact_cfg["clock_candidates_per_book_path"])
    seed = int(impact_cfg["clock_seed"])

    single_cfg = single_module._load_configuration()
    single = single_module._run_experiment(single_cfg, write_outputs=False)
    s_exp = single_cfg["experiment"]
    s_times = np.arange(int(s_exp["total_operational_steps"]) + 1) * float(
        single_cfg["model"]["operational_step_seconds"]
    )
    s_paths = int(s_exp["paths"])
    s_pairs = {
        DOMAIN_IDS[index]: _renewal_pairs(
            rows[index],
            paths=s_paths,
            horizon=float(s_times[-1]),
            candidates=candidates,
            seed=seed,
            purpose="single-impact",
        )
        for index in (2, 3)
    }
    s_existing = np.asarray(single["responses"])
    s_response = np.empty(s_existing.shape[:3] + (4,) + s_existing.shape[4:])
    s_active = np.ones_like(s_response)
    s_response[:, :, :, :2] = s_existing
    s_active[:, :, :, :2] = np.asarray(single["active"])
    event_step = int(s_exp["event_operational_step"])
    lag_steps = np.rint(
        np.asarray(single["lags_seconds"])
        / float(single_cfg["model"]["operational_step_seconds"])
    ).astype(int)
    query = event_step + lag_steps
    for domain in (2, 3):
        for path in range(s_paths):
            control = subordinate_two_book_previous_refresh(
                s_times, single["control_prices"][path], s_pairs[DOMAIN_IDS[domain]][path], s_times
            )
            for event_book in range(2):
                for side_index, side in enumerate(s_exp["event_sides"]):
                    shocked = subordinate_two_book_previous_refresh(
                        s_times,
                        single["shocked_prices"][path, event_book, side_index],
                        s_pairs[DOMAIN_IDS[domain]][path],
                        s_times,
                    )
                    s_response[path, event_book, side_index, domain] = float(side) * (
                        shocked.prices[query] - control.prices[query]
                    )
                    s_active[path, event_book, side_index, domain] = (
                        control.operational_indices[query] >= event_step
                    ).astype(float)

    meta_cfg = meta_module._load_configuration()
    meta = meta_module._run_experiment(meta_cfg, write_outputs=False)
    control_prices = np.asarray(meta["control_prices"])
    shocked_prices = np.asarray(meta["shocked_prices"])
    m_exp = meta_cfg["experiment"]
    m_times = np.asarray(meta["operational_times_seconds"])
    m_paths = int(m_exp["paths"])
    m_pairs = {
        DOMAIN_IDS[index]: _renewal_pairs(
            rows[index],
            paths=m_paths,
            horizon=float(m_times[-1]),
            candidates=candidates,
            seed=seed + 1,
            purpose="meta-impact",
        )
        for index in (2, 3)
    }
    old_traj = np.asarray(meta["trajectory"])
    old_relax = np.asarray(meta["relaxation"])
    trajectory = np.empty(old_traj.shape[:4] + (4,) + old_traj.shape[5:])
    relaxation = np.empty(old_relax.shape[:4] + (4,) + old_relax.shape[5:])
    trajectory[:, :, :, :, :2] = old_traj
    relaxation[:, :, :, :, :2] = old_relax
    trajectory_active = np.ones_like(trajectory)
    relaxation_active = np.ones_like(relaxation)
    trajectory_active[:, :, :, :, :2] = np.asarray(meta["trajectory_active"])
    relaxation_active[:, :, :, :, :2] = np.asarray(meta["relaxation_active"])
    step_seconds = float(meta_cfg["model"]["operational_step_seconds"])
    post_steps = np.rint(np.asarray(meta["post_lags"]) / step_seconds).astype(int)
    schedules = m_exp["schedules"]
    for domain in (2, 3):
        for path in range(m_paths):
            control = subordinate_two_book_previous_refresh(
                m_times, control_prices[path], m_pairs[DOMAIN_IDS[domain]][path], m_times
            )
            for schedule_index, schedule in enumerate(schedules):
                child_steps = np.asarray(schedule["child_operational_steps"], dtype=int)
                relax_steps = child_steps[-1] + post_steps
                for event_book in range(2):
                    for side_index, side in enumerate(m_exp["event_sides"]):
                        shocked = subordinate_two_book_previous_refresh(
                            m_times,
                            shocked_prices[schedule_index, path, event_book, side_index],
                            m_pairs[DOMAIN_IDS[domain]][path],
                            m_times,
                        )
                        difference = float(side) * (shocked.prices - control.prices)
                        trajectory[schedule_index, path, event_book, side_index, domain] = difference[child_steps]
                        relaxation[schedule_index, path, event_book, side_index, domain] = difference[relax_steps]
                        trajectory_active[schedule_index, path, event_book, side_index, domain] = (
                            control.operational_indices[child_steps] >= child_steps[:, None]
                        ).astype(float)
                        relaxation_active[schedule_index, path, event_book, side_index, domain] = (
                            control.operational_indices[relax_steps] >= child_steps[-1]
                        ).astype(float)
    curve_rows: list[dict[str, object]] = []
    single_members = {}
    for impact_type in ("own", "cross"):
        members = _impact_members(s_response, impact_type)
        single_members[impact_type] = members
        for domain in range(4):
            mean = np.mean(members[:, domain], axis=0)
            se = np.std(members[:, domain], axis=0, ddof=1) / math.sqrt(s_paths)
            support = np.mean(
                _impact_members(s_active, impact_type)[:, domain], axis=0
            )
            for lag_index, lag in enumerate(single["lags_seconds"]):
                curve_rows.append(
                    {
                        "experiment": "single_trade",
                        "schedule_id": "not_applicable",
                        "impact_type": impact_type,
                        "measurement_domain": DOMAIN_IDS[domain],
                        "x_coordinate": "lag_seconds",
                        "x_value": float(lag),
                        "mean_signed_log_mid_impact": mean[lag_index],
                        "standard_error": se[lag_index],
                        "active_observation_fraction": support[lag_index],
                        "software_version": VERSION,
                    }
                )

    meta_relax_members = {}
    meta_traj_members = {}
    for impact_type in ("own", "cross"):
        meta_relax_members[impact_type] = _meta_members(relaxation, impact_type)
        meta_traj_members[impact_type] = _meta_members(trajectory, impact_type)
        for schedule_index, schedule in enumerate(schedules):
            for domain in range(4):
                for kind, members, x_values, coordinate in (
                    ("meta_order_trajectory", meta_traj_members[impact_type], np.arange(1, int(m_exp["children_per_meta_order"]) + 1) * float(m_exp["child_quantity"]), "cumulative_quantity"),
                    ("meta_order_relaxation", meta_relax_members[impact_type], np.asarray(meta["post_lags"]), "post_completion_lag_seconds"),
                ):
                    values = members[schedule_index, :, domain]
                    mean = np.mean(values, axis=0)
                    se = np.std(values, axis=0, ddof=1) / math.sqrt(m_paths)
                    for point, x_value in enumerate(x_values):
                        curve_rows.append(
                            {
                                "experiment": kind,
                                "schedule_id": schedule["schedule_id"],
                                "impact_type": impact_type,
                                "measurement_domain": DOMAIN_IDS[domain],
                                "x_coordinate": coordinate,
                                "x_value": float(x_value),
                                "mean_signed_log_mid_impact": mean[point],
                                "standard_error": se[point],
                                "active_observation_fraction": "see_archive",
                                "software_version": VERSION,
                            }
                        )

    curve_path = PROJECT_ROOT / str(impact_cfg["curve_output"])
    write_csv(curve_path, list(curve_rows[0]), curve_rows)
    archive_path = PROJECT_ROOT / str(impact_cfg["archive"])
    np.savez_compressed(
        archive_path,
        domain_ids=np.asarray(DOMAIN_IDS),
        single_lags_seconds=np.asarray(single["lags_seconds"]),
        single_responses=s_response,
        single_active=s_active,
        meta_trajectory=trajectory,
        meta_trajectory_active=trajectory_active,
        meta_relaxation=relaxation,
        meta_relaxation_active=relaxation_active,
        meta_post_completion_lags_seconds=np.asarray(meta["post_lags"]),
    )

    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.6))
    for column, impact_type in enumerate(("own", "cross")):
        members = single_members[impact_type]
        for domain in range(4):
            mean = np.mean(members[:, domain], axis=0)
            se = np.std(members[:, domain], axis=0, ddof=1) / math.sqrt(s_paths)
            axes[0, column].plot(single["lags_seconds"], mean, color=DOMAIN_COLOURS[domain], lw=1.7, label=DOMAIN_SHORT[domain])
            axes[0, column].fill_between(single["lags_seconds"], mean - 1.96 * se, mean + 1.96 * se, color=DOMAIN_COLOURS[domain], alpha=0.08)
        axes[0, column].set_title(f"({'a' if column == 0 else 'b'}) Single-trade {impact_type} impact", loc="left")
        axes[0, column].set_xlabel("Lag after event [s]")

        members = meta_relax_members[impact_type]
        for domain in range(4):
            for schedule_index, schedule in enumerate(schedules):
                values = members[schedule_index, :, domain]
                mean = np.mean(values, axis=0)
                axes[1, column].plot(
                    meta["post_lags"], mean, color=DOMAIN_COLOURS[domain],
                    lw=1.55, ls="-" if schedule_index == 0 else "--",
                    label=f"{DOMAIN_SHORT[domain]} / {schedule['schedule_id']}",
                )
        axes[1, column].set_title(f"({'c' if column == 0 else 'd'}) Meta-order {impact_type} relaxation", loc="left")
        axes[1, column].set_xlabel("Lag after final child [s]")

    for axis in axes.ravel():
        axis.axhline(0.0, color="#777777", lw=0.7)
        axis.grid(alpha=0.17, linewidth=0.5)
        axis.set_ylabel("Aggressor-signed shocked-minus-control log-mid")
    axes[0, 0].legend(frameon=False, fontsize=7, ncol=2)
    axes[1, 0].legend(frameon=False, fontsize=6.6, ncol=2)
    figure.suptitle("Paired price impact under alternative observation clocks")
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
    stem = PROJECT_ROOT / str(impact_cfg["output_stem"])
    atomic_savefig(figure, stem.with_suffix(".png"), dpi=300)
    atomic_savefig(figure, stem.with_suffix(".pdf"), metadata={"CreationDate": None, "ModDate": None})
    plt.close(figure)
    return {
        "single": single,
        "meta": meta,
        "single_response": s_response,
        "single_active": s_active,
        "trajectory": trajectory,
        "relaxation": relaxation,
        "renewal_pairs": {**s_pairs, **{f"meta_{key}": value for key, value in m_pairs.items()}},
    }


def _law_checks(configuration: dict[str, object]):
    rows = configuration["figure_13"]["rows"]
    count = 240000
    rng = np.random.default_rng(188307)
    streams = _open_uniforms(rng, (4, count))
    ml = mittag_leffler_waits_from_uniforms(
        streams[0], streams[1], streams[2], beta=float(rows[2]["beta"]), scale_seconds=float(rows[2]["scale_seconds"])
    )
    tempered = tempered_mittag_leffler_waits_from_uniforms(
        streams[0], streams[1], streams[2], streams[3],
        beta=float(rows[3]["beta"]), scale_seconds=float(rows[3]["scale_seconds"]),
        tempering_rate_per_second=float(rows[3]["tempering_rate_per_second"]),
    )
    s = np.asarray((0.025, 0.1, 0.4))
    ml_empirical = np.mean(np.exp(-s[:, None] * ml[None, :]), axis=1)
    ml_theory = mittag_leffler_wait_laplace(s, beta=float(rows[2]["beta"]), scale_seconds=float(rows[2]["scale_seconds"]))
    t_empirical = np.mean(np.exp(-s[:, None] * tempered[None, :]), axis=1)
    t_theory = tempered_mittag_leffler_wait_laplace(
        s, beta=float(rows[3]["beta"]), scale_seconds=float(rows[3]["scale_seconds"]), tempering_rate_per_second=float(rows[3]["tempering_rate_per_second"])
    )
    t_mean = tempered_mittag_leffler_mean_wait(
        beta=float(rows[3]["beta"]), scale_seconds=float(rows[3]["scale_seconds"]), tempering_rate_per_second=float(rows[3]["tempering_rate_per_second"])
    )
    return {
        "ml_laplace_error": float(np.max(np.abs(ml_empirical - ml_theory))),
        "tempered_laplace_error": float(np.max(np.abs(t_empirical - t_theory))),
        "tempered_mean_relative_error": float(abs(np.mean(tempered) - t_mean) / t_mean),
        "ml_q99": float(np.quantile(ml, 0.99)),
        "tempered_q99": float(np.quantile(tempered, 0.99)),
        "tempered_acceptance_fraction": float(tempered.size / ml.size),
    }


def _check(check_id: str, claim: str, observed: object, criterion: str, passed: bool):
    return {
        "check_id": check_id,
        "claim": claim,
        "observed": json.dumps(observed) if isinstance(observed, (list, tuple, dict)) else observed,
        "criterion": criterion,
        "status": "Verified" if passed else "Failed",
        "software_version": VERSION,
    }


def main() -> int:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if configuration["schema_version"] != VERSION:
        raise ValueError("v2.1.0 clock-impact configuration version mismatch")
    fig13_module = _load_module("v21_fig13_base", "scripts/41_run_stylised_facts_recovery.py")
    single_module = _load_module("v21_single_impact", "scripts/33_run_single_trade_impact.py")
    meta_module = _load_module("v21_meta_impact", "scripts/34_run_meta_order_impact.py")

    figure13 = _figure13(configuration, fig13_module)
    if "--figure13-only" in sys.argv:
        print("v2.1.0 Figure 13 rendering complete")
        return 0
    impacts = _extend_impacts(configuration, single_module, meta_module)
    laws = _law_checks(configuration)

    clock_rows = _clock_rows(figure13["renewal_pairs"])
    write_csv(
        PROJECT_ROOT / str(configuration["outputs"]["clock_summary"]),
        list(clock_rows[0]),
        clock_rows,
    )
    source_hash = _sha256(PROJECT_ROOT / "source/source-v1/CATG-RD2Epps-v3-arXiv.tex")
    rows = configuration["figure_13"]["rows"]
    s_active = np.mean(impacts["single_active"], axis=(0, 1, 2, 4, 5))
    finite_impacts = bool(
        np.all(np.isfinite(impacts["single_response"]))
        and np.all(np.isfinite(impacts["trajectory"]))
        and np.all(np.isfinite(impacts["relaxation"]))
    )
    checks = [
        _check("V21CI-01", "clock-impact configuration identity", [configuration["schema_version"], configuration["target_id"]], "v2.1.0 clock-impact configuration", configuration["schema_version"] == "2.1.0" and configuration["target_id"] == "V210-CLOCK-IMPACT"),
        _check("V21CI-02", "frozen source-v1 paper unchanged", source_hash, FROZEN_SOURCE_V1_SHA256, source_hash == FROZEN_SOURCE_V1_SHA256),
        _check("V21CI-03", "Gaussian label applies only to operational innovations", configuration["scientific_boundary"]["gaussian_semantics"], "operational_innovations_not_waiting_intervals", configuration["scientific_boundary"]["gaussian_semantics"] == "operational_innovations_not_waiting_intervals"),
        _check("V21CI-04", "previous-refresh map exact", figure13["previous_refresh_exact"], "all displayed states equal indexed operational states", figure13["previous_refresh_exact"]),
        _check("V21CI-05", "untempered ML Laplace transform", laws["ml_laplace_error"], "maximum Monte Carlo error < 0.006", laws["ml_laplace_error"] < 0.006),
        _check("V21CI-06", "tempered ML Laplace transform", laws["tempered_laplace_error"], "maximum Monte Carlo error < 0.006", laws["tempered_laplace_error"] < 0.006),
        _check("V21CI-07", "tempered ML finite mean", laws["tempered_mean_relative_error"], "Monte Carlo relative error < 0.035", laws["tempered_mean_relative_error"] < 0.035),
        _check("V21CI-08", "tempering truncates extreme waits", [laws["ml_q99"], laws["tempered_q99"]], "tempered q99 < untempered q99", laws["tempered_q99"] < laws["ml_q99"]),
        _check("V21CI-09", "order-flow memory is declared exogenous input", configuration["scientific_boundary"]["order_flow_memory"], "exogenous heavy-tailed metaorder runs", "exogenous" in configuration["scientific_boundary"]["order_flow_memory"]),
        _check("V21CI-10", "event-sign persistence at lag 10", float(figure13["event_sign_acf"][10]), "> 0.05", float(figure13["event_sign_acf"][10]) > 0.05),
        _check("V21CI-11", "event-sign ACF log-log decay slope", figure13["event_sign_slope"], "between -1.2 and -0.05", -1.2 < figure13["event_sign_slope"] < -0.05),
        _check("V21CI-12", "observation clocks alter zero-return mass", figure13["zero_return_fractions"].tolist(), "untempered ML exceeds operational and tempering reduces ML atom", figure13["zero_return_fractions"][2] > figure13["zero_return_fractions"][0] and figure13["zero_return_fractions"][3] < figure13["zero_return_fractions"][2]),
        _check("V21CI-13", "paired impact outputs finite", finite_impacts, "all single-trade and meta-order responses finite", finite_impacts),
        _check("V21CI-14", "common-input single-trade control", impacts["single"]["pre_event_maximum"], "maximum pre-event difference <= 1e-14", float(impacts["single"]["pre_event_maximum"]) <= 1e-14),
        _check("V21CI-15", "common-input meta-order control", impacts["meta"]["pre_event_maximum"], "maximum pre-event difference <= 1e-14", float(impacts["meta"]["pre_event_maximum"]) <= 1e-14),
        _check("V21CI-16", "Mittag-Leffler parameters", [rows[2]["beta"], rows[2]["scale_seconds"]], "beta=0.8 and tau=10 s", float(rows[2]["beta"]) == 0.8 and float(rows[2]["scale_seconds"]) == 10.0),
        _check("V21CI-17", "tempering parameter", rows[3]["tempering_rate_per_second"], "lambda=0.0125 per second", float(rows[3]["tempering_rate_per_second"]) == 0.0125),
        _check("V21CI-18", "single-trade clock domains retain event information", s_active.tolist(), "all domain-wide mean active fractions are positive", bool(np.all(s_active > 0.0))),
        _check("V21CI-19", "Diana implementation pinned", configuration["diana_reference"]["commit"], "098f180729f0b678109c53f86c514dfdc12ec708", configuration["diana_reference"]["commit"] == "098f180729f0b678109c53f86c514dfdc12ec708"),
        _check("V21CI-20", "no parameter refit", configuration["scientific_boundary"]["parameter_refit"], "false", configuration["scientific_boundary"]["parameter_refit"] is False),
    ]
    check_path = PROJECT_ROOT / str(configuration["outputs"]["checks"])
    write_csv(check_path, list(checks[0]), checks)
    failures = [row for row in checks if row["status"] != "Verified"]
    print(f"Clock-impact checks: {len(checks) - len(failures)}/{len(checks)} verified")
    for row in failures:
        print(f"  FAILED {row['check_id']}: {row['claim']} ({row['observed']})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
