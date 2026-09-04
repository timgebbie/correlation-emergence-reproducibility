# Changelog

This project uses numeric semantic versions only. Pre-release labels such as
`alpha`, `beta`, and `rc` are not used.

## `v2.1.0` — 2026-09-04 — untagged release candidate

- Align the publication contract with the v2.0.0 structure: push the untagged
  candidate first, inspect it before tagging, and publish one release archive.
  Transient Git/Drive authorization state remains outside the scientific
  repository.
- Retain the frozen v2.0.0 verifier as a compatibility check for Figures 1--11
  while the v2.1.0 audit owns the exact Figures 1--14 release surface.
- Add the R14 release-candidate contract and conformity audit. Candidate
  metadata now identifies v2.1.0 consistently while the public v2.0.0 release,
  source-v1 paper, Git tags and GitHub releases remain unchanged.
- Add v2.1.0 release notes covering Figures 12--14, the enriched algorithmic
  supplement, the accepted scientific limits and the strict archive test route.

- Extend Figure 13 at R13 to four clock domains: the unchanged Gaussian-
  innovation operational path, Poisson previous refresh, Mittag--Leffler
  previous refresh with $\beta=0.8$, and its exact exponentially tempered law.
- Replace the finite Markov Figure 13 sign fixture with a declared exogenous
  heavy-tailed meta-order-run input, while explicitly withholding any
  endogenous-memory or empirical-calibration claim.
- Add Figure 14: common-input paired single-trade and fast/slow meta-order own
  and cross impact under the same operational, Poisson, untempered and tempered
  observation domains.
- Audit the impact construction against Diana and Gebbie's
  `InteractingLOBs.jl` commit `098f1807` and retain the repository's stricter
  shocked-minus-control estimand.
- Add exact caller-driven positive-stable, Mittag--Leffler and exponentially
  tilted renewal samplers, with Laplace-transform, finite-mean and
  previous-refresh regression controls.
- Expand and streamline the algorithmicx supplement with explicit renewal-
  clock and paired-impact algorithms. Preserve the accepted R12 commit as the
  unmodified base; no tag, GitHub Release or remote upload is made at R13.
- Add the accepted fixed-time order-book shock recovery as Figure 12.
- Add the accepted six-panel operational/calendar stylised-facts comparison as
  Figure 13, using irregular background arrivals and the unchanged R7B design.
- Qualify Figure 11's operational five-second ACF as a registered finite
  periodic-schedule diagnostic whose detailed curve is phase-sensitive.
- Retain the Figure 13 scope as ordinary operational order (`alpha_u=1`), zero
  cancellation and Poisson previous-refresh observation; no fractional-memory,
  non-Markovian-clock or empirical-calibration claim is added.
- Keep the v2.0.0 tag, release assets and frozen source paper unchanged. No
  v2.1.0 tag or GitHub Release is created at this gate.
- Add a repository-level LF policy with explicit binary exclusions so a
  standard Windows checkout preserves manifest-relevant bytes.
- Route tabular, archive and assembled-figure publication through one shared
  finalization helper. Windows performs complete staged-file readback before
  atomic replacement because both CRT and native forced-flush paths can fail
  for valid completed files; POSIX retains `fsync`.
- Add implementation-audited operational-evolution and previous-refresh
  algorithms to the v2.1.0 computational supplement.
- Present Figures 12 and 13 directly in the README, including the distinction
  between uniform-operational and previous-refresh calendar rows.
- Make representative-path choices explicit and validate that each remains in
  the numerical nearest-median class, preventing roundoff-dependent drift.

## `v2.0.0` — 2026-08-26 — untagged public repository state

This promotion changes release identity and public presentation only. The
accepted v1.9.3 mathematics, source-v1 paper, numerical parameters, estimators,
curves, figures and claim thresholds are unchanged.

- Promote the sealed v1.9.3 payload to the clean v2.0.0 repository vocabulary.
- Replace v1.9.3 gate-only configuration, verification-script, diagnostic and
  test names with final-release names while preserving their checks.
- Exclude the v1.9.3 acceptance and test reports from the public payload; the
  sealed gate and Library retain those records.
- Record Python 3.12 as the controlled environment and Python 3.13 as the
  independently verified Windows environment, with NumPy 2.3.5 and
  Matplotlib 3.10.8 fixed in both.
- Preserve exactly Figures 1--11, Figure 7 as the README key result, the v2
  supplement and the compact Bauer antecedent/correction provenance.
- Keep the repository state untagged. GitHub rendering, structure, links and a
  clean clone must be inspected and accepted before the single v2.0.0 tag and
  Release are created.

## `v1.9.3` — 2026-08-25 — Bauer-retirement publication gate

This gate removes the retired Bauer executable surface and integrates the
accepted corrected model into the final public Figure 1--11 presentation.

- Remove the Bauer Julia-to-Python implementation modules, generators,
  fixtures, stored simulations, source-v0 copy, development figures and
  legacy-only tests. Preserve the sealed v1.9.2 gate and Git history as the
  recovery boundary.
- Retain compact non-executable attribution and document the exact scientific
  distinctions: uniform operational evolution, post-dynamics
  previous-refresh subordination, `exp(-mu*y^2)`, receiving-front translation
  mode, weak/local moment correspondence and distinct operational/calendar
  exponents.
- Renumber the five accepted simulation figures after analytical Figure 6:
  estimator-aware integration as Figure 7, corrected coupling as Figure 8,
  single-trade impact as Figure 9, meta-order impact as Figure 10 and
  mid-price/trade-sign autocorrelations as Figure 11.
- Make Figure 7 the README's first and key image while preserving its accepted
  pixels, curve hash, summary hash, no-refit metrics and source-v1 paper hash.
- Retain Figures 9 and 10 as the accepted impact evidence. Keep both requested
  autocorrelation estimands explicit in Figure 11 and exclude price-level
  autocorrelation.
- Replace the analytical-only supplement with the compiled v2 computational
  supplement containing Figures 1--11, the boundary-representation correction
  and the development link from the Bauer antecedent to the accepted
  Angstmann--Gebbie implementation.
- Record the complete v1.0.0--v1.9.3--v2.0.0 scientific lineage in the README
  while keeping accepted object-version suffixes where they are provenance.
- Keep all remote writes disabled. The same accepted payload is promoted to an
  untagged v2.0.0 repository state, inspected and corrected on GitHub, and only
  then tagged and released once.

## `v1.9.2` — 2026-08-25 — provisional slimming gate

This gate constructs the slim release-candidate payload without changing the
accepted mathematics, model, estimator, parameters, curves or source-v1 paper.

- Preserve the sealed v1.9.1 archive as the full comparison parent, with
  SHA-256 `416c81194ea6fa102c8995ddf97d591969851364a197a8d1e78ef55ac9929361`.
- Reduce the initial extracted payload from approximately 75 MiB to 25 MiB by
  excluding 132 proven nondependencies, mainly stored member/path outputs,
  intermediate presentation figures, obsolete stage scripts/tests and gate
  transcripts.
- Retain six analytical figures and five final-v2 simulation figures: current
  Figures 26, 21, 23, 24 and 25. Keep Figures 7--9 temporarily only for the
  isolated Bauer verification boundary.
- Retain 33 earlier test modules containing 307 tests and add 12 focused
  v1.9.2 tests. Remove 13 development-only modules containing 131 tests.
- Restrict the active route to analytical outputs, operational and
  subordination invariants, clock-only conformity, corrected coupling,
  combined no-refit prediction, impact/dependence experiments and the final
  estimator-aware integration.
- Preserve Figure 26's accepted curve/data fingerprints and numerical metrics
  as the primary full/slim equivalence object.
- Repair two cross-platform test contracts found by the external Windows
  Python 3.13 audit: use the production gate's explicit `1e-9` tolerance for
  the synthetic curvature length, and preserve Figure 26's exact PNG hash as a
  sealed-archive fingerprint rather than requiring identical post-run raster
  bytes. The Windows-regenerated component CSVs differed from the accepted
  values by at most `8.15e-14`, and validation prices by at most `7.02e-14`;
  all schemas, lags, shapes, frozen scales and scientific gates were unchanged.
- Correct four prose-only standardized-RMSE references from `0.454980` to
  `0.455132`, matching the accepted hash-frozen summary and exact regenerated
  result. No calculation, curve, estimator, parameter or source-v1 byte is
  changed.
- Restore the required next gate as v1.9.3. It removes the entire Bauer
  executable surface, updates the README and v2 computational supplement, and
  renumbers the five selected simulation figures after analytical Figure 6.
- Keep all remote writes disabled. The untagged v2.0.0 GitHub presentation is
  pushed and inspected only after v1.9.3 acceptance.

## `v1.9.1` — 2026-08-24 — provisional gate

This gate streamlines the release-facing bundle without changing a model,
estimator, accepted curve or source-v1 paper file.

- Promote Figure 26 to the first and key README figure for the future GitHub
  update, with its no-refit estimator-aware interpretation stated directly.
- Replace the 920-line development diary in the README with a concise
  release-facing guide; keep detailed stage history in this changelog and the
  existing provenance records.
- Retain one active entrypoint, `scripts/run_all.py`, with strict fresh-archive
  verification by default and an explicit `--rerun` mode for an already-used
  tree.
- Keep historical input/clock generators as provenance-only commands and the
  superseded Stage 7 closure checker as development-only; none enters the
  active route.
- Preserve the accepted archive ledger and immutable-source checks. Mark
  development-only material for exclusion from the v2.0.0 package only after
  the final dependency check, rather than deleting scientific evidence now.
- Freeze the final GitHub identity as tag `v2.0.0`, release title beginning
  `v2.0.0 — ...`, README version line `Version: v2.0.0`, and archive
  `correlation-emergence-reproducibility-v2.0.0.zip`, following the public
  reaction-boundary-vol-surface bundle's presentation convention.
- Add 20 executable release-surface checks and focused regression tests,
  including the final GitHub identity and README key-figure requirements.
- Assign physical payload pruning to numeric gate `v1.9.2`. That gate maps
  every file and test to a current scientific claim, excludes development-only
  material only after dependency analysis, and proves that the slim payload
  reproduces the full bundle's claim-bearing Figure 26 outputs before
  `v2.0.0` is published.
- Extend the executable release-surface total to 21 checks for this mandatory
  pre-release boundary.

## `v1.9.0` — 2026-08-24 — accepted

This gate completes the final estimator-aware Epps theory/simulation
integration without rerunning or fitting the accepted component simulations.

- Assemble clock-only theory/simulation, corrected coupling-only
  theory/simulation, combined no-refit simulation, the leading-order product
  and the exact finite-grid, finite-step same-clock reference.
- Use one common linear 0--400 second and 0--1.1 normalized-covariance scale
  across all three panels of new Figure 26.
- Reduce the combined theoretical RMSE from `0.066963` for the leading-order
  product to `0.039719` for the estimator-aware reference; retain standardized
  RMSE `0.455132` and full pointwise normal-band coverage.
- Preserve all clock rates, coupling rates, boundary normalization, accepted
  simulation curves, source-v1 text and acceptance thresholds exactly.
- Verify 24 generated integration checks and focused regression tests. The
  accepted gate advances to `v1.9.1` release streamlining before `v2.0.0`.

## `v1.8.3` — 2026-08-21 — provisional gate

This Stage 8 closure candidate establishes mid-price-increment and
three-convention trade-sign dependence diagnostics without changing an
accepted model parameter or adding a theoretical curve.

- Complete 768 fully filled market events on one uniform operational event
  tape before introducing either book-specific observation clock.
- Measure five-second log-mid increment autocorrelation on the operational
  path and after explicit previous-refresh subordination; exclude price-level
  autocorrelation from the registered estimands.
- Measure ground-truth aggressor, quote/midpoint and frozen legacy tick-rule
  signs separately on the same event records, including exact pairwise
  agreement and misclassification counts.
- Keep same-book event-lag sign autocorrelation separate from five-second
  calendar-binned signed-flow autocorrelation after subordination.
- Register the declared finite Markov sign persistence as an exogenous
  estimator fixture, not endogenous long memory or empirical calibration.
- Generate Figure 25, nine machine-readable CSV datasets and one compressed
  path archive; verify all 49 generated checks and 10 focused regression
  tests.
- Preserve passive limit orders as nontrades, complete operational dynamics
  before calendar observation, and forbid nonuniform state updates,
  interpolation, refitting and source-v1 changes.
- Close Stage 8 on external acceptance and advance to `v1.9.0`, the final
  estimator-aware combined Epps theory/simulation integration.

## `v1.8.2` — 2026-08-21

This Stage 8 subphase establishes scheduled meta-order own and cross impact on
the accepted operational-time and explicit-subordination architecture. It
changes no accepted coupling rate, clock rate, source convention or source-v1
paper text.

- Define a meta-order as four separately labelled and fully filled child
  market orders, each applied immediately before its declared uniform
  operational step rather than as one enlarged density shock.
- Compare equal total signed volume under 15-second and 60-second execution
  horizons while holding child size, innovation paths and all accepted model
  parameters fixed; report schedule intensity separately from the
  non-identified true participation rate.
- Measure the complete two-by-two own/cross-impact matrix after every child
  and through 200 seconds after completion, first in operational time and then
  after the two accepted distinct book-specific previous-refresh clocks.
- Separate own-impact build-up, peak post-completion cross-impact catch-up and
  long-lag own/cross convergence so transmission during slow execution is not
  conflated with post-completion relaxation.
- Generate Figure 24 on one common linear scale, 64 trajectory-curve rows,
  1,024 trajectory-member rows, 144 relaxation-curve rows, 2,304
  relaxation-member rows, 256 child-event records and a compressed path
  archive.
- Inherit the v1.8.1 translation-mode boundary architecture with no independent
  selector width or mesoscale thickness parameter, and add the required
  meta-order operational/subordination supplementary insert.
- Verify all 50 generated checks and 10 focused regression tests. Dependence
  diagnostics remain assigned to `v1.8.3`.

## `v1.8.1` — 2026-08-21 — provisional gate

This Stage 8 subphase establishes paired single-market-order own and cross
impact on the accepted operational-time and explicit-subordination
architecture. It changes no accepted coupling rate, clock rate or source-v1
paper text.

- Apply one fully filled market-order density delta immediately before its
  declared uniform operational step and compare the shocked path with a
  common-innovation control.
- Measure the complete two-by-two own/cross-impact matrix in operational time,
  then measure the same completed paths after two distinct book-specific
  previous-refresh clocks; calendar interpolation and nonuniform state updates
  remain forbidden.
- Generate Figure 23 on one common linear scale, 96 curve rows, 1,536 member
  rows, 32 event records and a compressed path archive.
- Recover positive own impact at the event state, delayed positive cross
  impact, book-exchange symmetry and long-lag own/cross convergence.
- Define buy/sell symmetry using the largest absolute side difference divided
  by each domain's peak own-impact scale. The earlier cellwise relative form is
  retained as a diagnostic only because it is ill-conditioned for near-zero
  early calendar cross-impact.
- Register the required supplementary contrast: the paper's bounded
  regularised source is an analytical weak-moment closure, whereas the
  production numerical source directly excites the current reaction-front
  translation mode and needs no independently chosen selector width.
- Verify all 44 generated checks. Meta-orders remain assigned to `v1.8.2` and
  dependence/sign diagnostics to `v1.8.3`.

## `v1.8.0` — 2026-08-21 — provisional gate

This Stage 8 entry gate adds deterministic event semantics and registers the
impact/dependence programme. It adds no stochastic path, scientific figure,
source-v1 change or model-parameter change.

- Add validated limit-order and market-order records with book, operational
  step, side, quantity and optional meta-order identifiers.
- Place passive limit liquidity in one interior noncrossing uniform-grid cell;
  consume opposing market liquidity from the reaction boundary outwards under
  an explicit full/partial-fill policy.
- Keep event density deltas separate from the uniform operational solver and
  keep complete operational paths separate from book-specific calendar-time
  subordination.
- Implement ground-truth aggressor, quote/midpoint and frozen legacy tick-rule
  sign conventions without silently substituting one for another.
- Register the complete two-by-two own/cross-impact matrix, common-random-number
  comparison contract and the `v1.8.1`--`v1.8.3` sequence.
- Register `v1.9.0` for the final estimator-aware combined Epps display and
  `v1.9.1` for release streamlining before `v2.0.0`.
- Add 44 deterministic gate checks, 26 registered contracts and 12 focused
  regression tests. No stochastic event experiment is run at this entry gate.

## `v1.7.12` — 2026-08-21

This accepted gate performs the stability and integrity audit required to
close Stage 7. It changes no scientific model, parameter, estimator, curve or
source-v1 paper and adds no figure. The accepted parent is v1.7.11 at commit
`28da9526105dbef834f4c134eca422eb2d9306bb`.

- Add an executable 28-check closure audit covering accepted-parent hashes,
  exact numerical runtime versions, complete-archive and immutable-source
  manifest partitioning, workspace hygiene, Stage 7 diagnostics, result labels,
  figure pairs and the operational/calendar layer boundary.
- Freeze the complete Stage 7 evidence inventory at 253 checks: 244 verified,
  six scientifically qualified, three invalid preconditions and zero failed.
- Preserve Figures 16--22 as seven distinct PDF/PNG pairs and retain legacy
  Figure 7 as the preliminary test/reference case.
- Preserve the exact accepted result sequence: clock-only reference recovered
  with a qualified thick boundary; preliminary coupling reference recovered
  with an invalid thick-boundary experiment; corrected translation-mode
  coupling recovered; and combined prediction qualified without refitting.
- Require an exact 370-entry complete-archive manifest and 226-entry
  immutable-source subset, with no symbolic links, staging files or backups in
  the distributable workspace.
- Verify the complete preparation route with all 28 closure checks, all 379
  regression tests and all 226 post-run immutable-source entries passing.
- Verify the exact packaged gate again from a clean extraction with the same
  28/28 closure, 379/379 regression and 226/226 immutable-source results.
- Freeze the architectural result: uniform operational dynamics precede
  book-specific previous-refresh subordination; nonuniform state updates,
  interpolation and component/combined refits remain forbidden.
- Record external acceptance, closing Stage 7 and opening `v1.8.0`, the
  event-semantics and impact entry stage.

## `v1.7.11` — 2026-08-21

This accepted corrected Stage 7 gate carries forward the scientifically
unchanged v1.7.10 result and corrects one over-tight fixed-point assertion
exposed by native Windows execution. The density fixed-point tolerance remains
`2e-12`. The price-root tolerance is `3e-12`, which is no tighter than the
density tolerance divided by the measured minimum boundary slope. No numerical
scheme, solver parameter, estimator, generated scientific curve or acceptance
threshold changes. Stage 7 stability, integrity and closure moves to v1.7.12.

- Preserve the complete v1.7.10 scientific and reproducibility implementation,
  including exact numerical-library pins, fresh-archive verification and
  post-run immutable-source verification.
- Replace only the stationary uncoupled one-step price assertion tolerance
  `5e-13` with the slope-consistent value `3e-12`; retain zero relative
  tolerance and the existing density tolerance `2e-12`.
- Assert directly that the price tolerance is at least the density tolerance
  divided by the measured minimum absolute boundary slope, so the two
  fixed-point criteria cannot silently become inconsistent again.
- Verify the complete Linux route with 364/364 fresh-archive entries,
  369/369 regression tests and 222/222 post-run immutable-source entries.
- Record the v1.7.10 external Windows result: all scientific stages passed,
  including S6R-01 and S6R-21, before one of 369 tests differed from zero by
  `6.185399e-13`, exceeding the old price tolerance by only
  `1.185399e-13`.
- Move Stage 7 stability, integrity and closure to `v1.7.12`, preserving the
  numeric-only policy and preventing two distributed archives from sharing a
  version number.
- Record acceptance on 2026-08-21 after the external v1.7.10 route established
  that every scientific stage passed and the user accepted the narrowly
  classified, test-only slope-consistency correction. The exact v1.7.11 ZIP
  also passed the complete clean-extraction Linux route.

## `v1.7.10` — 2026-08-21 — superseded gate candidate

This provisional corrected Stage 7 gate carries forward the combined clock and
corrected-coupling prediction with all accepted component parameters frozen.
The exact reduced estimator-aware reference is recovered, while the paper's
explicitly leading-order product and the thick-boundary combination retain
registered scientific qualifications. The scientific outputs are unchanged
from the superseded v1.7.8 and v1.7.9 candidates. This gate freezes the
numerical environment and separates fresh-archive integrity from post-run
immutable-source integrity. The complete Linux route passes with 364/364
fresh-archive entries, 369/369 tests and 222/222 post-run immutable entries.
Native Windows execution subsequently passed every scientific stage, including
the formerly failing S6R-01 and S6R-21 checks, but exposed one over-tight
stationary price-root test. The candidate was neither accepted nor tagged; its
implementation is carried forward unchanged in v1.7.11 apart from that test
tolerance and the executable consistency assertion.

- Complete both books on the uniform operational grid before applying two
  independent equal-rate previous-refresh clocks. Exclude nonuniform state
  updates, interpolation and terminal-state clamping.
- Freeze the equal book rate `0.1 s^-1`, total coupling rate `0.025 s^-1`,
  ordered coupling parameters and accepted thick-boundary covariance scale;
  prohibit all component and combined refitting.
- Add an exact conditional reference for the symmetric reduced process given
  the operational indices selected by the realised clocks. The simulation
  recovers its covariance and correlation with RMSE `0.008530` and `0.002296`,
  standardized RMSE below `0.41` and full pointwise coverage.
- Measure intrinsic estimator-level nonseparability: the exact reduced
  reference differs from the leading-order product by RMSE `0.037391`, above
  the registered `0.03` threshold.
- Separate the thick-boundary covariance residual from the estimator residual.
  Thick minus exact reduced same-clock RMSE is `0.039719`; total RMSE versus
  the analytical product is `0.066963`, and RMSE versus the accepted component
  product is `0.056040`.
- Generate Figure 22, 20 curve/decomposition rows, three summary rows, four
  measured clock-rate rows, a compressed path/component archive and 38 checks:
  33 verified, five qualified and zero failed.
- Preserve the source-v1 paper and record that the result quantifies the
  limitations already allowed by its leading-order separability assumptions;
  it is not an implementation failure or a rejection of the conditional
  theory.
- Replace the Windows `os.fsync`/CRT `_commit` path with native
  `FlushFileBuffers` on the write-capable staged-file handle. POSIX retains
  `os.fsync`; atomic replacement and cleanup remain unchanged. Add explicit
  tests for both platform routes.
- Pin NumPy `2.3.5` and Matplotlib `3.10.8`, use canonical LF text output, and
  reject a mismatched numerical runtime before simulation begins.
- Verify the complete archive manifest before executing generators, then
  verify a separate immutable-source manifest after the full route. Validate
  generated artifacts through numerical, schema and scientific tests rather
  than requiring platform-identical rendering bytes.
- During a verified complete route, resolve accepted-input provenance against
  the fresh-archive manifest; retain strict current-byte checking for
  standalone stages and within-stage input immutability checks.
- Record that external v1.7.9 execution verified all 358 archive entries and
  the Windows figure-publication fix before the unfrozen environment caused
  Stage 6 accepted-output hashes to diverge.
- Move Stage 7 stability, integrity and closure to `v1.7.11`, preserving the
  numeric-only policy and preventing two distributed archives from sharing a
  version number.

## `v1.7.9` — 2026-08-21 — superseded gate candidate

This candidate carried the unchanged combined no-refit result and corrected
the Windows figure-publication path. External Windows Python 3.13 execution
verified all 358 archive entries and generated Figures 1 through 15, confirming
the `FlushFileBuffers` correction. It then failed Stage 6 checks S6R-01 and
S6R-21 because range-based requirements installed NumPy `2.5.2` and
Matplotlib `3.11.1` instead of the preparation environment's NumPy `2.3.5`
and Matplotlib `3.10.8`. The candidate was neither accepted nor tagged. Its
scientific scope and Windows publication fix are carried forward in v1.7.10.

## `v1.7.8` — 2026-08-20 — superseded gate candidate

The first combined no-refit candidate produced the same frozen scientific
result as v1.7.9, but external Windows Python 3.13 execution failed during
Figure 10 publication with `OSError: [Errno 9] Bad file descriptor` at
`os.fsync`. The candidate was neither accepted nor tagged. Its scientific
scope is carried forward unchanged in the corrected numeric gate `v1.7.9`.
That candidate was also superseded after its external environment-integrity
failure; the scientific scope was carried through v1.7.10 to the active
corrected gate `v1.7.11`.

## `v1.7.7` — 2026-08-20

This accepted Stage 7 gate implements the selected translation-mode coupling
in three separate operational modules and independently recovers its
deterministic response rate and stochastic coupling-only curves. All 343
manifest entries, the complete route and all 349 tests passed from a fresh
extraction; external acceptance was recorded on 2026-08-20.

- Add `TranslationModeCoupling` with
  `ell_T=-kappa_jk*z_jk*(-partial_x(phi_j_current))`, an explicit ordered
  response rate and no selector-width reinterpretation.
- Split coupling density, one-step solver entry and rolling path assembly into
  `translation_coupling.py`, `translation_solver.py` and
  `translation_path.py`; retain the accepted regularised implementation as an
  exact-hash comparator.
- Require eight signed deterministic perturbations and three-grid convergence
  before any stochastic recovery is executed. The maximum exponential-rate
  and local-drift relative errors are `0.006117` and `0.000645`.
- Freeze the stochastic covariance scale from 16 disjoint calibration paths,
  then validate on 32 independent paths under identity clocks. The normalized
  covariance response has RMSE `0.016700`, and the distinct exact return
  correlation has RMSE `0.008772`; both have full pointwise coverage.
- Record 38 verified generated checks, 20 curve rows, 11 rate rows, 1,288
  deterministic response rows, a compressed holdout archive and Figure 21.
- Keep all dynamics on the uniform operational grid. No nonuniform update,
  subordination, calendar interpolation or combined-curve refit occurs.
- Retain the paper's reduced response while qualifying the unproven bridge
  from the regularised `tanh` source amplitude to an effective response rate.
  The accepted source-v1 paper remains unchanged; the interpretation is
  recorded in a source-v2 overlay.

## `v1.7.6` — 2026-08-20

This accepted Stage 7 design gate selects a projection-consistent coupling
correction without changing the accepted production coupling, uniform solver,
path implementation or source-v1 paper snapshot. All 325 manifest entries,
the complete route and all 332 tests passed from a fresh extraction; external
acceptance was recorded on 2026-08-20.

- Compare four correction candidates and select the current-front translation
  mode `ell_T=-kappa_jk*z_jk*v_j`, with
  `v_j=-partial_x(phi_j_current)` from the immutable pre-step receiving-book
  density.
- Fix the ordered-pair sign so that a receiving book above the other book has
  negative drift and the reciprocal book has positive drift.
- Replace the legacy source-amplitude semantics in the corrected path by
  explicit ordered response rates. The symmetric target uses `1.25+1.25=2.5`
  per model-time unit, or `0.025 s^-1` in total.
- Remove the fixed-`epsilon` selector from the claim-bearing linear response.
  The old smooth source remains an immutable comparator; hard-side or
  fixed-spatial-width side flow is deferred to a projection-orthogonal
  robustness extension.
- Show in nine deterministic signed-spread probes that the existing solver
  recovers total rates from `2.498338` to `2.499672`, with maximum relative
  error `0.000665`, zero pair-centre drift to numerical precision and unique
  interior reaction boundaries.
- Freeze the v1.7.7 implementation contract: add a distinct
  `TranslationModeCoupling`, pass the deterministic independent-rate gate
  before stochastic Epps validation, and prohibit combined-curve refitting.
- Add 26 generated design checks, two machine-readable design outputs, a
  source-v2 derivation overlay and nine regression tests.

## `v1.7.5` — 2026-08-20

This accepted Stage 7 gate executes coupling-only conformity under identity
clocks. All 316 manifest entries, the complete route and all 323 tests passed
from a fresh extraction; external acceptance was recorded on 2026-08-20. The
reduced reference is recovered, but the accepted thick-boundary coupling fails
the independently registered positive-rate precondition. The combined no-refit
prediction is therefore not executed.

- Add an exact symmetric linear-SDE reference with a stationary OU spread and
  keep its normalized covariance response distinct from its exact finite-scale
  return correlation.
- Recover the registered reduced response with covariance RMSE `0.008231`,
  standardised RMSE `0.312156`, full pointwise coverage and measured rate
  `0.0250074 s^-1`, a relative rate error of `0.000295`.
- Add deterministic translation-mode perturbations and paired uncoupled
  controls on the accepted uniform operational grid.
- Show analytically and numerically that the current regularised coupling's
  linear-in-spread term is proportional to the base source and changes front
  amplitude rather than translating the zero crossing.
- Record non-positive exponential and local-drift rates at every positive
  `gamma` in the declared scan. The required `2.5` per model-time-unit rate is
  not bracketed, so the stochastic thick-boundary Epps experiment is labelled
  `invalid_experiment` and not run.
- Add Figure 20, 20 reduced-reference curve rows, six rate rows, 7,728 paired
  response rows, a two-row decision summary, 23 generated checks and 18 new
  regression tests.
- Harden the shared CSV/JSON publisher after the integrated route exposed
  incomplete large-file replacement. Outputs are now written to a dedicated
  same-filesystem staging area, flushed, fsynced and atomically replaced; an
  interrupted row source preserves the previously accepted target.
- Preserve the accepted paper source and record the derivation in a separate
  source-v2 overlay; no replacement coupling is selected at this gate.
- Block the formerly scheduled combined gate and adopt `v1.7.6` for correction
  design, `v1.7.7` for corrected coupling recovery, `v1.7.8` for the combined
  no-refit prediction and `v1.7.9` for Stage 7 closure.

## `v1.7.4` — 2026-08-14

This accepted Stage 7 gate executes clock-only conformity. All 299 manifest
entries, the complete route and all 305 tests passed from a fresh extraction;
external acceptance was recorded on 2026-08-14.

- Add a separate exact previous-refresh observation object without changing
  the accepted general inverse-clock implementation or uniform solver.
- Correct the equal-rate analytical mapping: `F(lambda*Delta)` uses each
  equal book rate `lambda=0.1 s^-1`; the exact minimum-wait rate is `0.2 s^-1`
  and is retained only as a rejected attenuation diagnostic.
- Recover the reduced correlated-Brownian reference with curve RMSE `0.006474`,
  standardised RMSE `0.518405`, full pointwise coverage and exact-overlap RMSE
  `0.000162`.
- Execute 16 calibration and 32 validation uncoupled reaction-boundary paths,
  crossed with four independent clock replications per validation path.
- Retain the full thick-boundary result as `qualified_nonconformity`: its
  absolute RMSE `0.032471` exceeds `0.03`, while standardised RMSE `0.815378`,
  95% pointwise coverage, plateau stability, exact overlap and all solver
  invariants pass.
- Add Figure 19, 40 machine-readable curve rows, two summary rows, the frozen
  boundary-price archive, 22 generated checks and 14 new regression tests.
- Open `v1.7.5` coupling-only work because the
  reduced clock reference is recovered; carry the qualified full-model clock
  residual into the no-refit combined interpretation.

## `v1.7.3` — 2026-08-14

This accepted design-only subphase reopens the conformity experiment after the accepted
v1.7.2 discrepancy without changing the accepted operational solver,
subordination implementation, simulation parameters or Figure 18 evidence.

- Freeze reduced-reference and full thick-boundary tiers for clock-only,
  coupling-only and combined recovery.
- Replace the invalid zero-correlation clock control by declared nonzero
  operational-correlation benchmarks.
- Set the two Poisson book rates from the analytical clock target and measure
  them from waiting intervals rather than fitting an Epps curve.
- Require the thick-boundary coupling rate to be measured independently from
  local spread drift and small-perturbation relaxation. Only `coupling_gamma`
  may be calibrated in the primary coupling experiment; the thickness and
  source parameters remain fixed.
- Propose a resolved dimensional map with a 0.5-second operational step, 20
  steps per clock timescale and 80 steps per coupling timescale. This remains
  a candidate until executed at `v1.7.4`.
- Separate calibration and validation paths, seeds and lags; predeclare rate,
  plateau, RMSE, standardised-residual and coverage criteria.
- Forbid any combined-curve refit. The combined curve at `v1.7.6` is an
  out-of-sample test of the leading-order separability approximation.
- Add six machine-readable experiment cells, 25 generated design checks and
  eight regression tests. Acceptance opens clock-only recovery at `v1.7.4`.

## `v1.7.2` — 2026-08-14

This accepted Stage 7 subphase adds Figure 18 and target `OVL-EPP-01`, the
registered analytical Figure 6--simulation discrepancy diagnostic.

- Preserve accepted analytical Figure 6 and simulated Figure 17 by exact
  hashes; the overlay route does not regenerate either source figure.
- Join the 20 accepted simulated lags to existing analytical abscissae exactly.
  No interpolation, fitted time map or fitted correlation normalisation is
  introduced.
- Superimpose the analytical clock, coupling and combined curves with the
  simulated path-group mean, its normal 95% band and the separate pooled
  estimate on the accepted linear 0--400 second, 0--1.05 comparison scale.
- Add a signed-difference panel for simulation minus the analytical combined
  curve, with the simulation uncertainty band shifted by the same fixed
  analytical reference.
- Record the conditional finite-ensemble result that the simulation upper band
  remains below the illustrative analytical combined curve at all 20 matched
  lags. This is not a calibrated goodness-of-fit test or a general model
  rejection.
- Retain 3,244 machine-readable overlay rows and 20 exact comparison rows.
  Add 25 generated checks and eight regression/output tests.
- Acceptance fixes the discrepancy evidence without asserting conformity or
  closing Stage 7. It opens the `v1.7.3` theory-conformity design.

## `v1.7.1` — 2026-08-14

This Stage 7 subphase was accepted after all 268 manifest entries, all 30
generated Figure 17 checks and the complete 275-test route passed from a fresh
extraction. It adds Figure 17 and target `SIM-F6-01`, the simulation analogue
of analytical Figure 6.

- Map the accepted pooled simulation clock rate `400` per model-calendar unit
  to the analytical Figure 6 clock rate `0.1 s^-1`. This fixes `4,000` seconds
  per model-calendar unit and a `20` second stored calendar step without
  fitting the Epps curve.
- Display accepted independent-Poisson simulation estimates from 20 through
  400 seconds on the Figure 6 dimensional axis.
- Retain a linear Figure 6 comparison panel on `0--400` seconds and
  normalised correlation `0--1.05`, then repeat the same curve on an aligned
  linear detail panel with limits `-0.22--0.30` so that the complete
  uncertainty band remains readable. Do not import the legacy Figure 7
  normalisation or use a logarithmic correlation axis.
- Normalise by the registered finite-window plateau proxy: the arithmetic
  mean of accepted equal-weight path-group correlations over lags 501--600.
- Derive increment autocorrelations directly from the explicitly subordinated
  reaction-boundary price paths using overlapping Pearson lag pairs.
- Derive one-sided Hann Welch spectra from the same increments using 256-point
  segments, 50% overlap and memberwise unit-integral normalisation.
- Average the two books and two clock replications within each operational
  path before estimating uncertainty across eight path groups.
- Retain 20 aggregate curve rows, 320 curve-member rows, 140 diagnostic rows
  and 4,480 diagnostic-member rows. Analytical Figure 6 and accepted Figure
  16 remain byte-identical.
- Add 30 generated checks and 12 regression/output tests. The analytical
  overlay remains a separate `v1.7.2` gate.

## `v1.7.0` — 2026-08-14

The Stage 7 entry gate was accepted after all 255 manifest entries, all 26
generated Figure 16 checks and the complete 263-test route passed from a fresh
extraction. It adds new Figure 16 and target `UPD-EPP-01`.
Legacy Figure 7 remains an immutable, separately numbered test/reference case.

- Assemble the accepted corrected uniform-operational curve and the accepted
  independent-Poisson calendar image without rerunning dynamics or clocks.
- Put operational scale `Delta u` and calendar scale `Delta t` in separate
  panels, with no interpolation or legacy nonuniform solver step.
- Use the equal-weight eight-operational-path mean as the primary estimate.
  Average two clock replications within path before calendar uncertainty.
- Retain the pooled realised correlation separately from the path-group mean
  and its normal 95% standard-error band.
- Preserve raw realised correlation at this gate; the analytical Figure 6
  scale and normalisation map remains `v1.7.1`--`v1.7.2` work.
- Retain 1,200 aggregate rows and 14,400 member rows, generate Figure 16 as
  PDF/PNG, and protect nine accepted inputs including Figure 7 by exact hashes.
- Add 26 generated checks and 11 regression/output tests. Independent
  acceptance is required before `v1.7.1` begins.

## `v1.6.2` — 2026-08-14

The Stage 6 closing gate was accepted after all 245 manifest entries, all 22
generated robustness checks and the complete 252-test route passed from a
fresh extraction and independently on Windows.

- Protect the accepted member and decomposition inputs with exact SHA-256
  values before and after the analysis.
- Average the two clock replications within operational path before omitting
  each of the eight path groups in turn.
- Recover the accepted grouped means exactly and their standard errors through
  the equivalent jackknife construction.
- Retain 57,600 pointwise omission rows, 288 bandwise omission rows and 36
  short-, medium- and long-band summaries.
- Verify that the long-band boundary contrast and total change remain positive
  under every omission for every nonidentity clock, and that the stable-clock
  long-band interaction remains negative under every omission.
- Generate Figure 15 with full grouped contrasts and omission envelopes for all
  three nonidentity clock scenarios.
- Freeze the next figure sequence: new Figure 16 corrected target at `v1.7.0`
  while Figure 7 remains the legacy test case, simulated Figure 6 at `v1.7.1`,
  and the analytical/simulation overlay at `v1.7.2`. Event semantics and
  impact begin only in Stage 8.
- Add 22 generated closing checks and 12 regression/output tests. Independent
  acceptance closes Stage 6 and opens the corrected figure target at `v1.7.0`.

## `v1.6.1` — 2026-08-14

The corrected Stage 6 entry gate was accepted after all 232 manifest entries,
all 22 generated mechanism-entry checks and the complete 240-test route passed
from a fresh extraction and independently on Windows Python 3.13. It supersedes
the unaccepted `v1.6.0` candidate.

- Freeze a matched two-by-four design: uncoupled control versus regularised
  reaction-boundary coupling, crossed with identity, independent Poisson,
  60% common-wait diagnostic and independent stable clocks.
- Reuse the accepted Stage 4 operational paths and Stage 5 clock paths. The
  two boundary cells share operational innovations, path index, clock path,
  common calendar support and aggregation lags.
- Define the reference cell, boundary main contrast, clock main contrast and
  clock-boundary interaction as an exact descriptive difference-in-
  differences decomposition. This is a computational mechanism attribution,
  not an empirical causal estimate.
- Form member contrasts before averaging the two clock replications within
  each operational path. Estimate dispersion and standard errors only across
  the eight operational-path groups.
- Generate all 4,800 factorial-cell rows, 76,800 member rows and 1,800
  decomposition rows. Figure 14 displays the four independent-Poisson cells
  and their pooled decomposition; the other clocks remain machine readable.
- Refactor the repeated identity-clock construction into one tested observation
  factory without changing the accepted Stage 5 result.
- Complete a workspace and stability audit. Remove only ignored Python and
  Matplotlib caches; retain the legacy implementation as active provenance and
  a regression comparator. Confirm a clean repository, clean object database,
  no symbolic links, and no editor, backup or atomic-staging remnants.
- Correct atomic figure publication for Windows by opening the completed
  staging file with write access before `fsync`; retain atomic replacement and
  add a platform-independent regression check for this handle contract.
- Add 22 generated Stage 6 entry checks and 13 tests. Mechanism robustness and
  Stage 6 closing evidence remain `v1.6.2`.

## `v1.6.0` — 2026-08-14 — superseded gate candidate

The first Stage 6 entry candidate implemented the paired mechanism experiment,
but independent Windows Python 3.13 execution failed during figure publication
because `os.fsync` received a read-only descriptor. This candidate was neither
accepted nor tagged. Its scientific scope is carried forward unchanged in the
corrected numeric patch gate `v1.6.1`.

## `v1.5.2` — 2026-08-14

The Stage 5 timestamp-aware estimator and closing gate was accepted after all
217 manifest entries, all 20 generated calendar-estimator checks and the
complete 227-test route passed from a fresh extraction.

- Retain the complete Stage 4 coupled and matched-control reaction-boundary
  paths in a hash-validated clock-free bridge archive.
- Apply each declared book clock through the accepted previous-completed-state
  inverse on one explicit common calendar grid. Select the analysis horizon by
  flooring the minimum realised support over all books, paths and scenarios.
- Reject extrapolation and terminal-state clamping. Record window counts,
  individual-book active counts and jointly active counts at every lag.
- Pair 16 clock paths with eight operational paths using two clock replications
  per path. Average replications within operational-path groups before
  computing the eight-group standard error.
- Generate 600-lag curves for identity, independent Poisson, 60% common-wait
  diagnostic and independent positive-stable clocks. Retain 2,400 aggregate
  rows, 38,400 member rows and 64 support/provenance rows.
- Add Figure 13 as the calendar-time completion of `SUB-EPP-01`, the historical
  Bauer Figure 5 project alias. Do not overwrite the released analytical
  Figure 5, which has a different scientific role.
- Overlay only the qualified Poisson separable reference. It is not fitted and
  is not an exact prediction for the coupled finite sample. Do not invent an
  exact joint-overlap reference for the distinct stable exponents.
- Add 20 generated checks and 12 tests. This gate closes Stage 5; paired
  clock-versus-boundary mechanism experiments begin in the `v1.6.x` stage.

## `v1.5.1` — 2026-08-14

The Stage 5 stochastic clock-ensemble gate was accepted after its 202-entry
manifest, all 20 generated clock-ensemble checks and the complete 215-test
route passed from a fresh extraction.

- Add caller-driven exponential and positive-stable clock transforms under
  `functions/observation/`; these functions contain no random generator.
- Keep the paper's independent Poisson-refresh benchmark distinct from its
  inverse-stable fractional benchmark. The stable `alpha_t=1` limit is
  deterministic drift rather than an exponential wait.
- Generate and retain 16 complete two-book paths over 2,400 operational steps
  for each of three scenarios: independent Poisson waits, a controlled 60%
  common-wait mixture, and independent stable subordinators with
  `alpha_t=(0.8,0.65)`.
- Record all interval arrays, cumulative clock paths, clock-law parameters,
  stream identifiers, seed provenance, supported horizons and array hashes.
  Stored arrays are authoritative; there is no empirical calibration claim.
- Mark the common-wait mixture as a controlled dependence diagnostic rather
  than part of the independent Poisson derivation. Keep `alpha_t` separate
  from the operational-memory exponent.
- Add 20 generated checks, 96 path-book summary rows and 12 tests. The
  timestamp-aware calendar estimators and subordinated Figure 5 remain
  `v1.5.2`.

## `v1.5.0` — 2026-08-13

The Stage 5 entry gate was accepted after its 191-entry manifest, all 15
generated clock/subordination checks and the complete 203-test route passed
from a fresh extraction.

- Add a separate observation layer for explicit book-clock paths, inverse
  clocks and pathwise operational-to-calendar subordination.
- Keep the numerical dynamics on the accepted uniform operational grid. Clock
  intervals are caller-supplied realised data and never become solver steps.
- Record each clock's law, stream identifier, optional seed provenance and
  supported calendar horizon without giving the observation layer an RNG.
- Declare the finite-grid previous-completed-state map
  `n(t)=max{n:T(u_n)<=t}`. Exact clock nodes retain their same-index state;
  identity clocks recover stored operational paths exactly.
- Reject interpolation and extrapolation. The discrete map is documented as a
  step-function approximation to the continuous theoretical inverse
  `E(t)=inf{u:T(u)>t}`.
- Exercise two explicit, distinct equal-mean book clocks. Swapping the clocks
  leaves the operational path unchanged and changes only its calendar image.
- Add 15 generated checks, 52 machine-readable fixture rows and 13 tests.
  Stochastic clock ensembles and timestamp-aware estimators remain later
  Stage 5 subphases.

## `v1.4.3` — 2026-08-13

The complete uniform-operational ensemble and Stage 4 closing gate was
accepted after its 182-entry manifest and complete 190-test route passed from
a fresh extraction.

- Add an ensemble runner that consumes caller-supplied arrays and retains the
  complete boundary paths, boundary geometry, selected density states and
  bounded final histories without owning a random generator or a clock.
- Add synchronous overlapping and nonoverlapping operational aggregation
  estimators. The primary target uses all overlapping fixed-grid windows and
  reports pooled realised correlation, individual-path correlations, path
  means, path dispersion and normal standard-error bands separately.
- Execute an eight-path, 2,400-step coupled ensemble and a matched-input
  uncoupled control with sample-orthogonal external innovations. The declared
  microscopic correlation is zero; the measured pooled boundary-return
  correlation rises from `0.002176` at one step to `0.510121` at lag 600,
  while the matched control is `-0.029704` at lag 600.
- Generate the operational counterpart to the Bauer Epps target as Figure 10,
  on the uniform operational grid with no interpolation, event clock,
  subordination or calendar-time label.
- Apply one Gaussian order-density impulse to book 1 and generate applied and
  relaxed paired control views as Figures 11 and 12. The output calls this a
  density impulse, not a market order or observed trade; the signed own and
  cross boundary responses remain machine readable.
- Add 19 generated checks, 1,200 aggregate curve rows, 9,600 path-lag rows,
  501 shock-response rows, 804 selected-density rows and nine tests. Calendar
  clocks and explicit subordination remain reserved for `v1.5.0`.

## `v1.4.2` — 2026-08-13

The operational numerical and thickness-robustness gate was accepted after
its 165-entry manifest and complete 181-test route passed from a fresh
extraction.

- Estimate local reaction-front slope and curvature with a boundary-centred
  polynomial stencil, and define the diagnostic curvature length
  `2*abs(slope)/abs(curvature)` so the appendix displacement ratio is explicit.
- Extend rolling path results with front-curvature and curvature-length paths;
  unavailable near-edge stencils remain visible as missing diagnostics.
- Report the Angstmann--Gebbie ratios `Delta x/w_ref`,
  `w_ref/mu^(-1/2)`, source-width/curvature-length and active
  selector-width/curvature-length without silently replacing `<<` by an
  arbitrary pass threshold.
- Verify monotonically decreasing reaction-boundary price and slope errors
  under spatial refinement, and decreasing off-centre boundary error as the
  Dirichlet domain expands.
- Verify decreasing fractional-density error as the raw Sibuya history cutoff
  increases from 8 to 128 terms.
- Verify finite-grid convergence of the regularised coupling first moment; the
  selected finite domain is within one percent of its continuum moment.
- Move atomic rendering intermediates from the synchronised `figures/`
  directory into a dedicated same-filesystem staging area after the complete
  route exposed an intermittent reappearance of a deleted Figure 7 temporary
  PDF. Preserve the last complete target when rendering fails.
- Add 15 generated checks, 21 machine-readable convergence rows and 11 tests,
  including three atomic-publication tests. Clock construction, subordination,
  full operational ensembles and publication-target recovery remain excluded.

## `v1.4.1` — 2026-08-13

The rolling operational-path gate was accepted after its 157-entry manifest
and complete 170-test route passed from a fresh extraction.

- Advance both books on one common uniform operational-time grid using only
  externally supplied standard innovations and shock fields.
- Retain a rolling density history bounded by the declared raw-kernel cutoff;
  store complete density fields only at explicitly requested snapshot steps.
- Execute the accepted minimum-step, relative-change and persistence burn-in
  policy; record the first converged operational step and optionally stop there.
- Validate each supplied initial price against the zero crossing of its initial
  density rather than silently treating the source centre as the boundary.
- Adopt the Angstmann--Gebbie appendix construction as the target thickness
  authority: `epsilon=abs(z_ref)*w_ref` and
  `w_epsilon(z)=epsilon/abs(z)`. The Bauer finite-grid deformation remains only
  in the frozen legacy route.
- Record the reaction-front slope, candidate count, domain-edge distance,
  directed spread and state-dependent coupling-selector width along the path.
- Add eight generated path checks and 13 tests. This gate contains neither a
  random generator nor a calendar clock, subordinate path, trade-event layer,
  estimator or production ensemble.

## `v1.4.0` — 2026-08-13

The uniform operational-solver entry gate was accepted after its 151-entry
manifest and complete 157-test route passed from a fresh extraction. It
composes the accepted Stage 3 target components for one simultaneous two-book
step without constructing a complete path.

- Select Dirichlet-zero outer density boundaries for the finite lit-book
  domain; reject implicit endpoint repetition and unsupported boundary modes.
- Replace the defective legacy local index seed by a complete candidate scan
  for exact and off-grid simple zero crossings.
- Require a unique reaction boundary by default. When several crossings are
  explicitly admitted, select the uniquely nearest previous boundary and
  reject distance ties.
- Expose the selected boundary slope, candidate count and distance to the
  domain edge for later robustness and convergence checks.
- Assemble both corrected books from one immutable previous-price snapshot,
  externally supplied jump biases and shocks, raw memory kernels, and one
  common uniform `Delta u`.
- Apply the outer boundary correction explicitly and retain it in the term
  decomposition rather than hiding it inside the recurrence.
- Verify an independently solved uncancelled stationary state as a one-step
  fixed point under the diffusion scaling relation.
- Add eight generated solver-entry checks and 14 tests. Complete rolling
  paths, burn-in execution, grid/domain convergence and ensembles remain later
  `v1.4.x` subphases. No clocks or calendar-time observations are introduced.

## `v1.3.5` — 2026-08-13

The operational-innovation conformity gate was accepted after its 145-entry
manifest, eight generated checks, and complete 143-test route passed from a
fresh extraction. It resolves PA-07 and PA-08 without assembling the full
solver and closes Stage 3.

- Accept externally supplied standard two-book innovations as the target
  input boundary; no target module owns a random generator or seed.
- Apply each book scale `sigma_j` exactly once, correcting the legacy
  `sigma_j^2` behaviour away from the frozen `sigma_j=1` targets.
- Make independent, correlated, shared and antithetic operational forcing
  explicit through a declared correlation in `[-1, 1]`.
- Default correlation-emergence experiments to independent microscopic
  forcing. Nonzero forcing correlation is a controlled benchmark, not a
  hidden source of the coupling result.
- Map scaled velocities to the bounded DTRW bias
  `F_j=r*tanh(V_j*Delta x/(4*D_j))`, then construct nonnegative transport
  weights that sum to one.
- Do not identify the microscopic forcing correlation automatically with the
  effective reaction-boundary price correlation; that quantity must be
  measured from completed operational paths.
- Add eight generated innovation checks and ten tests. Clocks, subordination,
  boundary extraction and complete operational paths remain excluded.
- Close Stage 3 after acceptance of this gate. The earlier provisional
  `v1.3.6` observation and `v1.3.7` paired-path gates are removed because they
  require the Stage 4 solver and Stage 5 clocks.
- Clean the active workspace by retaining one accepted bundle, moving 25
  obsolete checkpoint archives to recoverable temporary quarantine, ignoring
  renderer staging files and consolidating the completed audit plan into its
  final audit record.

## `v1.3.4` — 2026-08-13

The corrected operational-primitive gate was accepted after its 142-entry
manifest, 10 generated checks, and complete 133-test route passed from a fresh
extraction. It implements the four corrections accepted after the v1.3.3
audit without assembling the full operational solver.

- Add a physically separate `functions/operational/` package; the frozen
  `legacy_*` modules are unchanged.
- Implement the target source
  `-lambda*mu*y*exp(-mu*y^2)` without legacy periodic wrapping.
- Implement the bounded regularised thick coupling
  `gamma*z*q(y)*W(y,z;epsilon)`, including exact zero-spread vanishing,
  reversal checks and lattice first-moment matching.
- Store raw Sibuya coefficients and apply cancellation survival once using
  the operational elapsed time `(lag-1)*Delta u`.
- Construct all book sources and ordered-pair fields from one immutable price
  snapshot before solving explicitly named Dirichlet or Neumann stationary
  reference systems.
- Add a declared minimum-step, relative-tolerance and persistence burn-in
  policy; execution of burn-in remains part of the Stage 4 solver.
- Add 10 generated primitive checks and 14 tests, bringing the complete suite
  to 133 tests.
- Leave innovation scale/correlation at the accepted `v1.3.5` tractability
  gate. Clocks, subordination, boundary extraction and the complete path
  driver are not part of this checkpoint.

## `v1.3.3` — 2026-08-13

The revised formal conformity, computational and mathematical audit gate was
accepted after its 133-entry manifest and complete 119-test route passed from
a fresh extraction. No scientific correction is applied in this checkpoint.

- Confirm Angstmann--Gebbie arXiv:2606.14182v1 as the mathematical conformity
  target: fixed spatial grid, uniform operational time, and explicit
  book-specific calendar-time subordination.
- Retain Bauer--Diana--Gebbie arXiv:2408.03181v2 and the frozen Julia commit as
  the authority for legacy behaviour and statistical figure recovery.
- Generate a 22-finding audit register, 45 numerical metrics, and 45
  path/frame shock-relaxation records.
- Find no confirmed Python translation defect on the frozen port surface and
  assign each readiness finding to its proper target gate.
- Accept the architecture order: uniform operational dynamics, independent
  clock construction, explicit subordination, then timestamp-aware calendar
  measurement. Nonuniform calendar intervals are never solver steps.
- Confirm but defer the source correction from `exp(-(mu*y)^2)` to
  `exp(-mu*y^2)` and require a physically separate target coupling.
- Record that the legacy coupling remains nonzero at zero book spread, with
  maximum absolute value about `0.6433` on the frozen shock grid; the target
  spread-proportional thick coupling must vanish there.
- Accept source, thick-coupling, single-survival-memory and simultaneous-
  initialization corrections for `v1.3.4`; defer innovation acceptance to an
  isolated tractability gate at `v1.3.5`.
- Classify the Figure 9 residual asymmetry as a small, largely relaxed
  post-shock transient rather than evidence of stationary global equilibrium.
- Add nine audit tests, bringing the complete suite to 119 tests.
- Publish all active figure routes atomically and clear only orphaned
  `.figure-*.tmp.*` renderer staging files so interrupted or synchronised
  renders cannot invalidate a later gate.

## `v1.3.2` — 2026-08-12

The selected legacy shock-view checkpoint was accepted after its 126-file
archive, 125-entry manifest, and complete 110-test route passed from a fresh
extraction.

- Reconstruct Julia publication frames 1 and 9 from stored density steps 390
  and 398 for path 0, book 0.
- Preserve the plotting offset: each density is shown with the arrival and
  impulse fields for the following target step.
- Preserve nominal-step scaling for arrivals, removals, and impulse while
  retaining realised nonuniform clock time and effective spatial increment in
  each label.
- Generate five-path data and ensemble summaries for both selected frames,
  without claiming historical Julia path or pixel identity.
- Generate separate target-sized Figure 8 and Figure 9 PDF/PNG pairs.
- Add ten shock-view and output tests, bringing the complete suite to 110 tests.

## `v1.3.1` — 2026-08-12

The legacy Epps-estimator and figure checkpoint was accepted after its
116-file archive, 115-entry manifest, and complete 100-test route passed from
a fresh extraction.

- Port the synchronous reduction of the Julia Dirichlet Fourier estimator,
  including its duplicated Nyquist mode for even return counts.
- Preserve the 28,200-unit previous-tick horizon, 14,397 consumed raw states,
  and lags 1 through 400 on the legacy simulation-index axis.
- Separate the true 10-path mean and standard deviation from the historical
  sparse-matrix plotting artefact that divides the curve by 14,397.
- Reproduce the code-defined t ribbon and the Julia FFTW frequency-scale
  convention used by the inset.
- Generate three machine-readable CSV files and the target-sized Figure 7
  pair, historically referred to in this project as the Bauer Figure 5 target.
- Publish each baseline figure atomically so an interrupted renderer cannot
  replace a previously complete PDF or PNG with a partial file.
- Add ten estimator and output tests, bringing the complete suite to 100 tests.

## `v1.3.0` — 2026-08-12

The deterministic legacy-target execution checkpoint was accepted after its
106-file archive, 105-entry manifest, and complete 90-test route passed from a
fresh extraction.

- Execute all 10 `B-EPP-01` paths and all 5 `B-SHOCK-01` paths from the
  accepted `PY-LEGACY-V1.2.5-01` input ensemble.
- Freeze complete raw price paths, their shared nonuniform state-time grids,
  and all nine shock-density frames for every declared shock path.
- Record the legacy Epps consumer boundary: its nominal step 14,401 round trip
  resolves to 14,397 raw states on a unit-spaced simulation-index axis.
- Validate every array and archive hash, complete-path status, shared clocks,
  price domain, distinct streams, shock-frame indices, and exact recovery of
  every stored reaction boundary.
- Add eight execution tests, bringing the complete suite to 90 tests. The
  Epps estimator and publication plots remain later `v1.3.x` subphases.

## `v1.2.5` — 2026-08-12

Stage 2 was completed when the declared target-input checkpoint was accepted
after its 100-file archive, 99-entry manifest, and complete 82-test route
passed from a fresh extraction.

- Freeze ensemble `PY-LEGACY-V1.2.5-01` as stored `float64` arrays for both
  Bauer targets, with archive and per-array SHA-256 hashes.
- Preserve one shared clock stream across the two books while assigning
  distinct innovation streams to every book and path.
- Record PCG64, inverse-exponential, and Box-Muller seeds as provenance only;
  the stored arrays are authoritative and no Julia RNG parity is claimed.
- Add validated loaders and exact observed/corrected path slicing for 26,001
  Epps and 16,022 shock intervals in the observed route.
- Add eight ensemble tests, bringing the complete suite to 82 tests. One full
  path from each target also completed as a non-gate smoke check.

## `v1.2.4` — 2026-08-12

The initializer, clock, and streaming-driver checkpoint was accepted after the
94-file archive and complete 74-test route passed both the fresh-extraction
gate and the independent Windows virtual-environment run.

- Separate the observed overwritten Julia initialization from a corrected
  stationary initializer.
- Reproduce the legacy exponential-clock trimming defect and final epsilon,
  while exposing a separately named corrected trimming mode.
- Record and reproduce the unused final clock interval in the observed Julia
  top-level loop.
- Add a rolling-history target driver and memory plans for `B-EPP-01` and
  `B-SHOCK-01`, with density storage limited to requested snapshots.
- Add frozen `FX-06A` control-flow records and ten tests, bringing the complete
  suite to 74 tests. Target RNG inputs and Julia numerical exports remain
  unavailable.

## `v1.2.3` — 2026-08-12

The deterministic short-path checkpoint was accepted after the 88-file
archive, complete 64-test route, and fresh-extraction gate passed.

- Port the Julia velocity-to-jump-probability map and beta-zero realised-draw
  conversion used by both frozen targets.
- Port the indexed one-book impulse with its nominal-step window and sign.
- Assemble uniform and legacy variable-step one- or two-book paths from
  explicit initial states, draws, and interval arrays.
- Preserve previous-step price coupling for both books and replace the public
  `-1` boundary sentinel by explicit path failure fields.
- Add the frozen `FX-06` short-path record and nine path tests, bringing the
  current suite to 64 tests. The fixture is not an authoritative Julia export.

## `v1.2.2` — 2026-08-12

The recurrence checkpoint was accepted after the 83-file archive, complete
55-test route, and fresh-extraction gate passed.

- Port the active Julia fixed-step fractional-history recurrence as an
  independently testable one-step Python operation.
- Port the legacy variable-step recurrence and `dr_g_way` spatial interpolation
  solely as a reproduction reference for Stage 3.
- Preserve the additional cancellation exponential applied by the Julia step
  routines even though the stored kernel is already cancellation weighted.
- Add the manually evaluated, term-level `FX-05` fixture and eight recurrence
  tests, bringing the current suite to 55 tests. Authoritative Julia exports
  remain deferred.

## `v1.2.1` — 2026-08-12

Deterministic-primitives checkpoint accepted after the 79-file archive and
complete 47-test route passed.

- Port the legacy periodic source with exponent `-(mu*y)^2`.
- Port the finite-grid, side-selective pair coupling and its spread scale.
- Port the raw and cancellation-weighted Sibuya coefficient recurrences,
  including the Julia cutoff convention.
- Port the local zero-crossing search and linear reaction-boundary
  interpolation, replacing the `-1` public sentinel by an explicit failure.
- Add formula-level fixtures `FX-01` through `FX-04` and 12 primitive tests,
  bringing the current suite to 47 tests. Authoritative Julia exports remain
  deferred.

## `v1.2.0` — 2026-08-12

Stage 2 entry checkpoint accepted after the 72-file archive and complete
35-test route passed.

- Add a typed Python configuration and state boundary for the legacy two-book
  simulations.
- Freeze machine-readable configurations for `B-EPP-01` and `B-SHOCK-01`,
  including the hard-coded shared clock seed, absent master seed, legacy time
  indexing, and exact output contracts.
- Record that the calibrated legacy Epps script also enables a short impulse in
  book 1 at real time 50.
- Lock the faithful port to the Julia source exponent `-(mu*y)^2`; defer the
  corrected exponent `-mu*y^2` until after legacy port and reproduction tests.
- Add 10 configuration and state tests, bringing the current suite to 35 tests.

## `v1.1.4` — 2026-08-12

Stage 1 was accepted after independent Windows execution of the complete
reproduction route. The source-and-target freeze now opens Stage 2 at
`v1.2.0`.

- `v1.1.0`: freeze the repositories, paper sources, CPG v1.2 workflow, hashes,
  execution surface, and verification boundary.
- `v1.1.1`: map the legacy Julia implementation to its scientific operations
  and proposed Python objects.
- `v1.1.2`: freeze the legacy calibrated Epps plot and shock-response targets.
- `v1.1.3`: define deterministic cross-language fixtures, tolerances, and the
  gate into the Python conversion.
- `v1.1.4`: correct the cross-platform gate test so regenerated Matplotlib PDFs
  are checked structurally and scientifically rather than required to retain a
  platform-specific byte hash; accept the Stage 1 gate after 14 diagnostics,
  16 sensitivity checks, and 25 regression tests pass locally.

## `v1.0.0` — 2026-08-01

- First public analytical reproducibility bundle.

## Version progression to `v2.0.0`

The middle number denotes the major project stage. The patch number denotes an
accepted subphase or revision within that stage.

| Version family | Major project stage |
|---|---|
| `v1.1.x` | Source, target, and verification freeze |
| `v1.2.x` | Faithful Julia-to-Python conversion |
| `v1.3.x` | Legacy statistical reproduction and port-correctness audit |
| `v1.4.x` | Uniform-grid operational-time numerical scheme |
| `v1.5.x` | Explicit calendar-time subordination |
| `v1.6.x` | Separate two-clock and boundary-response experiments |
| `v1.7.x` | Core publication-figure reconstruction and analytical/simulation comparison |
| `v1.8.x` | Event semantics, own/cross-impact, meta-orders and dependence diagnostics |
| `v1.9.x` | Integration and release preparation |
| `v2.0.0` | Final released simulation extension |

A stage begins at `v1.N.0`. Material subphases or accepted corrections advance
to `v1.N.1`, `v1.N.2`, and so on. `v2.0.0` is reserved for the final public
release and is not used for intermediate work.

Stage 3 does not close immediately after visual recovery. Its sequence is
`v1.3.1` for statistical Epps recovery, `v1.3.2` for selected shock-view
recovery, `v1.3.3` for the formal conformity, numerical, and mathematical
audit, `v1.3.4` for the four target dynamics primitives, and `v1.3.5` for
innovation tractability and Stage 3 closure. Stage 4 then begins at `v1.4.0`.
Timestamp-aware observation requires the Stage 5 clocks, while paired clock
and boundary-response experiments belong to Stages 6 and 7.

Stage 4 is divided by numerical responsibility: `v1.4.0` establishes the
boundary and one-step contract; `v1.4.1` assembles a rolling path and executes
the burn-in policy; `v1.4.2` establishes grid, domain, history-cutoff and
boundary robustness; and `v1.4.3` executes the complete operational ensembles,
recovers the operational Figure/shock targets and closes Stage 4.

Stage 5 is divided by observation responsibility: `v1.5.0` establishes the
clock-path, inverse-clock and discrete subordination contracts; `v1.5.1` adds
stochastic two-book clock ensembles with fully recorded realised paths; and
`v1.5.2` adds timestamp-aware calendar estimators, completes the subordinated
Figure 5 comparison and closes Stage 5. The paired separation of clock and
boundary-response mechanisms remains Stage 6.

Stage 7 begins with the three core publication-figure deliverables after
the operational path, clocks and paired mechanism experiments are accepted:
`v1.7.0` for the corrected uniform-operational and explicitly subordinated
replacement target for legacy Figure 7; `v1.7.1` for the path-derived
simulation analogue of analytical Figure 6; and `v1.7.2` for their registered
analytical/simulation discrepancy diagnostic. The immutable legacy Figure 7
remains separately retained. Theory conformity then proceeds through
`v1.7.3` design, `v1.7.4` clock-only recovery and `v1.7.5` coupling-only
diagnosis. Because the accepted coupling does not provide the required local
positive response rate, the adopted revised continuation is `v1.7.6`
correction design, `v1.7.7` corrected coupling recovery, `v1.7.8` combined
no-refit prediction and `v1.7.9` Stage 7 closure.

The impact/event extension moves to Stage 8: `v1.8.0` establishes explicit
limit/market event semantics; `v1.8.1` measures single-event own/cross-impact;
`v1.8.2` adds meta-order impact and relaxation; and `v1.8.3` adds operational-
and calendar-time mid-price-increment and three-convention trade-sign
dependence diagnostics. These extensions must not relabel a density impulse as
an observed trade. Stage 9 integrates the accepted results and prepares the
numeric `v2.0.0` release.
