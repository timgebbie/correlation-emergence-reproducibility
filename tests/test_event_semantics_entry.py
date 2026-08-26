"""Tests for the v1.8.0 event-semantics and impact-entry gate."""

from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


CONFIG_PATH = ROOT / "config" / "config-v1.8.0.json"
CHECK_PATH = ROOT / "diagnostics" / "event-semantics-entry-checks-v1.8.csv"
REGISTER_PATH = ROOT / "outputs" / "event-semantics-register-v1.8.csv"
PROVENANCE_PATH = ROOT / "provenance" / "EVENT-SEMANTICS-AND-IMPACT-ENTRY-v1.8.md"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class EventSemanticsEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        fixture = cls.config["deterministic_fixture"]
        cls.grid = np.asarray(fixture["grid"], dtype=float)
        cls.density = np.asarray(fixture["density"], dtype=float)
        cls.mid = float(fixture["pre_event_mid_log_price"])

    def event(
        self,
        event_type: str,
        side: int,
        quantity: float,
        *,
        price: float | None = None,
        event_id: str = "test",
    ) -> OrderEvent:
        return OrderEvent(
            event_id=event_id,
            event_type=event_type,
            book_index=0,
            operational_step=1,
            side=side,
            quantity=quantity,
            limit_log_price=price,
        )

    def test_parent_and_accepted_inputs_are_exact(self) -> None:
        self.assertEqual(self.config["schema_version"], "1.8.0")
        self.assertEqual(self.config["accepted_parent"], "v1.7.12")
        self.assertFalse(accepted_input_errors(self.config["accepted_inputs"]))

    def test_event_declaration_validation(self) -> None:
        with self.assertRaises(ValueError):
            self.event(EVENT_MARKET_ORDER, 0, 1.0)
        with self.assertRaises(ValueError):
            self.event(EVENT_MARKET_ORDER, 1, -1.0)
        with self.assertRaises(ValueError):
            self.event(EVENT_LIMIT_ORDER, 1, 1.0)
        with self.assertRaises(ValueError):
            OrderEvent("meta", EVENT_MARKET_ORDER, 0, 1, 1, 1.0, meta_order_id="M")

    def test_limit_order_semantics_and_quantity_conservation(self) -> None:
        buy = apply_order_event(
            self.event(EVENT_LIMIT_ORDER, 1, 0.25, price=-1.0),
            self.grid,
            self.density,
            pre_event_mid_log_price=self.mid,
        )
        sell = apply_order_event(
            self.event(EVENT_LIMIT_ORDER, -1, 0.4, price=1.0),
            self.grid,
            self.density,
            pre_event_mid_log_price=self.mid,
        )
        dx = self.grid[1] - self.grid[0]
        self.assertEqual(buy.affected_grid_indices, (2,))
        self.assertEqual(sell.affected_grid_indices, (6,))
        self.assertAlmostEqual(dx * np.sum(np.abs(buy.density_delta)), 0.25)
        self.assertAlmostEqual(dx * np.sum(np.abs(sell.density_delta)), 0.4)
        self.assertFalse(buy.is_trade)
        self.assertFalse(sell.is_trade)

    def test_crossing_and_off_grid_limit_orders_are_rejected(self) -> None:
        for side, price in ((1, 0.0), (-1, 0.0), (1, -0.9)):
            with self.subTest(side=side, price=price), self.assertRaises(ValueError):
                apply_order_event(
                    self.event(EVENT_LIMIT_ORDER, side, 0.1, price=price),
                    self.grid,
                    self.density,
                    pre_event_mid_log_price=self.mid,
                )

    def test_market_orders_consume_boundary_outwards(self) -> None:
        buy = apply_order_event(
            self.event(EVENT_MARKET_ORDER, 1, 0.6), self.grid, self.density,
            pre_event_mid_log_price=self.mid,
        )
        sell = apply_order_event(
            self.event(EVENT_MARKET_ORDER, -1, 0.6), self.grid, self.density,
            pre_event_mid_log_price=self.mid,
        )
        self.assertEqual(buy.affected_grid_indices, (5, 6))
        self.assertEqual(sell.affected_grid_indices, (3, 2))
        self.assertAlmostEqual(buy.filled_quantity, 0.6)
        self.assertAlmostEqual(sell.filled_quantity, 0.6)
        self.assertTrue(np.all((self.density + buy.density_delta)[self.grid > 0.0] <= 1e-14))
        self.assertTrue(np.all((self.density + sell.density_delta)[self.grid < 0.0] >= -1e-14))

    def test_fill_policy_is_explicit(self) -> None:
        event = self.event(EVENT_MARKET_ORDER, 1, 10.0)
        with self.assertRaises(InsufficientLiquidityError):
            apply_order_event(event, self.grid, self.density, pre_event_mid_log_price=self.mid)
        partial = apply_order_event(
            event, self.grid, self.density,
            pre_event_mid_log_price=self.mid, allow_partial=True,
        )
        self.assertAlmostEqual(partial.filled_quantity, 1.5)

    def test_three_trade_sign_conventions(self) -> None:
        buy = apply_order_event(
            self.event(EVENT_MARKET_ORDER, 1, 0.6), self.grid, self.density,
            pre_event_mid_log_price=self.mid,
        )
        sell = apply_order_event(
            self.event(EVENT_MARKET_ORDER, -1, 0.6), self.grid, self.density,
            pre_event_mid_log_price=self.mid,
        )
        passive = apply_order_event(
            self.event(EVENT_LIMIT_ORDER, 1, 0.25, price=-1.0), self.grid, self.density,
            pre_event_mid_log_price=self.mid,
        )
        self.assertEqual((ground_truth_aggressor_sign(buy), ground_truth_aggressor_sign(sell)), (1, -1))
        self.assertEqual((quote_midpoint_sign(buy), quote_midpoint_sign(sell)), (1, -1))
        self.assertEqual(ground_truth_aggressor_sign(passive), 0)
        self.assertEqual(tick_rule_signs([0.5, 1.0, 1.0, 0.25, 0.25]).tolist(), [0, 1, 1, -1, -1])

    def test_event_layer_has_no_solver_clock_rng_or_legacy_dependency(self) -> None:
        source = (ROOT / "functions" / "events" / "records.py").read_text(encoding="utf-8")
        for token in (
            "default_rng",
            "np.random",
            "translation_solver import",
            "refresh_sampling import",
            "legacy_coupling import",
            "step_uniform",
        ):
            self.assertNotIn(token, source)

    def test_impact_matrix_and_numeric_stages_are_complete(self) -> None:
        matrix = self.config["impact_matrix"]
        self.assertEqual(
            {(row["event_book"], row["response_book"]) for row in matrix},
            {(0, 0), (0, 1), (1, 0), (1, 1)},
        )
        self.assertTrue(all(row["impact_type"] == "own" for row in matrix if row["event_book"] == row["response_book"]))
        self.assertTrue(all(row["impact_type"] == "cross" for row in matrix if row["event_book"] != row["response_book"]))
        self.assertEqual(
            [row["version"] for row in self.config["stage_sequence"]],
            ["v1.8.0", "v1.8.1", "v1.8.2", "v1.8.3", "v1.9.0", "v1.9.1", "v2.0.0"],
        )

    def test_final_epps_and_streamlining_contracts_are_registered(self) -> None:
        final = self.config["final_epps_integration"]
        self.assertIn("estimator_aware_finite_grid_finite_step_theory", final["required_curves"])
        self.assertEqual(final["conformity_parameters"], "frozen_no_retuning")
        self.assertEqual(final["optional_calibrated_curve"], "separate_and_explicitly_labelled")
        self.assertEqual(
            self.config["release_streamlining"]["classifications"],
            ["release_critical", "provenance_archive_only", "development_only"],
        )

    def test_generated_gate_outputs_have_44_checks_and_26_contracts(self) -> None:
        checks = _rows(CHECK_PATH)
        register = _rows(REGISTER_PATH)
        self.assertEqual(len(checks), 44)
        self.assertEqual(len({row["check_id"] for row in checks}), 44)
        self.assertTrue(all(row["status"] == "Verified" for row in checks))
        self.assertEqual({row["software_version"] for row in checks}, {"1.8.0"})
        self.assertEqual(len(register), 26)
        self.assertEqual({row["software_version"] for row in register}, {"1.8.0"})

    def test_provenance_states_limitations_and_boundaries(self) -> None:
        provenance = PROVENANCE_PATH.read_text(encoding="utf-8")
        for phrase in (
            "one signed-density front",
            "execution-price proxy",
            "uniform operational grid",
            "explicit subordination",
            "v1.8.1",
            "v1.9.0",
            "v1.9.1",
            "not a trade-impact result",
        ):
            self.assertIn(phrase, provenance)


if __name__ == "__main__":
    unittest.main()
