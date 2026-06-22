# Documentation Standards

*Last updated: 2026-06-19. Establishes required docstring styles, TOC requirements, and inline comment conventions for each stack component. These standards are enforced by pre-commit hooks and CI (see `moon/roadmaps/documentation.md §6.13`). Violations in new code are blocking; violations in existing code are tracked in §6.1–§6.5.*

---

## Table of Contents

- [General Principles](#general-principles)
- [Python (Google-style docstrings)](#python-google-style-docstrings)
- [Rust (rustdoc `///` comments)](#rust-rustdoc--comments)
- [TypeScript (TSDoc)](#typescript-tsdoc)
- [Kotlin (KDoc)](#kotlin-kdoc)
- [Swift (DocC)](#swift-docc)
- [Markdown Files](#markdown-files)
- [Inline Comments](#inline-comments)
- [Enforcement](#enforcement)

---

## General Principles

1. **Document the why, not the what.** Well-named identifiers already communicate what code does. Comments and docstrings add value only when they explain a non-obvious constraint, a subtle invariant, or a domain concept that cannot be inferred from the identifier alone.
2. **One source of truth.** If a fact appears in both a docstring and a comment, one of them will go stale. Keep the fact in the docstring and delete the comment.
3. **Executable documentation wins.** A doc-test (`# Examples` in Rust, `doctest` in Python) is simultaneously documentation and a regression test. Prefer it over prose examples whenever the function is pure or near-pure.
4. **Incremental coverage.** Do not block a PR for missing docstrings in code it does not touch. Focus enforcement on new or substantially modified public APIs.

---

## Python (Google-style docstrings)

All public functions, methods, and classes in `backend/src/` must have Google-style docstrings. Private helpers (`_name`) are exempt but encouraged for complex logic.

### Required sections

| Section | Required when |
|---------|--------------|
| `Args:` | Function has ≥ 1 parameter (excluding `self`) |
| `Returns:` | Function returns a non-`None` value |
| `Raises:` | Function explicitly raises an exception |
| `Example:` | Function is part of a public API consumed by tests |

### Format

```python
def compute_aligned_ssim(img_a: np.ndarray, img_b: np.ndarray, *, sigma: float = 1.5) -> float:
    """Compute SSIM after ECC alignment to correct for sub-pixel shift.

    Aligns `img_b` to `img_a` using an Euclidean ECC warp before computing
    SSIM, removing alignment-induced metric bias on near-identical frames.

    Args:
        img_a: Reference image, shape (H, W) or (H, W, C), uint8.
        img_b: Target image, same shape as img_a.
        sigma: Gaussian smoothing radius for the SSIM kernel.

    Returns:
        SSIM score ∈ [-1, 1]; 1.0 = identical.

    Raises:
        ValueError: If img_a and img_b have different shapes.

    Example:
        >>> import numpy as np
        >>> a = np.zeros((64, 64), dtype=np.uint8)
        >>> compute_aligned_ssim(a, a)
        1.0
    """
```

### Rules

- Max docstring line length: **88 characters** (matches `ruff` / `black` line length).
- First line is a short imperative summary ending with a period.
- Blank line between summary and body; blank line before each section header.
- Type annotations go in the function signature, not in the docstring (`Args:` lists names and descriptions only — omit types that are already in the signature).
- `Example:` blocks must be valid Python that can be run by `pytest --doctest-modules`.

### Enforcement

```bash
# Check style
pydoclint --style=google --arg-type-hints-in-signature=true backend/src/

# Run doctests
pytest --doctest-modules backend/src/animation/
```

---

## Rust (rustdoc `///` comments)

All public items (`pub fn`, `pub struct`, `pub enum`, `pub trait`, `pub const`) in `base/src/` must have `///` doc comments. Crate-level and module-level documentation uses `//!` at the top of `lib.rs` and each `mod.rs`.

### Required sections

| Section | Required when |
|---------|--------------|
| Summary line | Always |
| `# Arguments` | Function has ≥ 2 non-trivial parameters |
| `# Panics` | Function calls `panic!`, `unwrap()`, `expect()`, or `assert!()` |
| `# Examples` | Public function in `base/src/math/` or any PyO3-exported function |

### Format

```rust
/// Euclidean (L2) distance between two equal-length vectors.
///
/// # Panics
///
/// Panics if `a` and `b` have different lengths.
///
/// # Examples
///
/// ```
/// use base::math::distance::euclidean;
/// assert!((euclidean(&[0.0, 0.0], &[3.0, 4.0]) - 5.0).abs() < 1e-10);
/// ```
pub fn euclidean(a: &[f64], b: &[f64]) -> f64 {
    squared_euclidean(a, b).sqrt()
}
```

### Rules

- `# Examples` blocks must compile and pass via `cargo test --doc`.
- Avoid redundant comments like `/// Sets the value of x` on `pub fn set_x()`.
- `#[inline]` functions with trivially obvious behaviour (forwarding, casting) are exempt from `# Examples` but must have at least a summary line.
- PyO3-exported functions (`#[pyfunction]`) must additionally document what Python type each argument maps to in the summary or a `# Python` section.

### Enforcement

```bash
cargo test --doc
cargo doc --no-deps --document-private-items 2>&1 | grep "^warning"
```

---

## TypeScript (TSDoc)

All exported functions, interfaces, classes, and type aliases in `frontend/src/math/` and `frontend/src/api.ts` must have TSDoc comments.

### Format

```typescript
/**
 * Computes the Euclidean distance between two equal-length vectors.
 *
 * @param a - First vector.
 * @param b - Second vector, must have the same length as `a`.
 * @returns Euclidean distance ≥ 0.
 *
 * @example
 * ```ts
 * euclidean([0, 0], [3, 4]); // 5
 * ```
 */
export function euclidean(a: number[], b: number[]): number {
    return Math.sqrt(a.reduce((acc, ai, i) => acc + (ai - b[i]) ** 2, 0));
}
```

### Rules

- `@param` and `@returns` are required for all exported functions with ≥ 1 parameter or a non-`void` return.
- `@example` is required for all functions in `frontend/src/math/`.
- React component prop documentation goes in the Props interface, not on the component itself.
- `@internal` marks items intentionally excluded from the generated TypeDoc output.

### Enforcement

```bash
# Type-check (also catches missing @param types)
npx tsc --noEmit

# Generate docs and treat undocumented exports as warnings
npx typedoc --treatWarningsAsErrors --entryPointStrategy expand frontend/src/math
```

---

## Kotlin (KDoc)

All public classes, interfaces, and functions in `app/src/main/java/` must have KDoc comments.

### Format

```kotlin
/**
 * Loads the user's image library from the remote backend.
 *
 * Executes the network request on the IO dispatcher. The returned flow
 * emits [Resource.Loading] immediately, then [Resource.Success] or
 * [Resource.Error] on completion.
 *
 * @param accountId The authenticated account identifier.
 * @param page Zero-based page index for pagination.
 * @return A cold [Flow] of [Resource<List<ImageItem>>].
 */
suspend fun loadLibrary(accountId: String, page: Int): Flow<Resource<List<ImageItem>>>
```

### Rules

- `@param` for every parameter; `@return` for non-`Unit` returns.
- `@throws` when the function propagates a checked exception through the coroutine dispatcher.
- Data class properties: one-line KDoc (`/** The unique database ID for this image. */`) on each `val`/`var`.
- `internal` and `private` items are exempt but encouraged for complex state machines.

### Enforcement

```bash
./gradlew dokkaHtml
# Check output in app/build/dokka/html/
```

---

## Swift (DocC)

All public types, functions, and stored properties in the iOS target must have DocC `///` comments.

### Format

```swift
/// Fetches the paginated image library for the authenticated account.
///
/// Executes asynchronously on the network actor. Throws `NetworkError.unauthorized`
/// if the session token has expired.
///
/// - Parameters:
///   - accountId: The authenticated account identifier.
///   - page: Zero-based page index.
/// - Returns: An array of ``ImageItem`` models for the requested page.
/// - Throws: ``NetworkError`` on HTTP or decoding failure.
public func loadLibrary(accountId: String, page: Int) async throws -> [ImageItem]
```

### Rules

- `- Parameters:`, `- Returns:`, and `- Throws:` are required for all public functions with parameters, return values, or throws.
- Type cross-references use double-backtick notation: `\`\`ImageItem\`\``.
- Extension members on standard library types must have a `/// - Note:` explaining why the extension is necessary.

### Enforcement

```bash
xcodebuild docbuild -scheme ImageToolkit -destination 'platform=iOS Simulator,name=iPhone 15'
```

---

## Markdown Files

### TOC requirement

Any Markdown file exceeding **100 lines** must have a Table of Contents immediately after the title and "last updated" paragraph. Format:

```markdown
## Table of Contents

- [Section Name](#section-name)
  - [Subsection](#subsection)
```

GitHub anchor derivation rules: lowercase, spaces → `-`, special characters stripped.

### Roadmap files (`moon/roadmaps/`)

- Must end with an **Effort × Impact Matrix** and an **Anchor Index**.
- Section headers follow the numbering convention of the file (§5.x for architecture, §3.x for performance, etc.).
- Status tags: `✅ Shipped`, `⬜ Not started`, `🔄 In progress`.
- Option tags: **[Quick Win]** (< 1 day), **[Research]** (prototype required), **[Long-term]** (external dependency).

### General rules

- Maximum line length: **120 characters** for prose lines; no limit for code blocks.
- Code blocks must specify a language: ` ```python `, ` ```rust `, ` ```bash `, etc. Never use bare ` ``` `.
- Internal links use relative paths. Absolute URLs are allowed only for external resources.
- Link text must be descriptive — no bare URLs in prose.

### Enforcement

```bash
# Link checker
lychee --verbose --no-progress '**/*.md'

# Markdown lint (optional, not blocking)
markdownlint-cli2 '**/*.md'
```

---

## Inline Comments

### When to write a comment

Write an inline comment **only** when the code cannot express the why:

| Scenario | Example comment |
|----------|----------------|
| Hidden constraint or invariant | `# QPixmap must never be created off the main thread (Qt threading rule)` |
| Workaround for a specific bug | `# GTK portal dialog crashes with JPype JVM — see MEMORY.md Known Bugs` |
| Non-obvious algorithm choice | `# Using Cauchy loss (f_scale=10) instead of L2 to suppress outlier edges` |
| Magic number with domain meaning | `# 0.025 = empirically validated MAD threshold for animation hold detection` |

### When NOT to write a comment

- Restating what a well-named identifier already says.
- Describing what a block of code does (use a named function instead).
- Referencing the current task, PR, or ticket ("added for issue #123").
- Leaving "TODO" comments without a trackable item. Use a GitHub issue instead.

### Rust-specific

- `SAFETY:` comment is **required** above every `unsafe` block, explaining the invariant that makes it sound.
- `// PERF:` marks a performance-sensitive path that should not be refactored without benchmarking.

---

## Enforcement

### Pre-commit hooks

All hooks run locally via `pre-commit`. Install once with:

```bash
pip install pre-commit
pre-commit install
```

See `.pre-commit-config.yaml` for the full hook list. Key hooks:

| Hook | What it checks |
|------|---------------|
| `pydoclint` | Google-style docstring completeness for Python |
| `ruff` | Python linting + auto-fix |
| `mypy` | Python type annotations (strict modules) |
| `cargo test --doc` | Rust doc-tests (run via `make doc-test`) |
| `typedoc` | TypeScript TSDoc completeness |
| `lychee` | Broken links in Markdown files |

### CI gates (blocking)

See `.github/workflows/docs.yml` and `.github/workflows/ci.yml`. The following are blocking on every PR:

- `mkdocs build --strict` — broken links or missing doc pages fail the build.
- `cargo test --doc` — any failing Rust doc-test fails the build.
- `pydoclint` — undocumented public functions in `backend/src/animation/` fail the build.
- `lychee` — broken internal Markdown links fail the build.

### CI gates (advisory)

- `typedoc --treatWarningsAsErrors` — reported as a warning until `frontend/src/math/` coverage reaches 100%.
- `./gradlew dokkaHtml` — runs on schedule, not on every PR.
