"""Generate the two frozen publication tables as CSV and standalone LaTeX fragments."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.io_utils import ensure_output_directories, latex_escape, load_config, read_csv, write_csv


PARAMETER_ROWS = [
    {
        "paper_symbol": r"\(\Delta\)",
        "code_name": "aggregation_scale",
        "source": "Eqs. (8), (9), (11)",
        "units": "time; dimensionless after scaling",
        "role": "return aggregation horizon",
        "sensitivity_path": "direct horizontal scale",
        "treatment": "swept in F1-F6",
        "identifiability": "observed/design variable",
    },
    {
        "paper_symbol": r"\(\rho_\infty\)",
        "code_name": "rho_inf",
        "source": "Eqs. (8), (9), (11)",
        "units": "dimensionless correlation",
        "role": "long-scale vertical level",
        "sensitivity_path": "multiplicative vertical scale",
        "treatment": "fixed to one in base figures",
        "identifiability": "conditional on plateau coverage",
    },
    {
        "paper_symbol": r"\(\lambda_{12}\)",
        "code_name": "clock_rate",
        "source": "Eq. (8); App. A",
        "units": r"time\(^{-1}\)",
        "role": "pooled refresh/overlap rate",
        "sensitivity_path": r"\(F(\lambda_{12}\Delta)\)",
        "treatment": "unit scale; sensitivity in F2",
        "identifiability": "conditional; independently measurable in v2",
    },
    {
        "paper_symbol": r"\(\kappa=\kappa_1+\kappa_2\)",
        "code_name": "response_rate",
        "source": "Eq. (9); App. B",
        "units": r"time\(^{-1}\)",
        "role": "spread relaxation rate",
        "sensitivity_path": r"\(F(\kappa\Delta)\)",
        "treatment": "swept in F1-F2; derived in F4-F5",
        "identifiability": "conditional on clock rate and short scales",
    },
    {
        "paper_symbol": r"\(\alpha_c\)",
        "code_name": "alpha_clock",
        "source": "App. C, Eq. (C.18)",
        "units": "dimensionless",
        "role": "fractional clock order",
        "sensitivity_path": r"short power \(\Delta^{\alpha_c}\)",
        "treatment": "swept in F3",
        "identifiability": "not separate from alpha_response at short scale",
    },
    {
        "paper_symbol": r"\(\alpha_r\)",
        "code_name": "alpha_response",
        "source": "App. C, Eq. (C.18)",
        "units": "dimensionless",
        "role": "fractional response order",
        "sensitivity_path": r"short power \(\Delta^{\alpha_r}\)",
        "treatment": "swept in F3",
        "identifiability": "not separate from alpha_clock at short scale",
    },
    {
        "paper_symbol": r"\(\tau_c,\tau_r\)",
        "code_name": "clock_characteristic_time; response_characteristic_time",
        "source": "v1 nondimensionalisation",
        "units": "time",
        "role": "fractional scale convention",
        "sensitivity_path": r"\((\Delta/\tau)^\alpha\)",
        "treatment": "fixed to one in F3",
        "identifiability": "confounded with fractional rate convention",
    },
    {
        "paper_symbol": r"\(\gamma_{jk}\)",
        "code_name": "coupling_strength",
        "source": "Eq. (6); App. B",
        "units": "model-dependent",
        "role": "pair-trader coupling strength",
        "sensitivity_path": r"\(\kappa_j\propto\gamma_{jk}\)",
        "treatment": "one-at-a-time sweep in F4",
        "identifiability": "not separate from source/front quantities",
    },
    {
        "paper_symbol": r"\(\lambda_j\) (source)",
        "code_name": "source_amplitude",
        "source": "Eq. (5); App. B",
        "units": "source amplitude",
        "role": "decaying-Gaussian amplitude",
        "sensitivity_path": r"\(M_j^+\propto a_j\)",
        "treatment": "one-at-a-time sweep in F4",
        "identifiability": "not separate from coupling strength",
    },
    {
        "paper_symbol": r"\(\mu_j\)",
        "code_name": "source_width",
        "source": "Eq. (5); App. B",
        "units": r"price\(^{-2}\)",
        "role": "Gaussian source-shape scale",
        "sensitivity_path": r"\(M_j^+\propto\mu_j^{-1/2}\)",
        "treatment": "one-at-a-time sweep in F4",
        "identifiability": "not separate from amplitude/front slope",
    },
    {
        "paper_symbol": r"\(|\mathcal L_j|\)",
        "code_name": "front_slope_abs",
        "source": "Eq. (B.9); Eq. (B.13)",
        "units": "density per price",
        "role": "frozen reaction-front slope",
        "sensitivity_path": r"\(\kappa_j\propto|\mathcal L_j|^{-1}\)",
        "treatment": "one-at-a-time sweep in F4",
        "identifiability": "not identifiable as thickness from Epps alone",
    },
    {
        "paper_symbol": r"\(\varepsilon\)",
        "code_name": "epsilon",
        "source": "Eq. (6); App. D",
        "units": r"price\(^2\) for \(yz/\varepsilon\)",
        "role": "continuum selector regularisation",
        "sensitivity_path": "centred moment invariant; representation path",
        "treatment": "swept in F5",
        "identifiability": "not a reaction-front thickness parameter",
    },
    {
        "paper_symbol": r"\(\Delta x\)",
        "code_name": "lattice_spacing",
        "source": "App. D",
        "units": "price",
        "role": "numerical lattice resolution",
        "sensitivity_path": "discrete moment error to effective response",
        "treatment": "swept in F5",
        "identifiability": "known numerical control",
    },
    {
        "paper_symbol": r"\(z_{jk}\)",
        "code_name": "directed_spread",
        "source": "Eq. (6); App. B",
        "units": "price",
        "role": "directed book-price spread",
        "sensitivity_path": r"selector argument \(yz/\varepsilon\)",
        "treatment": "fixed to 0.2 in F5",
        "identifiability": "state variable, not inferred parameter",
    },
    {
        "paper_symbol": "--",
        "code_name": "alignment_offset_cells",
        "source": "v1 numerical diagnostic",
        "units": "lattice cells",
        "role": "source-selector centring error",
        "sensitivity_path": "parity breaking to effective response",
        "treatment": "0 and 0.5 in F5",
        "identifiability": "known numerical control",
    },
    {
        "paper_symbol": "--",
        "code_name": "domain_halfwidth",
        "source": "v1 numerical diagnostic",
        "units": "price",
        "role": "finite integration/lattice domain",
        "sensitivity_path": "tail truncation to effective response",
        "treatment": "full and truncated in F5",
        "identifiability": "known numerical control",
    },
]


def _table_one_tex(rows: list[dict[str, object]]) -> str:
    body = []
    for row in rows:
        code_parts = str(row["code_name"]).split("; ")
        code_tex = r"\newline".join(
            r"\texttt{" + latex_escape(part).replace(r"\_", r"\_\allowbreak{}") + "}"
            for part in code_parts
        )
        body.append(
            "{} & {} & {} & {} & {} & {} & {} & {} \\\\".format(
                row["paper_symbol"],
                code_tex,
                latex_escape(row["source"]),
                row["units"],
                latex_escape(row["role"]),
                row["sensitivity_path"],
                latex_escape(row["treatment"]),
                latex_escape(row["identifiability"]),
            )
        )
    return "\n".join(
        [
            "% Standalone table fragment. Required packages: booktabs, tabularx, array, float.",
            "\\begin{table}[H]",
            "\\centering",
            "\\scriptsize",
            "\\caption{\\textbf{Parameter, timescale and identifiability register.} The table maps paper notation to implementation names and records units, roles, sensitivity pathways, and fixed or swept status. Refresh rate and source amplitude receive different code names despite source-notation overlap. Identifiability classifications describe the information available from the planned outputs under the stated model; they are not estimates, formal statistical-identifiability proofs, or empirical calibration results.}",
            "\\label{tab:parameter-register}",
            "\\renewcommand{\\arraystretch}{0.98}",
            "\\begin{tabularx}{\\linewidth}{@{}p{1.7cm}p{3.3cm}p{2.3cm}p{2.5cm}X X X X@{}}",
            "\\toprule",
            "Paper symbol & Code name & Source & Units & Role & Sensitivity path & Figure treatment & Identifiability from Epps output \\\\",
            "\\midrule",
            *body,
            "\\bottomrule",
            "\\end{tabularx}",
            "\\end{table}",
            "",
        ]
    )


def _table_two_tex(rows: list[dict[str, str]]) -> str:
    body = []
    for row in rows:
        body.append(
            "{} & {} & {} & {} & {} & {} \\\\".format(
                latex_escape(row["diagnostic_id"]),
                latex_escape(row["diagnostic"]),
                latex_escape(row["expected_result"]),
                latex_escape(row["tolerance"]),
                latex_escape(row["observed_result"]),
                latex_escape(row["status"]),
            )
        )
    return "\n".join(
        [
            "% Standalone table fragment. Required packages: booktabs, tabularx, array, float.",
            "\\begin{table}[H]",
            "\\centering",
            "\\scriptsize",
            "\\caption{\\textbf{Numerical benchmarks, convergence tests and acceptance status.} Each row records a claim-relevant diagnostic, its analytic or independent reference result, declared tolerance, observed value or error, and acceptance status. Checks cover the ordinary kernel and derivative, fractional $\\alpha=1$ recovery and independent reference values, the decaying-Gaussian first moment, centred-selector invariance, finite-grid refinement, invalid inputs, and the analytic/simulation overlay contract. The table supports numerical reliability and reproducible execution within the tested environment; it is not a mathematical proof of the model, an empirical validation, or evidence for excluded legacy-simulation claims.}",
            "\\label{tab:numerical-benchmarks}",
            "\\renewcommand{\\arraystretch}{1.02}",
            "\\begin{tabularx}{\\linewidth}{@{}p{0.9cm}p{3.6cm}X p{3.0cm}X p{1.8cm}@{}}",
            "\\toprule",
            "ID & Diagnostic & Expected result & Tolerance & Observed result & Status \\\\",
            "\\midrule",
            *body,
            "\\bottomrule",
            "\\end{tabularx}",
            "\\end{table}",
            "",
        ]
    )


def main() -> int:
    ensure_output_directories()
    load_config()  # Fails early if the single configuration source is invalid.
    table_one_csv = PROJECT_ROOT / "tables" / "table-01-parameter-timescale-identifiability-v1.csv"
    write_csv(table_one_csv, list(PARAMETER_ROWS[0]), PARAMETER_ROWS)
    (PROJECT_ROOT / "tables" / "table-01-parameter-timescale-identifiability-v1.tex").write_text(
        _table_one_tex(PARAMETER_ROWS), encoding="utf-8", newline="\n"
    )

    diagnostics_path = PROJECT_ROOT / "diagnostics" / "diagnostic-results-v1.csv"
    if not diagnostics_path.exists():
        raise FileNotFoundError("Run scripts/01_run_diagnostics.py before generating Table 2")
    diagnostics = read_csv(diagnostics_path)
    table_two_fields = [
        "diagnostic_id",
        "diagnostic",
        "expected_result",
        "tolerance",
        "observed_result",
        "maximum_error",
        "status",
        "supports",
        "does_not_prove",
    ]
    table_two_csv = PROJECT_ROOT / "tables" / "table-02-numerical-benchmarks-v1.csv"
    write_csv(table_two_csv, table_two_fields, diagnostics)
    (PROJECT_ROOT / "tables" / "table-02-numerical-benchmarks-v1.tex").write_text(
        _table_two_tex(diagnostics), encoding="utf-8", newline="\n"
    )

    failures = [row for row in diagnostics if row["status"] != "Verified"]
    print(f"Table 1: {len(PARAMETER_ROWS)} parameter/register rows generated as CSV and LaTeX.")
    print(f"Table 2: {len(diagnostics)} diagnostic rows generated as CSV and LaTeX.")
    if failures:
        print("Table 2 contains failed diagnostics; scientific output promotion is blocked.")
        return 1
    print("Two frozen publication tables generated; all included diagnostics are verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
