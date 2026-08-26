"""Generate the v1.5.0 clock and subordination entry evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.io_utils import write_csv
from functions.observation import (
    book_clock_from_intervals,
    identity_book_clock,
    inverse_clock_previous_state,
    subordinate_operational_values,
    subordinate_two_book_prices,
)


CONFIG_PATH = PROJECT_ROOT / "config" / "config-v1.5.json"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "clock-subordination-checks-v1.5.csv"
FIXTURE_PATH = PROJECT_ROOT / "outputs" / "clock-subordination-fixture-v1.5.csv"
VERSION = "1.5.0"


def _inclusive_grid(specification: dict[str, float]) -> np.ndarray:
    start = float(specification["start"])
    stop = float(specification["stop"])
    step = float(specification["step"])
    points = int(round((stop - start) / step)) + 1
    values = start + step * np.arange(points, dtype=float)
    if not np.isclose(values[-1], stop, rtol=0.0, atol=1e-14):
        raise ValueError("declared grid endpoint is not reached exactly")
    return values


def _row(
    check_id: str,
    check: str,
    observed: float,
    criterion: str,
    verified: bool,
) -> dict[str, object]:
    return {
        "check_id": check_id,
        "check": check,
        "observed": observed,
        "criterion": criterion,
        "status": "Verified" if verified else "Failed",
        "software_version": VERSION,
    }


def build_evidence() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        configuration = json.load(handle)
    if configuration["finite_grid_convention"] != "previous_completed_operational_state":
        raise ValueError("v1.5.0 requires the declared previous-state convention")
    operational_times = _inclusive_grid(configuration["operational_grid"])
    calendar_queries = _inclusive_grid(configuration["calendar_query_grid"])

    clocks = []
    for record in configuration["book_clocks"]:
        clocks.append(
            book_clock_from_intervals(
                operational_times,
                np.asarray(record["calendar_intervals"], dtype=float),
                law=str(record["law"]),
                stream_id=str(record["stream_id"]),
                seed=int(record["seed"]),
            )
        )
    clock_one, clock_two = clocks
    identity_one = identity_book_clock(
        operational_times, stream_id="IDENTITY-V1.5.0-BOOK-1"
    )
    identity_two = identity_book_clock(
        operational_times, stream_id="IDENTITY-V1.5.0-BOOK-2"
    )

    operational_prices = np.column_stack(
        (
            0.1 + operational_times + 0.05 * operational_times**2,
            -0.2 + 0.5 * operational_times - 0.025 * operational_times**2,
        )
    )
    original_prices = operational_prices.copy()
    identity_result = subordinate_two_book_prices(
        operational_prices,
        (identity_one, identity_two),
        operational_times,
    )
    asynchronous_result = subordinate_two_book_prices(
        operational_prices,
        clocks,
        calendar_queries,
    )
    alternate_result = subordinate_two_book_prices(
        operational_prices,
        (clock_two, clock_one),
        calendar_queries,
    )
    inverse_one = inverse_clock_previous_state(clock_one, calendar_queries)
    inverse_two = inverse_clock_previous_state(clock_two, calendar_queries)
    exact_node_inverse = inverse_clock_previous_state(
        clock_one, clock_one.calendar_times
    )
    field = np.column_stack(
        (operational_prices[:, 0], operational_prices[:, 0] ** 2)
    )
    subordinated_field = subordinate_operational_values(
        field, clock_one, calendar_queries
    )

    beyond_support_rejected = False
    try:
        inverse_clock_previous_state(
            clock_one, np.asarray([clock_one.supported_calendar_horizon + 0.1])
        )
    except ValueError:
        beyond_support_rejected = True

    checks = [
        _row("CLK-01", "identity clock nodes", float(np.max(np.abs(identity_one.calendar_times - operational_times))), "maximum error equals zero", np.array_equal(identity_one.calendar_times, operational_times)),
        _row("CLK-02", "identity inverse indices", float(np.max(np.abs(identity_result.operational_indices - np.arange(operational_times.size)[:, None]))), "maximum index error equals zero", np.array_equal(identity_result.operational_indices, np.tile(np.arange(operational_times.size)[:, None], (1, 2)))),
        _row("CLK-03", "identity recovers operational prices", float(np.max(np.abs(identity_result.prices - operational_prices))), "maximum error equals zero", np.array_equal(identity_result.prices, operational_prices)),
        _row("CLK-04", "equal mean waiting intervals", float(abs(np.mean(clock_one.calendar_intervals) - np.mean(clock_two.calendar_intervals))), "absolute difference equals zero", np.mean(clock_one.calendar_intervals) == np.mean(clock_two.calendar_intervals)),
        _row("CLK-05", "equal-law clock paths are distinct", float(np.max(np.abs(clock_one.calendar_times - clock_two.calendar_times))), "maximum path difference > 0", not np.array_equal(clock_one.calendar_times, clock_two.calendar_times)),
        _row("CLK-06", "clock streams are explicit and distinct", float(clock_one.stream_id != clock_two.stream_id), "equals one", clock_one.stream_id != clock_two.stream_id),
        _row("CLK-07", "clock seeds are explicit and distinct", float(clock_one.seed != clock_two.seed), "equals one", clock_one.seed is not None and clock_two.seed is not None and clock_one.seed != clock_two.seed),
        _row("CLK-08", "exact clock nodes retain same-index state", float(np.max(np.abs(exact_node_inverse.operational_indices - np.arange(clock_one.states)))), "maximum index error equals zero", np.array_equal(exact_node_inverse.operational_indices, np.arange(clock_one.states))),
        _row("CLK-09", "clock endpoint maps to final operational state", float(inverse_one.operational_indices[-1]), f"equals {operational_times.size - 1}", inverse_one.operational_indices[-1] == operational_times.size - 1),
        _row("CLK-10", "calendar extrapolation is rejected", float(beyond_support_rejected), "equals one", beyond_support_rejected),
        _row("SUB-01", "book-specific inverse paths differ", float(np.max(np.abs(inverse_one.operational_indices - inverse_two.operational_indices))), "maximum index difference > 0", not np.array_equal(inverse_one.operational_indices, inverse_two.operational_indices)),
        _row("SUB-02", "subordinated field preserves trailing shape", float(subordinated_field.shape[1]), "equals two", subordinated_field.shape == (calendar_queries.size, 2)),
        _row("SUB-03", "clock replacement leaves operational path unchanged", float(np.max(np.abs(operational_prices - original_prices))), "maximum error equals zero", np.array_equal(operational_prices, original_prices)),
        _row("SUB-04", "clock replacement changes only calendar image", float(np.max(np.abs(asynchronous_result.prices - alternate_result.prices))), "maximum calendar-image difference > 0", not np.array_equal(asynchronous_result.prices, alternate_result.prices)),
        _row("SUB-05", "declared previous-state convention", float(asynchronous_result.inverse_convention == "previous_completed_operational_state"), "equals one", asynchronous_result.inverse_convention == "previous_completed_operational_state"),
    ]

    fixture_rows: list[dict[str, object]] = []
    for scenario, result in (
        ("identity", identity_result),
        ("book_specific", asynchronous_result),
    ):
        for query_index, calendar_time in enumerate(result.calendar_times):
            for book in range(2):
                operational_index = int(result.operational_indices[query_index, book])
                fixture_rows.append(
                    {
                        "scenario": scenario,
                        "calendar_time": calendar_time,
                        "book_index": book,
                        "clock_stream_id": result.clock_stream_ids[book],
                        "operational_index": operational_index,
                        "inverse_operational_time": result.inverse_operational_times[query_index, book],
                        "operational_price": operational_prices[operational_index, book],
                        "calendar_price": result.prices[query_index, book],
                        "supported_calendar_horizon": result.clock_horizons[book],
                        "inverse_convention": result.inverse_convention,
                        "software_version": VERSION,
                    }
                )
    return checks, fixture_rows


def main() -> int:
    checks, fixture_rows = build_evidence()
    write_csv(CHECK_PATH, list(checks[0]), checks)
    write_csv(FIXTURE_PATH, list(fixture_rows[0]), fixture_rows)
    failures = [row for row in checks if row["status"] != "Verified"]
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    if failures:
        print(f"Clock/subordination route failed: {len(failures)} check(s).")
        return 1
    print(
        f"Clock/subordination route completed: {len(checks)} checks verified, "
        f"{len(fixture_rows)} fixture rows, 0 failures."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
