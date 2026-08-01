# Release notes — v1.0.0

This is the first public analytical reproducibility release for arXiv:2606.14182.

The release contains six deterministic scientific figures, two publication tables, machine-readable figure data, an analytical overlay interface for the future v2.0.0 simulation extension, numerical diagnostics, sensitivity checks, and 25 regression/output tests. Figure 6 provides the accepted calendar-time Epps representation with analytical clock and response-memory diagnostics.

The complete reproduction command is:

```bash
python scripts/run_all.py
```

The supplementary material is provided as a compiled PDF in the repository and as a minimalist document-only ZIP release asset containing its LaTeX source, six figure PDFs, and two generated LaTeX tables.

The scientific boundary remains formula-first: no empirical data, calibration, stochastic order-book paths, or Julia simulation conversion is included in v1.0.0.
