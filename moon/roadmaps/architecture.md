# Architecture & Infrastructure Roadmap — Quality, Reliability, and Maintainability

*Last updated: 2026-06-04. ASP unit tests now at 90 (90 passing). ASP benchmark: 52/96 true composites (54.2%), alignment gate added for 2D motion. See `asp.md` for per-session tracking.*

---

## How to Use This Document

Each section describes an architectural debt or infrastructure gap, all viable implementation options with trade-offs, and a recommendation. Items tagged **[Quick Win]** take under a day. Items tagged **[Research]** require prototyping.

---

## 5.1 ASP Pipeline Unit Test Coverage

**Pain point:** `backend/test/anim/` tests end-to-end ASP runs but has limited unit tests for individual pipeline stages. Regressions in `bundle_adjust.py` or `compositing.py` are hard to catch without running the full benchmark.

### Options

**A — Unit tests for each stage in isolation**
Synthetic test cases: known translation pairs for bundle adjustment, known frame strips for composite, known match sets for outlier rejection. Each test runs in <1s.
- Coverage targets:
  - `bundle_adjust.py`: test with known inlier/outlier edge sets; verify residuals and rejected edges.
  - `compositing.py`: test seam DP with a hand-crafted cost array; verify path is minimum.
  - `matching.py`: test each matcher tier with synthetic frame pairs; verify inlier count thresholds.
  - `stage_11.py`: test feather blend with known gains; verify output pixel values.
- Pros: Fast. Catches regressions without running the full pipeline.
- Cons: Synthetic inputs may not cover real-world edge cases.

**B — Property-based testing with Hypothesis**
Generate random translation sequences with known properties (monotonic, bounded step ratio) and verify the pipeline produces valid output affines.
- Example property: "For any sequence of translations where each step is > 50px, the pipeline produces a valid panorama with no canvas overlaps."
- Reference: [Hypothesis + pytest guide](https://pytest-with-eric.com/pytest-advanced/hypothesis-testing-python/)
- Pros: Catches edge cases that hand-crafted tests miss. Especially useful for the outlier rejection heuristics.
- Cons: Hypothesis needs domain-specific strategies for image generation. Longer test runs.

**C — Benchmark diff testing (golden gate)**
Run the 22-test benchmark on every PR and fail if any metric regresses beyond a threshold:
- Sharpness regression > 5% → fail
- Ghosting increase > 10% → fail
- Success rate decrease → fail
- Runtime increase > 20% → warning
- Reference: [pytest-benchmark](https://github.com/ionelmc/pytest-benchmark); [benchmarking with CI](https://towardsdatascience.com/benchmarking-pytest-with-cicd-using-github-action-17af32b4a30b/)
- Pros: Catches integration-level quality regressions. Ground truth is the 22-test corpus.
- Cons: Slow (~20 min). Best run only on main branch merges, not every commit.

**D — Mutation testing**
Use `mutmut` or `cosmic-ray` to inject mutations into `bundle_adjust.py` and `compositing.py`. Verify that existing tests catch the mutations.
- Pros: Measures test quality, not just coverage.
- Cons: Very slow. High false-positive rate for numerical code.

**E — Snapshot testing for intermediate outputs**
Store the intermediate outputs of each stage (affine matrices, seam masks, gain-corrected frames) for the 22-test corpus as golden snapshots. Assert that new runs match within tolerance.
- Pros: Catches subtle numerical regressions in intermediate stages.
- Cons: Snapshots must be updated whenever a valid algorithm change is made. Large storage overhead for image snapshots.

**Recommendation:** A + C. Unit tests catch regressions early; the benchmark gate prevents quality regressions from reaching main.

---

## 5.2 Benchmark Regression CI

**Pain point:** The benchmark suite in `backend/benchmark/` exists with baseline comparison but is not wired into GitHub Actions for automatic regression detection.

### Options

**A — GitHub Actions workflow on push to main**
Run `python run_all.py --baseline results/baseline/` on every push to main. Fail the build if `time > baseline × 1.2` or `memory > baseline × 1.15`.
- Workflow structure:
  ```yaml
  name: benchmark-regression
  on: push:
    branches: [main]
  jobs:
    benchmark:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - run: python backend/benchmark/run_all.py --baseline baseline/
        - uses: actions/upload-artifact@v4
          with:
            path: benchmark/results/
  ```
- Pros: Automatic regression detection. Results stored as CI artifacts for trend analysis.
- Cons: Python benchmarks may be fast enough; ASP + Rust benchmarks are not (20 min+). Must split into fast/slow suites.

**B — Weekly scheduled run with email/Slack notification**
For expensive benchmarks (Rust criterion, full ASP), run weekly. Report a summary diff vs the previous week.
- Pros: Amortises the cost of expensive benchmarks. Avoids blocking every PR on a 20-minute run.
- Cons: Weekly cadence may miss regressions introduced mid-week.

**C — Pre-commit hook for lightweight checks**
A subset of fast benchmarks (phash speed, DB query latency, fast image load) runs locally on commit via pre-commit. Full suite is opt-in via `make benchmark`.
- Reference: [pre-commit framework](https://pre-commit.com/)
- Pros: Catches performance regressions before they reach CI. Zero CI cost for fast checks.
- Cons: Developers must install pre-commit hooks. Local machine performance varies, making thresholds unreliable.

**D — Performance tracking dashboard (Bencher / codspeed)**
Use a service like [Bencher](https://bencher.dev/) or [CodSpeed](https://codspeed.io/) to track benchmark trends over time. Visualise performance history as a graph.
- Pros: Long-term trend visibility. PR-level performance comparison.
- Cons: External service dependency. Data leaves the repository.

**Recommendation:** A for Python benchmarks (fast enough). B for full ASP + Rust benchmarks. C as a low-friction local guard.

---

## 5.3 Plugin System for Matchers and Compositors

**Pain point:** Matching and compositing stages have grown a large number of fallback tiers (TM, PC, ALIKED+LightGlue, RoMa, segment-guided). Adding new matchers requires editing `matching.py` directly.

### Options

**A — Matcher registry with priority list**
A `dict` mapping matcher name → callable. Pipeline tries matchers in priority order until one returns sufficient inliers. Adding a new matcher = registering it in the dict.
```python
MATCHER_REGISTRY: dict[str, MatcherCallable] = {
    "loftr": loftr_match,
    "lightglue": lightglue_match,
    "roma": roma_match,
    ...
}
```
- Pros: Simple. Minimal refactor. Adding a new matcher doesn't touch pipeline logic.
- Cons: No enforced interface. Each matcher callable may have a different return signature.

**B — Abstract `Matcher` base class with formal interface**
```python
class Matcher(ABC):
    @abstractmethod
    def match(self, frame_a: np.ndarray, frame_b: np.ndarray) -> list[MatchPair]: ...
    @abstractmethod
    def is_available(self) -> bool: ...  # checks GPU/model availability
```
- Pros: Formal interface prevents the current situation where each matcher has subtly different return types. `is_available()` enables runtime capability detection.
- Cons: Requires refactoring all existing matchers to subclass `Matcher`.

**C — Protocol-based duck typing (typing.Protocol)**
Define a `MatcherProtocol` using `typing.Protocol` instead of ABC. Matchers don't need to inherit from anything — they just need the right methods.
- Pros: Lighter-weight than ABC. Works with existing matchers without refactoring.
- Cons: No runtime enforcement of the interface. Type checker enforces it statically.

**D — External plugin discovery via entry_points**
Allow third-party packages to register matchers via setuptools `entry_points`:
```toml
[tool.poetry.plugins."image_toolkit.matchers"]
my_matcher = "my_package:MyMatcher"
```
- Pros: Third-party extensibility. Standard Python plugin pattern.
- Cons: Overkill for the current single-package codebase. Discovery adds startup overhead.

**E — Compositor registry (same pattern as matcher)**
Apply the same registry/interface pattern to compositing strategies (hard-partition, soft-feather, Poisson, ToonCrafter). The pipeline selects a compositor by name.
- Pros: Decouples compositing algorithm selection from pipeline logic. Enables A/B testing of compositors.
- Cons: Requires abstracting the current compositing code significantly.

**Recommendation:** B establishes the correct foundation. C is a pragmatic step if B's refactor scope is too large. E is a natural follow-on once B is in place for matchers.

---

## 5.4 Logging and Diagnostics

**Pain point:** Pipeline logs to stdout with `print()` statements. Diagnosing failures requires replaying the entire run. No structured log format for automated analysis.

### Options

**A — Python `logging` module with file handler [Quick Win]**
Replace all `print()` calls with `logging.getLogger(__name__).info/debug/warning`. Add a `RotatingFileHandler` saving per-run logs to `~/.config/image-toolkit/logs/run_{timestamp}.log`. Log level controlled by config.
- Pros: Standard Python practice. `getLogger(__name__)` gives per-module log namespacing. Rotating handler prevents unbounded disk use.
- Cons: Requires touching every file that currently uses `print()`. Must audit for sensitive data in log messages.

**B — Pipeline execution trace JSON**
At the end of each ASP run, dump a structured JSON summary to the output directory:
```json
{
  "run_id": "...",
  "timestamp": "...",
  "stages": [
    {"name": "bundle_adjust", "duration_s": 0.15, "outliers_rejected": 2},
    {"name": "composite", "duration_s": 24.5, "seam_cost": 0.003}
  ],
  "metrics": {"sharpness": 33.14, "ghosting": 22.17},
  "config": {...}
}
```
Already partially done by the benchmark runner — standardise and always enable.
- Pros: Machine-readable. Enables trend analysis and RLHF integration.
- Cons: Must define a stable schema. Schema versioning needed as new stages are added.

**C — GUI log panel**
A collapsible log panel in the main window showing the last N log lines in real-time during operations. Filterable by level (DEBUG/INFO/WARNING/ERROR).
- Implementation: A `QPlainTextEdit` in read-only mode with `appendPlainText`. Connect to the logging handler via a `QSignalHandler`.
- Pros: Replaces the cluttered console output with a polished in-app log.
- Cons: GUI thread must not block on log writes. Log handler must be thread-safe.

**D — Structured logging with structlog**
Use `structlog` for context-bound structured logging (key-value pairs rather than formatted strings). Each log event carries its pipeline stage, frame index, and metric values as structured data.
- Pros: Better for automated log parsing and aggregation.
- Cons: `structlog` dependency. Larger refactor than option A.

**E — Sentry integration for error tracking**
Send exception tracebacks and error-level log events to Sentry. Aggregates errors across sessions.
- Pros: Production-grade error tracking. Crash reports include context.
- Cons: External service. Privacy concern — images/paths may appear in tracebacks. Must redact sensitive data.

**Recommendation:** A + B immediately. C as a quality-of-life follow-on. D if log analysis at scale is needed. Skip E unless the app becomes multi-user.

---

## 5.5 Vault Manager Modernisation

**Pain point:** `vault_manager.py` starts a JVM via JPype before Qt initialises. This is the root cause of the known `libstdc++` RTTI conflicts with GTK native dialogs and QtWebEngine. The JVM startup adds ~1–2s to app launch.

### Options

**A — Rewrite in Python using the `cryptography` library**
Implement AES-256-GCM in Python using `cryptography.hazmat.primitives.ciphers.aead.AESGCM`. Eliminate the JVM dependency entirely.
- `cryptography` is a Python package with a Rust backend — no JVM needed.
- Requires verifying `.vault` format compatibility with the Kotlin implementation (same IV, AAD, tag structure).
- Pros: Fastest path if `.vault` format is documented. Zero JVM overhead. Eliminates all `libstdc++` conflicts.
- Cons: Python-side secret material handling requires care (avoid logging, secure memory zeroing).

**B — Subprocess-based vault operations**
Keep the Kotlin implementation but call it via `subprocess` rather than JPype. Avoids JVM-in-process RTTI conflicts; small per-call overhead (~100ms) is acceptable for infrequent credential operations.
- Pros: Minimal code change. No re-implementation of crypto logic.
- Cons: Subprocess startup adds 100ms per vault operation. Credential bytes must be passed via stdin/stdout (not argv, which would expose them to `ps`).

**C — Rust AES-256-GCM via PyO3 [Recommended]**
Implement AES-256-GCM in Rust using the `aes-gcm` crate. Compile into the existing `base` extension module.
- `aes-gcm` is a well-audited crate (RustCrypto organisation). Supports 128-bit authentication tags.
- Pros: Zero-overhead FFI into the existing Rust extension. No JVM. Same security guarantees as the Kotlin implementation. Memory safety from Rust.
- Cons: Requires verifying `.vault` format compatibility. Adds `aes-gcm` crate to `base/Cargo.toml`.

**D — Age encryption (modern replacement)**
Replace the custom `.vault` format with `age` (a modern encryption standard). Use `pyrage` (Python bindings for age).
- Pros: Modern, well-audited encryption standard. Built-in key management. No JVM.
- Cons: Breaking change to `.vault` format. All existing vaults must be migrated.

**E — OS keyring integration**
Use the OS keyring (Freedesktop Secret Service on Linux via `keyring` Python library) to store credentials instead of encrypted vault files.
- Pros: Credentials managed by the OS. No custom vault format to maintain.
- Cons: Requires `keyring` dependency. OS keyring may not be available in all environments (headless servers). Reduces portability.

**Recommendation:** C is the architecturally cleanest solution — consolidates security-critical code into the already-existing Rust extension. A is the fastest path if the `.vault` format is documented. E as a long-term direction for desktop environments with reliable OS keyring support.

---

## 5.6 Mobile App Feature Parity Backlog

**Pain point:** Android app (`app/`) exists but its relationship to the desktop app's feature set is undocumented. No clear scope definition.

### Options

**A — Remote wallpaper control**
Set the desktop wallpaper from the phone via the REST API layer (§4.10B). Mobile app sends `POST /api/wallpaper/set` with an image ID from the database.
- Pros: Simple, useful, clearly scoped.
- Cons: Requires the REST API and LAN connectivity.

**B — Gallery browsing via web frontend**
Expose the desktop database as a read-only gallery browsable from any device on LAN via the React frontend served by Django.
- Pros: No native mobile code needed; works on any browser.
- Cons: Requires running the web frontend server.

**C — Push notifications for long operations**
When a long-running desktop operation completes (e.g., ASP batch job), send a push notification to the mobile app via Firebase Cloud Messaging (FCM).
- Pros: Good UX for overnight batch runs.
- Cons: FCM dependency. Google account required.

**D — Offline image viewer (local sync)**
Sync a subset of the desktop image library to the phone for offline viewing. Uses the existing Dropbox/GDrive sync infrastructure as transport.
- Pros: Useful for reviewing content on the go.
- Cons: Storage and bandwidth considerations. Sync conflict resolution.

**E — Remote stitch trigger**
Initiate an ASP pipeline run from the phone by selecting a frame group via the REST API. Status updates via WebSocket or polling.
- Pros: Enables remote processing of desktop's compute resources.
- Cons: High scope. Requires A + §4.10C + §2.7.

**Recommendation:** Define the mobile app's explicit scope before adding features. A + B are the most clearly scoped items. C for power users who run overnight batches.

---

## 5.7 Dependency Audit and Pinning

**Pain point:** `requirements.txt` / `pyproject.toml` may have unpinned transitive dependencies. Version drift between environments causes subtle failures.

### Options

**A — `uv lock` for reproducible installs [Quick Win]**
Use `uv lock` to generate a deterministic lockfile. Add `uv sync --frozen` to CI to ensure exact dependency versions.
- Pros: Zero new tooling — `uv` is already the package manager. Fully reproducible builds.
- Cons: Lockfile must be committed and kept updated.

**B — Dependabot or Renovate for automated dependency updates**
Configure Dependabot (GitHub-native) or Renovate (more configurable) to open PRs when dependencies have new versions.
- Pros: Proactive security patch application. Never miss a CVE fix.
- Cons: Renovate/Dependabot PRs require human review. Noisy for projects with many dependencies.

**C — `pip-audit` for CVE scanning in CI**
Run `pip-audit` (or `safety check`) on every CI run to detect known-vulnerable dependency versions.
- Pros: Catches security vulnerabilities automatically.
- Cons: False positives for dev-only or test dependencies. `pip-audit` requires internet access in CI.

**D — Cargo `cargo audit` for Rust dependencies**
Run `cargo audit` in CI to detect CVEs in Rust crate dependencies.
- Pros: Extends security scanning to the Rust extension.
- Cons: Requires `cargo-audit` in the CI environment.

**Recommendation:** A immediately (already using `uv`). C + D for security scanning. B for dependency freshness.

---

## Anchor Index

| Section | Anchor |
|---------|--------|
| 5.1 Unit Test Coverage | [#51-asp-pipeline-unit-test-coverage](#51-asp-pipeline-unit-test-coverage) |
| 5.2 Benchmark Regression CI | [#52-benchmark-regression-ci](#52-benchmark-regression-ci) |
| 5.3 Plugin System | [#53-plugin-system-for-matchers-and-compositors](#53-plugin-system-for-matchers-and-compositors) |
| 5.4 Logging and Diagnostics | [#54-logging-and-diagnostics](#54-logging-and-diagnostics) |
| 5.5 Vault Manager Modernisation | [#55-vault-manager-modernisation](#55-vault-manager-modernisation) |
| 5.6 Mobile App Backlog | [#56-mobile-app-feature-parity-backlog](#56-mobile-app-feature-parity-backlog) |
| 5.7 Dependency Audit | [#57-dependency-audit-and-pinning](#57-dependency-audit-and-pinning) |
