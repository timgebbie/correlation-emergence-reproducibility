"""Integrity checks for generated figures, tables, datasets, and frozen sources."""

from __future__ import annotations

import csv
import hashlib
import struct
import sys
import unittest
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.diagnostic_checks import OVERLAY_REQUIRED_FIELDS


def _png_chunks_are_valid(path: Path) -> bool:
    """Check PNG chunk boundaries and CRCs using only the standard library."""
    payload = path.read_bytes()
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset = 8
    while offset + 12 <= len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_end = offset + 12 + length
        if chunk_end > len(payload):
            return False
        chunk_type = payload[offset + 4 : offset + 8]
        chunk_data = payload[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", payload[offset + 8 + length : chunk_end])[0]
        observed_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if observed_crc != expected_crc:
            return False
        offset = chunk_end
        if chunk_type == b"IEND":
            return offset == len(payload)
    return False


class GeneratedOutputTests(unittest.TestCase):
    def test_six_figure_pairs_exist(self) -> None:
        pdfs = sorted((PROJECT_ROOT / "figures").glob("figure-0[1-6]-*.pdf"))
        pngs = sorted((PROJECT_ROOT / "figures").glob("figure-0[1-6]-*.png"))
        self.assertEqual(len(pdfs), 6)
        self.assertEqual(len(pngs), 6)
        self.assertTrue(all(path.stat().st_size > 5_000 for path in pdfs + pngs))
        self.assertTrue(all(path.read_bytes()[:4] == b"%PDF" for path in pdfs))
        self.assertTrue(all(path.read_bytes().rstrip().endswith(b"%%EOF") for path in pdfs))
        self.assertTrue(all(_png_chunks_are_valid(path) for path in pngs))

    def test_six_machine_readable_figure_datasets_exist(self) -> None:
        datasets = sorted((PROJECT_ROOT / "outputs").glob("figure-0[1-6]-*-data-v1.csv"))
        self.assertEqual(len(datasets), 6)
        for path in datasets:
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertGreater(len(rows), 50, path.name)

    def test_calendar_bridge_contains_curve_and_memory_panels(self) -> None:
        path = PROJECT_ROOT / "outputs" / "figure-06-calendar-time-epps-memory-data-v1.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual({row["panel"] for row in rows}, {"calendar_epps_curve", "memory_diagnostic"})
        self.assertEqual(
            {row["mechanism"] for row in rows},
            {
                "limiting_correlation",
                "clock",
                "coupling",
                "combined",
                "clock_no_refresh_survival",
                "coupling_relaxation_survival",
            },
        )

    def test_two_csv_latex_table_pairs_exist(self) -> None:
        for number in ("01", "02"):
            csv_paths = list((PROJECT_ROOT / "tables").glob(f"table-{number}-*.csv"))
            tex_paths = list((PROJECT_ROOT / "tables").glob(f"table-{number}-*.tex"))
            self.assertEqual(len(csv_paths), 1)
            self.assertEqual(len(tex_paths), 1)
            self.assertGreater(csv_paths[0].stat().st_size, 500)
            self.assertGreater(tex_paths[0].stat().st_size, 500)

    def test_diagnostic_csv_and_latex_status_agree(self) -> None:
        csv_path = PROJECT_ROOT / "tables" / "table-02-numerical-benchmarks-v1.csv"
        tex_path = PROJECT_ROOT / "tables" / "table-02-numerical-benchmarks-v1.tex"
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        tex = tex_path.read_text(encoding="utf-8")
        self.assertEqual(len(rows), 14)
        for row in rows:
            self.assertIn(row["diagnostic_id"], tex)
            self.assertIn(row["status"], tex)

    def test_overlay_schema_and_curve_types(self) -> None:
        path = PROJECT_ROOT / "outputs" / "epps-overlay-v1.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fields = set(reader.fieldnames or [])
        self.assertTrue(OVERLAY_REQUIRED_FIELDS.issubset(fields))
        self.assertEqual({row["curve_type"] for row in rows}, {"analytic"})
        self.assertEqual({row["mechanism"] for row in rows}, {"clock", "coupling", "combined"})

    def test_sensitivity_report_has_no_failed_checks(self) -> None:
        path = PROJECT_ROOT / "outputs" / "sensitivity-summary-v1.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 16)
        self.assertTrue(all(row["status"] == "Verified" for row in rows))

    def test_supplement_pdf_and_tex_exist(self) -> None:
        tex_path = PROJECT_ROOT / "SUPPLEMENTARY-MATERIAL-v1.0.0.tex"
        pdf_path = PROJECT_ROOT / "supplementary-materials" / "SUPPLEMENTARY-MATERIAL-v1.0.0.pdf"
        self.assertTrue(tex_path.is_file())
        self.assertTrue(pdf_path.is_file())
        self.assertGreater(pdf_path.stat().st_size, 100_000)
        self.assertEqual(pdf_path.read_bytes()[:4], b"%PDF")
        self.assertTrue(pdf_path.read_bytes().rstrip().endswith(b"%%EOF"))

    def test_source_freeze_hashes(self) -> None:
        expected = {
            "CATG-RD2Epps2-v2-arXiv.tex": "707f4a6aee671acf1ab333758a2934edf4692014248696333ba9a78743b4f1a1",
            "CoupledOB.bib": "93a71de424f36a7cfbbbc302802b17900831316cd405901b455c85d657f8155d",
            "widetext.sty": "a74c899cc9dc1da83c7b284d9b771b3ee034a78eaa22720e3ab1c779b10eedbb",
        }
        for name, digest in expected.items():
            path = PROJECT_ROOT / "source" / "source-v0" / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
