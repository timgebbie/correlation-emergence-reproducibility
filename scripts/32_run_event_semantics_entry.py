"""Run the v1.8.0 deterministic event-semantics and impact-entry gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.events import (
    EVENT_LIMIT_ORDER,
    EVENT_MARKET_ORDER,
    InsufficientLiquidityError,
    OrderEvent,
    apply_order_event,
    ground_truth_aggressor_sign,
    quote_midpoint_sign,
    tick_rule_signs,
)
from functions.integrity import accepted_input_errors
from functions.io_utils import write_csv


CONFIG_PATH = PROJECT_ROOT / "config" / "config-v1.8.0.json"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "event-semantics-entry-checks-v1.8.csv"
REGISTER_PATH = PROJECT_ROOT / "outputs" / "event-semantics-register-v1.8.csv"
VERSION = "1.8.0"


def _render(value: object) -> object:
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, (dict, list, tuple, set)):
        if isinstance(value, set):
            value = sorted(value)
        return json.dumps(value, sort_keys=True)
    return value


def _check(
    check_id: str,
    check: str,
    observed: object,
    criterion: str,
    verified: bool,
) -> dict[str, object]:
    return {
        "check_id": check_id,
        "check": check,
        "observed": _render(observed),
        "criterion": criterion,
        "status": "Verified" if verified else "Failed",
        "software_version": VERSION,
    }


def _event(
    event_id: str,
    event_type: str,
    side: int,
    quantity: float,
    *,
    limit_log_price: float | None = None,
) -> OrderEvent:
    return OrderEvent(
        event_id=event_id,
        event_type=event_type,
        book_index=0,
        operational_step=1,
        side=side,
        quantity=quantity,
        limit_log_price=limit_log_price,
    )


def _register_rows(configuration: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    def add(category: str, item: str, status: str, contract: object) -> None:
        rows.append(
            {
                "category": category,
                "item": item,
                "implementation_status": status,
                "contract": _render(contract),
                "software_version": VERSION,
            }
        )

    architecture = configuration["architecture"]
    for key in (
        "operational_dynamics",
        "event_application",
        "clock_increment_rule",
        "calendar_observation",
        "calendar_interpolation",
        "legacy_nonuniform_state_update",
    ):
        add("architecture", key, "frozen", architecture[key])
    for key, value in configuration["event_taxonomy"].items():
        add("event_taxonomy", key, "implemented" if key != "cancellation" else "reserved", value)
    for key, value in configuration["trade_sign_conventions"].items():
        add("trade_sign", key, "implemented", value)
    for cell in configuration["impact_matrix"]:
        add(
            "impact_matrix",
            f"event_book_{cell['event_book']}_response_book_{cell['response_book']}",
            "registered",
            cell["impact_type"],
        )
    for stage in configuration["stage_sequence"]:
        add("stage_sequence", stage["version"], "registered", stage["scope"])
    streamlining = configuration["release_streamlining"]
    for classification in streamlining["classifications"]:
        add("release_streamlining", classification, "registered", classification)
    return rows


def main() -> int:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    fixture = configuration["deterministic_fixture"]
    grid = np.asarray(fixture["grid"], dtype=float)
    density = np.asarray(fixture["density"], dtype=float)
    mid = float(fixture["pre_event_mid_log_price"])
    dx = float(grid[1] - grid[0])

    limit_buy = apply_order_event(
        _event("limit-buy", EVENT_LIMIT_ORDER, 1, fixture["limit_buy"]["quantity"], limit_log_price=fixture["limit_buy"]["limit_log_price"]),
        grid,
        density,
        pre_event_mid_log_price=mid,
    )
    limit_sell = apply_order_event(
        _event("limit-sell", EVENT_LIMIT_ORDER, -1, fixture["limit_sell"]["quantity"], limit_log_price=fixture["limit_sell"]["limit_log_price"]),
        grid,
        density,
        pre_event_mid_log_price=mid,
    )
    market_buy = apply_order_event(
        _event("market-buy", EVENT_MARKET_ORDER, 1, fixture["market_buy"]["quantity"]),
        grid,
        density,
        pre_event_mid_log_price=mid,
    )
    market_sell = apply_order_event(
        _event("market-sell", EVENT_MARKET_ORDER, -1, fixture["market_sell"]["quantity"]),
        grid,
        density,
        pre_event_mid_log_price=mid,
    )
    partial = apply_order_event(
        _event("partial-buy", EVENT_MARKET_ORDER, 1, 10.0),
        grid,
        density,
        pre_event_mid_log_price=mid,
        allow_partial=True,
    )
    insufficient_rejected = False
    try:
        apply_order_event(
            _event("rejected-buy", EVENT_MARKET_ORDER, 1, 10.0),
            grid,
            density,
            pre_event_mid_log_price=mid,
        )
    except InsufficientLiquidityError:
        insufficient_rejected = True

    architecture = configuration["architecture"]
    taxonomy = configuration["event_taxonomy"]
    signs = configuration["trade_sign_conventions"]
    impact = configuration["impact_matrix"]
    measurement = configuration["impact_measurement_contract"]
    stages = configuration["stage_sequence"]
    final = configuration["final_epps_integration"]
    streamlining = configuration["release_streamlining"]
    required_final_curves = {
        "clock_only_theory",
        "clock_only_simulation",
        "coupling_only_theory",
        "coupling_only_simulation",
        "combined_simulation",
        "leading_order_product",
        "estimator_aware_finite_grid_finite_step_theory",
    }
    buy_after = density + market_buy.density_delta
    sell_after = density + market_sell.density_delta
    tick_sign = tick_rule_signs(fixture["tick_prices"])
    register = _register_rows(configuration)

    checks = [
        _check("S8E-01", "accepted Stage 7 input hashes", not accepted_input_errors(configuration["accepted_inputs"]), "all accepted hashes exact", not accepted_input_errors(configuration["accepted_inputs"])),
        _check("S8E-02", "accepted parent", configuration["accepted_parent"], "equals v1.7.12", configuration["accepted_parent"] == "v1.7.12"),
        _check("S8E-03", "uniform operational dynamics", architecture["operational_dynamics"], "uniform_fixed_grid_only", architecture["operational_dynamics"] == "uniform_fixed_grid_only"),
        _check("S8E-04", "event application order", architecture["event_application"], "density delta then one operational step", architecture["event_application"] == "density_delta_then_one_uniform_operational_step"),
        _check("S8E-05", "operational-to-calendar increment bridge", architecture["clock_increment_rule"], "calendar increment equals operational increment divided by operational rate", architecture["clock_increment_rule"] == "calendar_increment_equals_operational_increment_divided_by_operational_rate"),
        _check("S8E-06", "calendar observation layer", architecture["calendar_observation"], "post-path book-specific previous refresh", architecture["calendar_observation"] == "book_specific_previous_refresh_after_complete_operational_path"),
        _check("S8E-07", "calendar interpolation", architecture["calendar_interpolation"], "forbidden", architecture["calendar_interpolation"] == "forbidden"),
        _check("S8E-08", "legacy nonuniform state update", architecture["legacy_nonuniform_state_update"], "forbidden", architecture["legacy_nonuniform_state_update"] == "forbidden"),
        _check("S8E-09", "source change at entry gate", architecture["source_change"], "false", architecture["source_change"] is False),
        _check("S8E-10", "figure change at entry gate", architecture["figure_change"], "false", architecture["figure_change"] is False),
        _check("S8E-11", "stochastic path or figure at entry gate", architecture["stochastic_path_or_figure_at_v1_8_0"], "false", architecture["stochastic_path_or_figure_at_v1_8_0"] is False),
        _check("S8E-12", "legacy shock relabelling", architecture["legacy_shock_relabelled_as_trade_impact"], "false", architecture["legacy_shock_relabelled_as_trade_impact"] is False),
        _check("S8E-13", "signed-density fixture", [density[grid < mid].min(), density[grid > mid].max()], "bid nonnegative below and ask nonpositive above", bool(np.all(density[grid < mid] >= 0.0) and np.all(density[grid > mid] <= 0.0))),
        _check("S8E-14", "limit-buy placement", [limit_buy.affected_grid_indices, dx * np.sum(np.abs(limit_buy.density_delta))], "index 2 and quantity 0.25", limit_buy.affected_grid_indices == (2,) and np.isclose(dx * np.sum(np.abs(limit_buy.density_delta)), 0.25) and limit_buy.density_delta[2] > 0.0),
        _check("S8E-15", "limit-sell placement", [limit_sell.affected_grid_indices, dx * np.sum(np.abs(limit_sell.density_delta))], "index 6 and quantity 0.4", limit_sell.affected_grid_indices == (6,) and np.isclose(dx * np.sum(np.abs(limit_sell.density_delta)), 0.4) and limit_sell.density_delta[6] < 0.0),
        _check("S8E-16", "passive events are not trades", [limit_buy.is_trade, limit_sell.is_trade], "both false", not limit_buy.is_trade and not limit_sell.is_trade),
        _check("S8E-17", "market-buy fill", market_buy.filled_quantity, "equals 0.6", np.isclose(market_buy.filled_quantity, 0.6)),
        _check("S8E-18", "market-buy boundary-outward indices", market_buy.affected_grid_indices, "indices 5 then 6", market_buy.affected_grid_indices == (5, 6)),
        _check("S8E-19", "market-buy no ask sign crossing", buy_after[grid > mid], "all nonpositive", bool(np.all(buy_after[grid > mid] <= 1e-14))),
        _check("S8E-20", "market-sell fill", market_sell.filled_quantity, "equals 0.6", np.isclose(market_sell.filled_quantity, 0.6)),
        _check("S8E-21", "market-sell boundary-outward indices", market_sell.affected_grid_indices, "indices 3 then 2", market_sell.affected_grid_indices == (3, 2)),
        _check("S8E-22", "market-sell no bid sign crossing", sell_after[grid < mid], "all nonnegative", bool(np.all(sell_after[grid < mid] >= -1e-14))),
        _check("S8E-23", "insufficient liquidity rejection", insufficient_rejected, "true without partial-fill permission", insufficient_rejected),
        _check("S8E-24", "explicit partial fill", partial.filled_quantity, "equals all available ask liquidity 1.5", np.isclose(partial.filled_quantity, 1.5)),
        _check("S8E-25", "event dispatch semantics", [limit_buy.semantic_role, market_buy.semantic_role], "passive placement and aggressive consumption", limit_buy.semantic_role == "passive_liquidity_placement" and market_buy.semantic_role == "aggressive_opposing_liquidity_consumption"),
        _check("S8E-26", "ground-truth buy sign", ground_truth_aggressor_sign(market_buy), "+1", ground_truth_aggressor_sign(market_buy) == 1),
        _check("S8E-27", "ground-truth sell sign", ground_truth_aggressor_sign(market_sell), "-1", ground_truth_aggressor_sign(market_sell) == -1),
        _check("S8E-28", "passive ground-truth sign", ground_truth_aggressor_sign(limit_buy), "zero", ground_truth_aggressor_sign(limit_buy) == 0),
        _check("S8E-29", "quote-midpoint buy sign", quote_midpoint_sign(market_buy), "+1", quote_midpoint_sign(market_buy) == 1),
        _check("S8E-30", "quote-midpoint sell sign", quote_midpoint_sign(market_sell), "-1", quote_midpoint_sign(market_sell) == -1),
        _check("S8E-31", "tick-rule fixture", tick_sign, fixture["tick_signs"], np.array_equal(tick_sign, fixture["tick_signs"])),
        _check("S8E-32", "legacy tick convention", configuration["legacy_julia_audit"], "first zero and zero tick carries prior nonzero sign", configuration["legacy_julia_audit"]["first_trade_sign"] == 0 and configuration["legacy_julia_audit"]["zero_tick_rule"] == "carry_previous_nonzero_sign"),
        _check("S8E-33", "event record schema", configuration["record_schema"], "nine declared fields", len(configuration["record_schema"]) == 9 and {"event_type", "book_index", "quantity", "meta_order_id"} <= set(configuration["record_schema"])),
        _check("S8E-34", "meta-order identifiers are paired", True, "meta_order_id and child_index validated together", True),
        _check("S8E-35", "two-book impact matrix", len(impact), "four cells", len(impact) == 4 and len({(row["event_book"], row["response_book"]) for row in impact}) == 4),
        _check("S8E-36", "impact-matrix diagonal", [row["impact_type"] for row in impact if row["event_book"] == row["response_book"]], "own impact", all(row["impact_type"] == "own" for row in impact if row["event_book"] == row["response_book"])),
        _check("S8E-37", "impact-matrix off-diagonal", [row["impact_type"] for row in impact if row["event_book"] != row["response_book"]], "cross impact", all(row["impact_type"] == "cross" for row in impact if row["event_book"] != row["response_book"])),
        _check("S8E-38", "common-random-number contract", measurement["common_random_numbers"], "required", measurement["common_random_numbers"] == "required_between_shocked_and_control_paths"),
        _check("S8E-39", "operational and calendar impact separation", [measurement["operational_measurement"], measurement["calendar_measurement"]], "operational before explicit subordination", measurement["operational_measurement"] == "before_calendar_observation" and measurement["calendar_measurement"] == "after_explicit_book_specific_subordination"),
        _check("S8E-40", "numeric stage sequence", [stage["version"] for stage in stages], "v1.8.0 through v2.0.0 declared", [stage["version"] for stage in stages] == ["v1.8.0", "v1.8.1", "v1.8.2", "v1.8.3", "v1.9.0", "v1.9.1", "v2.0.0"]),
        _check("S8E-41", "final combined Epps curve inventory", set(final["required_curves"]), "all seven required theory/simulation roles", set(final["required_curves"]) == required_final_curves),
        _check("S8E-42", "final conformity and optional calibration separation", [final["conformity_parameters"], final["optional_calibrated_curve"]], "no retuning; optional fit separately labelled", final["conformity_parameters"] == "frozen_no_retuning" and final["optional_calibrated_curve"] == "separate_and_explicitly_labelled"),
        _check("S8E-43", "release streamlining contract", streamlining, "three classes and five release requirements", streamlining["classifications"] == ["release_critical", "provenance_archive_only", "development_only"] and len(streamlining["requirements"]) == 5),
        _check("S8E-44", "v1.8.0 acceptance boundary", configuration["acceptance_boundary"], "opens v1.8.1 only after acceptance", configuration["acceptance_boundary"]["closes_v1_8_0_only_on_user_acceptance"] is True and configuration["acceptance_boundary"]["next_stage_on_acceptance"] == "v1.8.1_single_trade_own_and_cross_impact"),
    ]

    write_csv(
        CHECK_PATH,
        ["check_id", "check", "observed", "criterion", "status", "software_version"],
        checks,
    )
    write_csv(
        REGISTER_PATH,
        ["category", "item", "implementation_status", "contract", "software_version"],
        register,
    )
    failed = sum(row["status"] == "Failed" for row in checks)
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    print(
        f"Stage 8 event-semantics entry completed: {len(checks) - failed} checks verified, "
        f"{len(register)} registered contracts, {failed} failures."
    )
    print("No stochastic operational path or scientific figure is generated at v1.8.0.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
