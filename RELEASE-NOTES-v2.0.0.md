# v2.0.0 — Reproducibility code for arXiv:2606.14182

This release extends the analytical reproducibility bundle for
arXiv:2606.14182 with the accepted corrected order-book simulation route.

It contains:

- six analytical figures and two publication tables;
- estimator-aware clock-only, corrected coupling-only and combined no-refit
  evidence, with Figure 7 as the key result;
- corrected receiving-front translation-mode coupling on uniform operational
  time;
- explicit book-specific previous-refresh calendar subordination;
- paired single-trade and scheduled meta-order own/cross-impact simulations;
- log-mid increment and trade-sign autocorrelation diagnostics;
- a compiled v2 computational supplement and frozen target-paper source; and
- one strict fresh-archive command with an explicit used-tree `--rerun` mode.

The historical Bauer et al. implementation was a staged computational
antecedent. Its executable surface, stored simulations and development-only
tests are not included. The README and compact provenance record preserve the
development link and document the nonuniform-update, Gaussian-source and
boundary-interface corrections.

The complete reproduction command is:

```bash
python scripts/run_all.py
```

Python 3.12 is the controlled release environment; the same route was also
verified on Windows with Python 3.13. NumPy 2.3.5 and Matplotlib 3.10.8 are
fixed exactly by `requirements.txt`.

The release is model-conditional reproducibility evidence. It does not fit
market data, provide a trading strategy or claim pointwise identity between the
paper's analytical regularization and the numerical translation-mode kernel.
