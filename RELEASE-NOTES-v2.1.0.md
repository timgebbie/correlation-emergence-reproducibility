# v2.1.0 — Recovery, long-memory clocks and impact extensions

## What changed

- Figure 7 is supplied as three standalone square PDF/PNG pairs for clock-only,
  coupling-only and combined use. The accepted three-panel composite remains
  the README overview; its source curves and all numerical logic are unchanged.
- Figure 12 adds fixed-time order-book shock recovery from the pre-event state
  through market-order consumption and 80 seconds of operational relaxation.
- Figure 13 holds the operational paths fixed while comparing direct
  operational observation with Poisson, untempered Mittag--Leffler
  (`beta=0.8`) and exponentially tempered previous-refresh clocks.
- Figure 14 applies those same observation clocks to common-input paired
  single-trade and fast/slow meta-order impact paths.
- The computational supplement now gives streamlined `algorithmicx`
  constructions for operational evolution, nested previous refresh, renewal
  clocks and paired clock-dependent impact.
- The README presents Figures 12--14 and explains the distinction between the
  operational process and its observation-clock image.
- No active `\\todo` commands remain in the release source. The unused
  `todonotes` import is retained only in the byte-frozen v1 manuscript source.

## Scientific boundary

The long-memory order flow in this release is a declared exogenous
heavy-tailed order-splitting input. It is not an endogenous result or an
empirical calibration. The Gaussian description applies to the operational
innovations, not to the waiting-time law. The lower-row central spike and
leptokurtic appearance in Figure 13 arise from zero returns under
previous-refresh observation; the operational dynamics are unchanged.

Figure 14 reports unconditional shocked-minus-control responses. An impact not
yet observed by a calendar clock contributes its actual zero paired response;
it is not discarded. No impact law, clock parameter, coupling parameter or
scientific threshold is refitted.

The six accepted Stage 7 qualifications remain unchanged. They concern the
clock-only thick-boundary approximation and five combined no-refit
approximation/stability measures; none is a new v2.1.0 failure.

## Reproduction

Python 3.12 is the controlled environment and Python 3.13 is the verified
Windows compatibility environment. From a fresh extracted release archive,
install `requirements.txt` and run:

```text
python scripts/run_all.py
```

The strict route verifies the complete archive before execution, regenerates
the retained scientific evidence, runs the regression suite and verifies the
immutable inputs. In an already-used tree, use `python scripts/run_all.py
--rerun`.

## Publication boundary

The release archive is the sole versioned asset defined for publication. The
public v2.0.0 tag and release remain frozen.
