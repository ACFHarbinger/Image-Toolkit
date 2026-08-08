# Anime Stitch Pipeline: Owner Status, Review, and Roadmap Decision Report

**Date opened:** 2026-08-08  
**Owner/editor:** ACFHarbinger  
**Repository under review:** `submodules/ASP` (`Anime-Stitch-Pipeline`)  
**Document authority:** Owner-authored synthesis and decision record  
**Status:** Structure ready for owner fill — multi-agent template contributions complete enough to begin the visual rating pass (2026-08-08 final-pass consensus target)  
**Purpose:** Reconcile independent ASP reports, record the owner's visual benchmark assessment, establish product and engineering decisions, and provide binding input to the final roadmap set.

**Provenance note (paths):** All four agent status reports live under `.agent/reports/{claude,chat,gemini,grok}/`. All four proposed roadmaps live under `.agent/cache/{claude,chat,gemini,grok}/` (Image-Toolkit root). Ignore older path variants that pointed into `submodules/ASP/.agent/cache/...` unless a file is also mirrored there.

---

## How to Use This Report

This is not another agent proposal. It is the owner's authoritative synthesis of:

- direct experience using ASP;
- visual inspection of panoramic benchmark outputs;
- independent reports from Claude, Codex/ChatGPT, Gemini, and Grok;
- proposed roadmaps from those agents;
- product decisions made during the 2026-08-08 question-and-answer sessions;
- unresolved disagreements that must be settled before the final roadmaps are written.

The owner should replace every `[OWNER TODO]` marker that affects a decision. Agents may add evidence, alternatives, cross-references, and suggested wording, but must not silently convert a proposal into an owner decision.

Use these labels consistently:

- **DECIDED** — owner has selected the policy or outcome.
- **PROVISIONAL** — current direction, subject to evidence or prototype results.
- **OPEN** — a decision is still required.
- **REJECTED** — considered and explicitly declined, with a reason.
- **OBSERVED** — direct fact or owner visual observation.
- **AGENT CLAIM** — conclusion from an agent report not yet independently accepted.

### Filling order (recommended for the owner)

Do **not** try to complete every table in one pass. Suggested order:

1. **§4 Visual benchmark review** (or a linked ratings export) — this is the evidence the rest depends on.  
2. **§5 Product contract OPEN rows** — reconcile conflicting Q&A answers (especially 2D scope, Tauri, composite aggressiveness, “nearly all”).  
3. **§3 Shared findings + per-report verdicts** — short accept/qualify/reject; no need to re-summarize each report.  
4. **§1 Executive summary** — write last; it should quote your §4/§5 conclusions.  
5. **§8–§11** — release gate wording, keep/change/archive, binding decisions for final roadmap authors.  
6. **§12 Checklist** — only when the above are done.

### What the owner should prioritize writing (Grok guidance, 2026-08-08)

See also **§0** (Owner writing brief) for the full checklist of content Grok requests from you. Minimum viable owner report for final-roadmap authors:

| Priority | Section | Why |
| ---: | --- | --- |
| P0 | §4 (visual review) and/or link to ratings JSON from `asp-benchmark-assess` | Without this, agent consensus on “coherence first” remains unvalidated by *your* eyes |
| P0 | §5 OPEN rows + Appendix A conflicts you care about | Prevents agents from shipping contradictory roadmaps |
| P1 | §1.1–1.3 | One page anyone can read before writing `docs/moon/*` |
| P1 | §8.3–8.5 release gate + sequencing | Makes “v1.0” operational |
| P2 | §3 report ratings + keep/reject roadmap items | Archives which agent ideas you actually want |
| P2 | §11 Final owner decisions + instructions to roadmap authors | Binding handoff |
| Optional | §4.7 manual frame-selection experiment | Strongly recommended because the release gate permits it |
| Optional | §6 deep architecture tables | Only where you disagree with agent leanings |

Agents already did the long synthesis. **Your scarce value is visual judgment + conflict resolution**, not re-deriving package-import graphs.

### Weekend MVP (do this; ignore the rest until after ratings) *(added by Grok final pass, 2026-08-08)*

The document has many `[OWNER TODO]` markers by design. **You do not need to clear them all before starting ratings or before agents can draft a final roadmap skeleton.** For the next 24–48 hours, treat only this as blocking:

| # | Task | Where | Blocks final roadmap? |
| ---: | --- | --- | --- |
| 1 | Run / continue human visual ratings (full corpus preferred; large majority OK) | Inspector tool → export path in §4.2 + Appendix B | **Yes** |
| 2 | Write overall visual verdict + rough failure taxonomy | §4.3, §4.4 | **Yes** |
| 3 | Note ≥5 worst / ≥5 wins / ≥5 metric-disagreements (can grow later) | §4.5 | **Yes** |
| 4 | ≤5 binding conclusions from what you saw | §4.9 | **Yes** |
| 5 | Resolve the **load-bearing** conflicts only (not every Appendix A row) | §5 / Appendix A | **Yes** for: 2D scope, Tauri role, composite aggressiveness, “nearly all” definition, standalone priority, handoff elevated? |

**Explicitly deferrable until after ratings (will not block starting the rating pass):**  
§3 full prose reviews · §3.7 score matrix · §4.6–4.8 deep metric tables · §4.7 manual selection experiment (high value, second wave) · §6 architecture essays · §7 full research classification · §9–10 exhaustive keep/risk tables · polishing §1 until the end.

Agents reading this file: if only the Weekend MVP is filled, treat §6–§10 blanks as **not yet decided**, not as rejection of prior proposals.

### Contribution rules

1. Add every material edit to the changelog at the end of this file.
2. Do not rewrite another contributor's changelog entry.
3. Cite the report, roadmap, benchmark artifact, code path, or owner observation supporting a claim.
4. Distinguish historical benchmark numbers from fresh owner visual judgments.
5. Record disagreement; do not manufacture consensus.
6. Keep detailed experiment history in the relevant report/cache/archive and summarize it here.
7. The owner has final authority over product priorities and visual-quality verdicts.

### Concurrent editing protocol (added by Claude, 2026-08-08)

Four agent programs (`claude`, `codex`, `agy`/Gemini, `grok`) plus the owner
edit this file concurrently. To avoid silently clobbering each other:

1. **Re-read the file immediately before every edit session** — do not edit
   from a stale copy loaded earlier in your own conversation.
2. **Edit append-only or inside blocks you own** (your §3.x clarifications,
   your §5.x evidence subsection, your changelog row, your edit-map row).
   Never rewrite a peer's block; add a labeled response block instead.
3. **Shared tables** (§5 contract, Appendix A register): only *add* rows;
   never reword an existing row. If you dispute a row, add a
   `(disputed by <contributor>: …)` note in a new row or your own section.
4. If you find your previous edit missing or mangled, assume a write collision
   — restore it from your own record and note the restoration in the
   changelog rather than assigning blame.
5. The owner's edits always win; agents repair around them.

---

## 0. Owner Writing Brief (requested content)

*Added by Grok, 2026-08-08. This section is guidance for the owner’s contribution, not an owner decision.*

### 0.1 On the four status reports (what to write in §3)

Write **verdicts**, not re-analyses. For each report, ½–1 page total is enough if the tables are filled.

**Claude** (concise, high-signal status report):  
Expect agreement on ratings-first critical path, Hybrid as shippable spine, photometric borderline as cheap lever, no full rewrite. Decide: (a) VLM as routine judge vs advisory; (b) whether 2D starts in parallel with quality; (c) whether handoff elevates to spine (Claude later conceded yes).

**Codex/ChatGPT** (longest architecture/product review):  
Strongest on standalone packaging, project/undo document model, unified engine API, fallback accounting (safety ≠ algorithmic success), capability-oriented roadmap split. Decide: (a) 95/97 vs other “nearly all” definition; (b) standalone extraction timing vs your “launch bridge is enough” preference; (c) SQLite project model now vs later; (d) vertical-first vs must-have 2D (Codex vertical-first vs Grok must-have 2D from *your* answers to different agents).

**Gemini** (short, research-forward):  
Treat as a **research opportunity register**, not a committed phase plan. Explicitly accept/reject/park: PSO/DE replacing GNC-TLS BA; early PPO for global parameters; diffusion generative seams; Tauri restart now; local LLM copilot. Salvage candidates: interactive in-app guidance (start non-LLM); later RL/math-opt **on frame selection** (aligned with everyone else once gated).

**Grok** (detailed code+product+research assessment + product contract from Grok Q&A):  
Decide whether you still stand behind the Grok-session product contract (P1–P14): Hybrid spine + auto gate, handoff > isolated polish, aggressive composites + visible SCANS, 2D must-have, multi-output OK, selection-first ML/RL, Tauri as release UI / PySide6 prototype, standalone deprioritized, max options, SFW corpus after quality. Where Grok-session answers conflict with Codex/Claude-session answers, **pick one superseding answer in §5 and Appendix A**.

### 0.2 On the four proposed roadmaps (what to write in §3 and §8)

| Proposal | Use as… | Owner should say |
| --- | --- | --- |
| Claude | Measurement endgame + VLM tripwire + parallel B/C/D/E tracks | Keep A.1–A.5 shape? Parked handoff was wrong — confirm Handoff elevated |
| Codex | Capability map, release/usability/platform gates, project model, standalone foundation | Accept 95/97 provisional? Capability index multi-file set? |
| Gemini | Aggressive ML/opt phase list | Which items enter research backlog with entry gates vs REJECTED |
| Grok | Parallel Q/H/S/P tracks + locked product contract from Grok Q&A | Confirm/supersede P-table; keep selection-export-for-OpenCV |

**Recommended merge shape for final authors (Grok lean, non-binding):**  
Codex’s multi-document capability index **or** Claude’s ≤350-line single plan as the index; Grok/Claude parallel tracks for sequencing; Codex fallback accounting + project model; Claude VLM-after-ratings if you DECIDED it; Grok H1 handoff + S1 selection-first; Gemini items only inside research backlog with hard entry gates. Do **not** serialise “standalone foundation before all quality” if you reaffirm launch-bridge-only.

### 0.3 On the panoramic benchmark review (include this)

**Yes — include §4 (or a linked ratings export) in this admin report.**  
Grok, Claude, and Codex all treat owner visual judgment as the real success metric. Without it, final roadmaps will keep optimising ambient agent consensus instead of your actual failure classes.

If the full 97-case pass is in the inspector tool, you may:

1. Complete ratings in `asp-benchmark-assess` / evaluation JSON;  
2. Fill §4.2 context + §4.3 overall verdict + §4.4 taxonomy counts (even approximate);  
3. Fill §4.5 with **at least** worst 5 / best 5 / metric-disagreement 5 / borderline 5;  
4. Optionally attach paths in Appendix B;  
5. Write §4.9 (≤5 binding conclusions for the roadmap).

Also strongly recommended: **§4.7 manual frame-selection experiment** on a hard subset — your release gate explicitly allows “at most manual frame selection,” and no agent can settle whether that concession actually works without your trial.

### 0.4 What you do *not* need to rewrite

- Full pipeline stage tables (already in agent reports / state-of-pipeline).  
- Re-derivation of import graphs and CMake coupling (Codex/Grok already documented).  
- Pre-trim session archaeology (archive later; do not paste into §1).  
- Agreement paragraphs that only restate “corpus is valuable / human > metrics.”

### 0.5 Optional extras worth including if time allows

- Screenshots or path to montages for the 5 worst / 5 best cases.  
- Time-to-rate estimate after the real pass (for future VLM tripwire design).  
- Any case where **Hybrid-only** would have been faster than fighting auto.  
- Explicit list of roadmap items you want **deleted from active planning** (Gemini early generative seams, etc.).

---

## 1. Owner Executive Summary

### 1.1 Overall assessment

**Status:** `[OWNER TODO: OBSERVED / DECIDED]`

Write a candid summary in approximately three to eight paragraphs covering:

- what ASP is today;
- whether it is currently useful to you;
- whether the automatic output is presently trustworthy;
- whether HybridStitch is presently useful;
- the largest technical and product obstacles;
- which assets make the project worth continuing;
- what must be true before you consider ASP ready for its intended audience.

Suggested starting proposition to accept, revise, or reject:

> ASP is a strong research platform and promising human-assisted editor with exceptional evaluation assets, but it is not yet a standalone, production-ready desktop application and its automatic pipeline has not yet demonstrated reliable human-perceived superiority over OpenCV on the full corpus.

### 1.2 Current product identity

**Status:** `PROVISIONAL — based on owner answers; confirm wording`

Proposed statement:

> ASP is a local-first, capability-oriented research desktop application for reconstructing panoramas from extracted anime video frames. In the near term it serves the owner, a few friends, and researchers. Later it may serve anime screenshot wallpaper stitchers. HybridStitch is the primary human-facing workspace, while automatic stitching must eventually match or exceed OpenCV on nearly all benchmark cases with no intervention beyond, at most, manual frame selection.

`[OWNER TODO: Accept or edit this product identity.]`

### 1.3 Most important immediate actions

Rank no more than five immediate actions. Suggested candidates from the reports:

1. Complete the owner visual coherence/quality rating pass.
2. Turn those ratings into a failure taxonomy and metric calibration.
3. Decide the final product/UI spine and automatic release gate.
4. Specify auto-to-Hybrid project/state handoff.
5. Fix standalone package ownership and clean-clone execution.

`[OWNER TODO: Rank, edit, add, or remove.]`

---

## 2. Review Inputs and Provenance

### 2.1 Independent status reports

| Contributor | Report | Scope | Owner disposition |
| --- | --- | --- | --- |
| Claude | `.agent/reports/claude/ASP_Status_Report_2026-08-08.md` | Concise product, pipeline, benchmark, GUI, and repo assessment | `[OWNER TODO]` |
| Codex/ChatGPT | `.agent/reports/chat/asp_independent_product_architecture_review_2026-08-08.md` | Standalone-first product/architecture review, project model, testing, packaging, alternatives | `[OWNER TODO]` |
| Gemini | `.agent/reports/gemini/asp_analysis.md` | Short analysis emphasizing RL, swarm optimization, generative stitching, and interactive teaching | `[OWNER TODO]` |
| Grok | `.agent/reports/grok/asp_comprehensive_analysis_2026-08-08.md` | Detailed code, pipeline, benchmark, packaging, product, and research assessment | `[OWNER TODO]` |

### 2.2 Proposed roadmaps

| Contributor | Proposal | Shape | Owner disposition |
| --- | --- | --- | --- |
| Claude | `.agent/cache/claude/ASP_Proposed_Roadmap_2026-08-08.md` | Phases A–E: measurement endgame + VLM tripwire; quality; unparked 2D; RL/math-opt; hygiene. Handoff originally parked (later conceded elevation). | `[OWNER TODO]` |
| Codex/ChatGPT | `.agent/cache/chat/codex_proposed_asp_roadmap_2026-08-08.md` | Capability-oriented map; 95/97 provisional gate; standalone foundation first; project/undo model; Hybrid workspace; coherence-first core | `[OWNER TODO]` |
| Gemini | `.agent/cache/gemini/asp_next_gen_roadmap.md` | Four tech-led phases: CUDA PSO/DE BA; PPO params + generative seams; dual UI (Tauri now); interactive tutorials/LLM | `[OWNER TODO]` |
| Grok | `.agent/cache/grok/asp_proposed_roadmap_2026-08-08.md` | Product contract P1–P14; parallel tracks Q (quality) / H (Hybrid+handoff) / S (selection+ML) / P (PySide6→Tauri); selection export for OpenCV | `[OWNER TODO]` |

#### 2.2.1 Cross-roadmap consensus (AGENT CLAIM — Grok synthesis, 2026-08-08)

All four proposals (with Gemini more loosely) converge on:

- human (or human-calibrated) visual judgment as the release authority;
- HybridStitch as the human-facing spine while auto quality remains a release gate;
- frame selection / phase coherence as the highest-leverage algorithm work;
- ground-rule discipline (one change → one bench; no unmeasured default-ON);
- no complete C++/Rust rewrite as the quality strategy;
- archive chronological roadmap archaeology out of the active plan.

They **diverge** on sequencing and ambition of: standalone extraction priority, Tauri timing, 2D scope for v1, composite aggressiveness, VLM-as-judge, PSO/DE replacing BA, early generative seams, and multi-file vs single roadmap. Those divergences are catalogued in Appendix A.

### 2.3 Primary project evidence

At minimum, the final report should cite:

- `submodules/ASP/docs/moon/ROADMAP.md`
- `submodules/ASP/docs/reports/ASP_Critical_Evaluation_2026-07-08.md`
- `submodules/ASP/.agent/cache/asp_state_of_the_pipeline.md`
- `submodules/ASP/.agent/cache/asp_benchmark_2026-07.md`
- current full-corpus benchmark JSON and rendered comparisons;
- relevant postmortems for any experiment proposed for revival;
- code/build evidence for standalone coupling and test behavior.

`[OWNER/AGENT TODO: Add exact current benchmark artifact paths and commit hashes.]`

---

## 3. Owner Review of the Independent Reports

### 3.1 Findings shared by Claude, Codex/ChatGPT, and Grok

The three detailed reports substantially agree on the following. For each item, mark **accept**, **partly accept**, or **reject**, and explain why.

| Shared finding | Owner verdict | Owner reasoning/evidence |
| --- | --- | --- |
| The benchmark corpus, comparison harness, human-rating UI, and postmortems are strategic assets that must be preserved. | `[OWNER TODO]` | |
| Structural coherence and animation-phase/source selection are more fundamental than further seam micro-tuning. | `[OWNER TODO]` | |
| HybridStitch is the most credible artist-facing product spine today. | `[OWNER TODO]` | |
| Automatic results should feed editable Hybrid state rather than remain an isolated output. | `[OWNER TODO]` | |
| A complete C++ or Rust rewrite is not currently justified by the evidence. | `[OWNER TODO]` | |
| C++ should remain or expand selectively for measured hot paths. | `[OWNER TODO]` | |
| ASP is not genuinely standalone because of parent imports, native headers/bindings, paths, and test assumptions. | `[OWNER TODO]` | |
| The README, AGENTS instructions, and parts of the documentation still misdescribe ASP as a template. | `[OWNER TODO]` | |
| The active roadmap contains too much chronological history and should be split or archived. | `[OWNER TODO]` | |
| Human visual ratings must outrank proxy metrics. | `[OWNER TODO]` | |
| RL/evolutionary/generative work should be bounded by a named failure class and human-calibrated evaluation. | `[OWNER TODO]` | |
| PySide6 should remain the immediate working/prototyping UI. | `[OWNER TODO]` | |

### 3.2 Claude report review

**What I agree with:**  
`[OWNER TODO]`

**What I disagree with or would qualify:**  
`[OWNER TODO]`

**Evidence or priorities Claude missed:**  
`[OWNER TODO]`

**Claude roadmap items to retain:**  
`[OWNER TODO]`

**Claude roadmap items to modify, defer, or reject:**  
`[OWNER TODO]`

Prompts worth addressing:

- Is the human rating pass truly a 45–90 minute bounded task in your workflow?
- Should a calibrated VLM enter routine verdict generation, or remain advisory only?
- Should horizontal and diagonal work begin in parallel with quality work, or only after the vertical core stabilizes?
- Claude parks auto-to-Hybrid handoff polish later than Grok/Codex recommend. Which ordering do you prefer?

**Claude clarifications on the prompts above (added by Claude, 2026-08-08):**

- *VLM judge*: the owner already answered this in the Claude Q&A — yes, as the
  routine judge after the human pass, with manual re-checks on drastic score
  changes. My roadmap wires it into the verdict path with that tripwire
  (Phase A.3); what remains for the owner is only to confirm it here as
  `DECIDED` and set the tripwire threshold.
- *2D sequencing*: the owner's answer to Claude ("a LOT of appetite,
  including diagonal") is why my roadmap unparks 2D as a parallel Track C. If
  the Codex-session answer (vertical-first) governs instead, my C.1
  (axis-generalization refactor, byte-stable on the vertical corpus) still
  stands as the safe first step either way — the tracks only diverge at C.2+.
- *Auto→Hybrid handoff*: fair criticism. I kept it parked because the old
  roadmap parked it and my Q&A didn't surface the owner's P3/P4 answers
  (recorded by Grok). Given those answers, I now support elevating handoff to
  the product spine — Grok's H1 schema-first sequencing is the right shape,
  and my Track B/C items should feed intermediates through it.

### 3.3 Codex/ChatGPT report review

**What I agree with:**  
`[OWNER TODO]`

**What I disagree with or would qualify:**  
`[OWNER TODO]`

**Evidence or priorities Codex missed:**  
`[OWNER TODO]`

**Codex roadmap items to retain:**  
`[OWNER TODO]`

**Codex roadmap items to modify, defer, or reject:**  
`[OWNER TODO]`

Prompts worth addressing:

- Is `95/97` an acceptable provisional definition of “nearly all,” or should the target be `97/97`, category-weighted, or expressed differently?
- Should OpenCV fallbacks count only as safety, or toward release parity?
- Is a full project/document model with undo for masks, seams, warps, color, and crop worth building now, or should v1 start with only ordering/frame-selection undo?
- Should standalone extraction precede quality improvements, run in parallel, or wait?
- Is SQLite plus portable project export an acceptable storage direction?

### 3.4 Gemini report review

**What I agree with:**  
`[OWNER TODO]`

**What I disagree with or would qualify:**  
`[OWNER TODO]`

**Evidence or priorities Gemini missed:**  
`[OWNER TODO]`

**Gemini roadmap items to retain as research hypotheses:**  
`[OWNER TODO]`

**Gemini roadmap items to modify, defer, or reject:**  
`[OWNER TODO]`

The owner should explicitly review these proposals because they conflict with historical evidence and the other reports' sequencing:

- Replacing GNC-TLS/LM bundle adjustment with CUDA PSO or differential evolution before demonstrating that solver local minima are the dominant failure cause.
- Training PPO to tune pipeline thresholds before a validated reward signal and simpler optimization baselines exist.
- Discarding multi-band blending for generative stitching despite source-fidelity requirements and prior deletion of unmeasured generative systems.
- Restarting Tauri while the working PySide6 product and core quality remain unsettled.
- Adding a local LLM copilot before simpler contextual guidance is evaluated.

These ideas may remain in a research opportunity register, but should not become committed phases without explicit owner acceptance, a named failure class, baselines, cost estimates, and entry/exit gates.

### 3.5 Grok report review

**What I agree with:**  
`[OWNER TODO]`

**What I disagree with or would qualify:**  
`[OWNER TODO]`

**Evidence or priorities Grok missed:**  
`[OWNER TODO]`

**Grok roadmap items to retain:**  
`[OWNER TODO]`

**Grok roadmap items to modify, defer, or reject:**  
`[OWNER TODO]`

Prompts worth addressing:

- Grok treats horizontal and diagonal support as v1 must-haves, while your answer to Codex says vertical is the first production focus, horizontal is wanted, and diagonal may come later. Which statement governs the final roadmap?
- Grok treats Tauri as the release UI, while the other reports recommend continuing PySide6 until a measured reason to migrate. Is Tauri committed, provisional, or merely an option?
- Grok recommends more aggressive true composites and visible fallbacks. What risk of a visibly broken composite is acceptable?
- Is multi-output, such as one panorama per animation phase, an acceptable success result or only a diagnostic/advanced mode?
- Grok deprioritizes standalone packaging relative to algorithm work. Does that match your desired Image-Toolkit launch-bridge model?

**Grok clarifications on the prompts above (added by Grok, 2026-08-08):**

- *2D must-have:* Grok P6 is a faithful record of the **Grok-session** owner answer (“horizontal and diagonal are MUST have”), not an independent engineering claim. If the Codex-session vertical-first answer supersedes, mark Grok P6 `SUPERSEDED` in §5 and keep horizontal/diagonal as staged Track Q3 with vertical release-blocking only. If Grok-session governs, Codex’s “diagonal later” is `SUPERSEDED` and Q3/C tracks stay release-relevant.
- *Tauri as release UI:* Same provenance — Grok P9 records owner intent (PySide6 prototype + alternative; Tauri release shell). Grok’s roadmap still **quality-gates** Tauri unfreeze (not “restart scaffold tomorrow”). Claude/Codex freeze-until-bar is compatible if you define the unfreeze trigger explicitly in §5.
- *Aggressive composites:* Means “minimise SCANS when coherence holds,” not “ship torn anatomy.” After Q0 ratings, gates may loosen only where owner-rated coherence stays green. Visible fallback labels remain mandatory (P5).
- *Multi-output:* Grok recorded owner acceptance as **product-acceptable success**, not diagnostic-only. Confirm in §5; if accepted, evaluation must score multi-output honestly (not punish ASP for shipping N phase plates when one incoherent plate would fail).
- *Standalone deprioritised:* Matches owner “Launch ASP App button is enough.” Grok deliberately **does not** put Codex Capability A (full `asp_native` extraction) on the critical path. Soft hygiene (README, package aliases, fewer parent imports) can still proceed as non-blocking.
- *Handoff vs auto polish:* Grok P4 — when capacity conflicts, auto→Hybrid handoff wins. Aligns with post-clarification Claude and with Codex Hybrid-as-workspace; conflict with Claude’s original “park handoff” is resolved in favor of elevation unless owner rejects P4.
- *What Grok under-weighted vs peers:* project/undo document model (Codex is stronger); quantified 95/97 gate (Codex); VLM routine judge (Claude/owner-to-Claude); VRAM dual profiles (Claude); docs toolchain Vue-as-presentation (Claude). Owner should pull those from peers even if accepting Grok’s product contract.

### 3.6 Cross-agent synthesis (AGENT CLAIM — Grok, 2026-08-08)

| Theme | Claude | Codex | Gemini | Grok | Implication for owner |
| --- | --- | --- | --- | --- | --- |
| Ratings first | Yes (A.1) | Yes (eval system) | Implicit | Yes (Q0) | Do §4 / rating pass before algorithm debates |
| Hybrid spine | Yes | Yes | HITL keep | Yes (H track) | DECIDED-leaning across sessions |
| Auto release gate | Yes | Yes (95/97) | Indirect | Yes (nearly all) | Quantify “nearly all” in §8.3 |
| Selection first ML | Yes (D.1) | Yes | PPO broader | Yes (S1) | Converge on selection-first RL/opt |
| 2D scope | Parallel strong appetite | Vertical first | Not detailed | v1 must-have | **Owner must reconcile** |
| Standalone | Hygiene E.2 | Foundation first | N/A | Low priority | **Owner must reconcile** |
| Tauri | Frozen post-bar | Evidence-gated | Restart now | Release UI, quality-gated | **Owner must reconcile** |
| Generative seams | Parked + gates | Optional bg fill only | Replace blend | Reject wholesale revival | Reject default-on generative seams |
| PSO/DE replace BA | No | No | Phase 1 | No (selection PSO yes) | Keep GNC-TLS; opt elsewhere |
| Roadmap form | ≤350 single | Multi-file capabilities | 4 short phases | Tracks + later joint form | Choose in §8.1 |

### 3.7 Report quality and confidence

Rank each report on evidence quality, product insight, architecture insight, research usefulness, and agreement with your direct experience.

| Report | Evidence quality | Product insight | Architecture insight | Research usefulness | Overall confidence | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Claude | `[1–5]` | `[1–5]` | `[1–5]` | `[1–5]` | `[1–5]` | |
| Codex/ChatGPT | `[1–5]` | `[1–5]` | `[1–5]` | `[1–5]` | `[1–5]` | |
| Gemini | `[1–5]` | `[1–5]` | `[1–5]` | `[1–5]` | `[1–5]` | |
| Grok | `[1–5]` | `[1–5]` | `[1–5]` | `[1–5]` | `[1–5]` | |

---

## 4. Owner Review of ASP Benchmark Panoramas

### 4.1 Why this section is required

**Status:** `REQUIRED INPUT TO THE FINAL ROADMAP` *(strengthened from “recommended” by Grok, 2026-08-08 — still not an owner decision, but agent consensus is unanimous that final roadmaps must not ship without this evidence)*

All detailed reports agree that automated metrics do not reliably measure structural coherence. Your visual review is therefore not optional evidence if the roadmap is meant to prioritize actual quality work. It should be included even if the full 97-case rating pass is completed separately in the evaluation tool.

This section should summarize what your eyes say, not repeat SSIM tables.

**Minimum fill for roadmap authors (Grok):** §4.2 context + §4.3 overall verdict + §4.4 with at least relative frequencies + §4.5 ≥15 case rows (5 worst / 5 wins / 5 metric-disagreements) + §4.9 ≤5 binding conclusions. Full 97 counts can live in the ratings JSON and be summarized here.

**If ratings live primarily in the inspector export:** put the file path in §4.2 and Appendix B, then still write §4.3 / §4.9 in prose here so agents do not have to reverse-engineer the JSON.

### 4.2 Review context

| Field | Value |
| --- | --- |
| ASP commit | `[OWNER TODO]` |
| Benchmark JSON | `[OWNER TODO]` |
| Corpus version/hash | `[OWNER TODO]` |
| Models and hashes | `[OWNER/AGENT TODO]` |
| GPU/provider | `[OWNER TODO]` |
| Comparator versions | `[OWNER/AGENT TODO]` |
| Date rated | `[OWNER TODO]` |
| Rating tool/version | `[OWNER TODO]` |
| Number of cases reviewed | `[OWNER TODO]` |

### 4.3 Overall visual verdict

`[OWNER TODO: Describe how often ASP, OpenCV, Overmix, or Hugin produces the image you would actually keep. Separate genuine ASP composites from ASP outputs replaced by fallback.]`

### 4.4 Failure taxonomy from direct observation

Use counts if possible. If counts are not yet available, label examples and relative frequency.

| Failure class | Frequency/count | Severity | Representative cases | Likely stage | Notes |
| --- | ---: | --- | --- | --- | --- |
| Torn or phase-mixed anatomy | | Critical | | Selection/phase/composite | |
| Duplicated or repeated content | | Critical | | Matching/BA/ordering | |
| Misordered strips or trajectory | | Critical | | Selection/matching/BA | |
| Missing useful coverage | | High | | Selection/canvas/crop | |
| Exposure/luminance bands | | Medium–High | | Photometric/composite | |
| Hue/chroma shifts | | Medium–High | | Photometric/blend | |
| Visible seams | | Medium | | Seam/composite | |
| Ghosting | | Medium–High | | Phase/register/composite | |
| Excessive blur | | Medium | | Warp/blend/render | |
| Excessive fallback | | Product concern | | Gates/failure policy | |
| Crop/framing defects | | Medium | | Canvas/trim | |
| Other | | | | | |

### 4.5 Representative case notes

Record at least:

- five worst ASP cases;
- five clearest ASP wins;
- five cases where metrics and your visual judgment disagree;
- five borderline cases most likely to change roadmap priority;
- any case where manual frame selection alone fixes the result;
- any case where a single-phase or multi-output result would be preferable.

| Test | Preferred output | ASP genuine/fallback | Main defect or strength | Manual frame selection sufficient? | Recommended roadmap implication |
| --- | --- | --- | --- | --- | --- |
| `[test]` | | | | | |
| `[test]` | | | | | |
| `[test]` | | | | | |

### 4.6 Comparator-specific observations

#### ASP

`[OWNER TODO: Where does ASP uniquely win? Where does its complexity visibly hurt?]`

#### OpenCV SCANS

`[OWNER TODO: Why is it preferred when it wins? What defects does it retain?]`

#### Overmix

`[OWNER TODO: Which cases illustrate its sampling/reconstruction strengths or limitations?]`

#### Hugin

`[OWNER TODO: Where is it useful as a comparator, and where is it structurally unsuitable?]`

### 4.7 Manual frame-selection experiment

Because the proposed release gate permits at most manual frame selection, test and report it as a distinct track.

For a representative hard subset:

1. Choose frames manually without changing other pipeline parameters.
2. Run both ASP and OpenCV on the same selected set.
3. Record active selection time.
4. Judge coherence, fidelity, coverage, and final acceptability.
5. Determine whether selection alone closes the quality gap.

| Test | Default result | Manual selection time | ASP after selection | OpenCV after selection | Accepted? | Lesson |
| --- | --- | ---: | --- | --- | --- | --- |
| | | | | | | |

### 4.8 Metric trust review

For each metric, state whether it agrees with your visual priorities and what it may still diagnose.

| Metric | Trust for ranking? | Diagnostic use | Known disagreement/examples |
| --- | --- | --- | --- |
| Raw GT-SSIM | | | |
| Aligned GT-SSIM | | | |
| SI-FID | | | |
| Seam visibility | | | |
| Seam coherence | | | |
| Ghosting SIQE | | | |
| Sharpness | | | |
| Coverage | | | |
| Other | | | |

### 4.9 Benchmark conclusions that bind the roadmap

`[OWNER TODO: List no more than five conclusions. Each must name the observed failure class and the roadmap capability/workstream it should prioritize.]`

### 4.10 Rating reliability and reviewer-fatigue safeguards

*Added by Codex, 2026-08-08. This protects the quality of the evidence; it is
not another roadmap decision or a requirement to finish in one session.*

Because these ratings will calibrate metrics, possible VLM judgments, candidate
selectors, and future ML/RL rewards:

- split the corpus across as many sessions as needed and record approximate
  duration;
- randomize or blind comparator identity/order when supported, otherwise note
  that labels/order were visible;
- record confidence (`low` / `medium` / `high`) separately from quality;
- repeat a small stratified sample (suggested: 5–10 wins, losses, and
  borderline cases) later and record changed verdicts;
- score correctness/coherence separately from aesthetic preference;
- stop when attention degrades rather than forcing a fatigued nominal pass.

| Safeguard | What was done | Result / caveat |
| --- | --- | --- |
| Session split and duration | `[OWNER TODO]` | |
| Comparator blinding/randomization | `[OWNER TODO]` | |
| Confidence captured | `[OWNER TODO]` | |
| Repeat-consistency sample | `[OWNER TODO]` | |
| Correctness vs aesthetics separated | `[OWNER TODO]` | |

---

## 5. Product Contract

Record binding decisions in this table. Where prior Q&A answers conflict, explain which answer supersedes the other.

| Topic | Status | Owner decision | Rationale | Revisit condition |
| --- | --- | --- | --- | --- |
| Near-term target user | `DECIDED` | Owner, a few friends, researchers | | |
| Later target user | `DECIDED` | Anime screenshot wallpaper stitchers | | |
| Primary input | `DECIDED` | Extracted video frames | | |
| Product workflow | `DECIDED` | Fastest reliable human-assisted result | | |
| Automatic release gate | `PROVISIONAL` | Match/exceed OpenCV on nearly all cases with at most manual frame selection | Define “nearly all” | |
| Active user-time target | `DECIDED` | Approximately one minute per panorama | | |
| Primary OS | `DECIDED` | Kubuntu | | |
| Acceleration | `DECIDED` | CUDA primary; CPU-only remains useful | | |
| Inference locality | `DECIDED` | Local by default; service only optional alternative | | |
| Image-Toolkit relationship | `DECIDED` | Thin launch bridge is acceptable | | |
| Breaking current integration | `DECIDED` | Allowed | | |
| Main workspace | `DECIDED` | HybridStitch | | |
| Source fidelity | `DECIDED` | Optional small background generation only when explicitly enabled; off by default | | |
| Reproducibility | `DECIDED` | Material reproducibility, hardware caveats allowed | Define tolerance | |
| Commercial distribution | `DECIDED` | Not a current objective | | |
| Roadmap organization | `DECIDED` | Capability-oriented | | |
| Historical session material | `DECIDED` | Move to archive | | |
| Training tools placement | `OPEN` | Product, research mode, separate app, or CLI | | |
| Vertical scope | `PROVISIONAL` | First production focus *(Codex-session lean)* | Reconcile with Grok-session “2D must-have” | |
| Horizontal scope | `PROVISIONAL` | Active secondary *or* v1 must-have | Conflicting Q&A (Codex vs Grok sessions) | |
| Diagonal/complex geometry | `OPEN` | Later objective or v1 must-have? | Conflicting agent Q&A | |
| PySide6 vs Tauri | `OPEN` | | Conflicting agent Q&A | |
| Fallback aggressiveness | `OPEN` | | Conservative safety vs more true composites | |
| Multi-output by phase | `OPEN` | | Grok records owner acceptance; confirm | |
| VLM judge role | `OPEN` | | Advisory, triage, or verdict path | |
| Project undo scope | `OPEN` | | Ordering-only vs all edit operations | |
| Auto→Hybrid handoff priority | `PROVISIONAL — Grok-session; confirm` | Handoff more important overall than isolated auto polish; both matter | Owner answers to Grok #5–#6 | |
| Frame selection as first ML target | `PROVISIONAL — Grok-session; confirm` | First ML/math-opt priority; selection manifests reusable by OpenCV and ASP | Owner answer to Grok #14 | |
| Options richness vs flag cull | `PROVISIONAL — Grok-session; confirm` | Max user-selectable models/algorithms; cull default-OFF flags/dead trainers by owner quality judgment | Owner answers to Grok #16, #20 | |
| SFW public corpus timing | `PROVISIONAL — Grok-session; confirm` | After ASP performs decently on current NSFW-sourced GT bench; needed for CI/docs, not marketing | Owner answer to Grok #3 | |
| Documentation toolchain | `PROVISIONAL — owner answer in Claude Q&A; confirm here` | Drop Structurizr and Doxygen; keep MkDocs (portal) + Sphinx (API); the Vue site stays as the presentation layer that ingests MkDocs/Sphinx build output, not a parallel toolchain | Owner answer #6 to Claude, 2026-08-08 | |
| VRAM tiers | `PROVISIONAL — owner answer in Claude Q&A; confirm here` | Both high-VRAM (desktop, dual RTX 3090 Ti) and low-VRAM (laptop RTX 4080) profiles must be supported configurations | Owner answer #3 to Claude, 2026-08-08 | |
| Human rating pass timing | `PROVISIONAL — owner answer in Claude Q&A; confirm here` | Owner committed to running the Phase-0.1 human coherence pass the weekend of 2026-08-08/09 | Owner answer #2 to Claude, 2026-08-08 | |

### 5.1 Owner Q&A evidence from the Claude session (added by Claude, 2026-08-08)

Recorded here so the owner can confirm or supersede these answers in the tables
above rather than re-deciding from scratch. These were direct owner answers,
not agent proposals — but per the contribution rules, only the owner flips a
status to `DECIDED`:

- **Identity**: assistive tool first (HybridStitch spine, richer user
  parameters, editable intermediates), **but** the release bar is autonomous:
  match/beat OpenCV-class stitchers on nearly all benchmark tests with at most
  manual frame selection. (Matches Grok P2/P3 and Codex §2.1 — three sessions
  independently recorded the same pairing; this one appears genuinely settled.)
- **VLM judge**: accepted as the routine judge after the human pass, with the
  owner manually re-checking any test whose score changes drastically —
  i.e. the "calibrated judge + drastic-change tripwire" model. Relevant to the
  `VLM judge role` OPEN row: the owner's answer to Claude was more committal
  than the other sessions recorded.
- **RL/math-opt**: "not the point, but a very important means — a few steps
  below the threshold of being THE point"; owner is an RL/ML/math-opt
  researcher and wants to leverage that here. Consistent with Grok P12;
  stronger than Codex §15's hard-gated framing.
- **Image-Toolkit coupling**: "not really that important" — at the extreme, a
  `Launch ASP App` button suffices. Consistent with Grok P9 and Codex A5.
- **2D scope**: "a LOT of appetite" for the parked 2D-canvas work — horizontal
  **and diagonal**. Conflicts with the Codex-session answer (vertical first);
  see the Conflict Register row and §3.2 clarification.
- **License**: dual license exists because it's the owner's repo-template
  default, not an active commercial objective — supports the existing
  `Commercial distribution: Not a current objective` row.

### 5.2 Owner Q&A evidence from the Grok session (added by Grok, 2026-08-08)

Recorded so the owner can confirm or supersede. Full product contract encoding:
`.agent/cache/grok/asp_proposed_roadmap_2026-08-08.md` §0 (P1–P14).

- **Users**: near-term = owner + few friends/researchers only.
- **v1.0 gate**: match/exceed OpenCV on quality+coherence on nearly all tests;
  auto with zero effort or at most manual frame selection; no disjointed body
  parts / out-of-order strips.
- **Spine**: HybridStitch human-empowering tool is primary objective; ML/RL/math
  opt + human edits yield best quality; auto threshold still a release gate.
- **Handoff**: auto→Hybrid handoff more important overall than isolated auto
  quality work (both important).
- **Fallback**: SCANS remains visible; objective is to fall back as little as
  possible; prefer more aggressive true composites.
- **2D**: horizontal and diagonal alignments are MUST-have (conflicts with
  Codex-session vertical-first — owner must supersede one).
- **Multi-output**: acceptable product behavior (e.g. per animation phase).
- **SFW corpus**: wanted for CI/docs after decent performance on current bench;
  NSFW GT corpus retained because human artist stitches were easiest to source
  there — not a marketing blocker.
- **Toolkit**: launch-bridge sufficient; stitching lives in Image Stitch
  category with little cross-category coupling.
- **UI**: PySide6 for rapid prototypes + alternative desktop; **Tauri is the
  release cross-platform app**.
- **Compute**: CUDA primary; CPU Hybrid with degraded auto OK.
- **Perf**: willing to include a performance target per sequence.
- **License**: stay AGPL + commercial.
- **Flags/trainers**: delete default-OFF flags and dead trainers based on owner
  judgment of intermediate/final output quality (not pure dogma).
- **ML first target**: frame selection (also to help OpenCV / other stitchers).
- **RL/math-opt appetite**: moderate overall sequencing (ratings + classical
  parity first) but **very high** for RL/math-opt specifically on frame
  selection; research must-have (owner research work).
- **Options**: maximize end-user algorithm/model options.
- **Roadmaps**: both roadmap doc(s) and GitHub issues; single vs split form
  deferred to joint finalisation.

### 5.3 Owner Q&A evidence from the Codex session (summary pointer)

Codex’s product contract tables in its report/roadmap already encode:
vertical-first production focus, ~1 minute active user time, Kubuntu primary,
local-first inference, capability-oriented roadmaps, archive session history,
optional small generative bg fill off by default, commercial distribution not
a current objective. Where those conflict with §5.1–5.2, the owner’s superseding
row in the §5 table is authoritative — not the agent’s preferred session.

---

## 6. Architecture Decisions

### 6.1 Standalone boundary

**Status:** `[OWNER TODO: DECIDED / PROVISIONAL / OPEN]`

Choose or combine:

- Full ASP ownership: `asp_core`, `asp_gui`/`asp_desktop`, `asp_native`.
- Shared foundation package for genuinely generic Image-Toolkit/ASP components.
- Local engine process/API used by multiple frontends.
- Minimal launch-only integration with Image-Toolkit.

Record:

- target package names;
- dependency direction;
- compatibility strategy;
- native binding ownership;
- migration tolerance;
- order relative to quality work.

### 6.2 Engine execution model

`[OWNER TODO: Decide whether GUI, CLI, benchmark, and tests must use one typed engine API and whether CUDA work should run in a separate process.]`

### 6.3 Project format and undo

`[OWNER TODO: Decide the minimum v1 project state, persistence format, autosave/recovery requirements, and undo scope.]`

Recommended principle to review:

> Source frames remain immutable. Ordering, inclusion, masks, transforms, color corrections, seams, warps, crop, and generated-fill acceptance are stored as reversible parameters or operations, even if the first UI exposes undo incrementally.

### 6.4 UI strategy

`[OWNER TODO: Decide whether PySide6 is the product UI for the foreseeable future, a prototype before Tauri, or one of two intentionally supported clients.]`

Require a measurable reason before maintaining two complete UI implementations.

### 6.5 Configuration and objective profiles

`[OWNER TODO: Confirm whether user-facing Coherence/Fidelity/Coverage/Sharpness/Speed profiles should replace most direct environment-flag exposure, while research controls remain available in a lab mode.]`

### 6.6 Local models and optional service

`[OWNER TODO: Define model manager expectations, CUDA/CPU profiles, and what an optional service is allowed to do.]`

---

## 7. Research and Algorithm Decisions

### 7.1 Coherence-first reconstruction

`[OWNER TODO: Accept, modify, or reject phase/pose grouping before compositing as the main architectural direction.]`

Candidate components:

- temporal hold/cut analysis;
- adjacent-first background alignment;
- phase compatibility graph;
- coherent foreground source selection;
- robust background reconstruction;
- global photometric solve;
- semantic seam constraints;
- focused uncertainty questions to the user.

### 7.2 Frame selection

`[OWNER TODO: Decide whether frame selection is the first ML/optimization target and whether selected-frame manifests must be reusable by ASP and OpenCV.]`

### 7.3 Photometric fallback class

`[OWNER TODO: Based on visual review, decide whether borderline photometric failures are the cheapest near-term quality lever.]`

### 7.4 RL and mathematical optimization

For each proposal, select **active**, **research backlog**, **blocked on evidence**, or **rejected**.

| Proposal | Status | Required evidence before implementation | Baseline |
| --- | --- | --- | --- |
| Contextual bandit/RL for frame selection | | Human-calibrated reward and offline evaluation | Classical/DINO selection |
| PSO/CMA-ES/genetic search over selection parameters | | Bounded space and held-out evaluation | Grid/Bayesian/manual tuning |
| PSO/DE replacing bundle adjustment | | Evidence solver local minima dominate failures | Current GNC-TLS/LM |
| Optimization over seam/warp parameters | | Named residual failure class | Existing deterministic solver |
| PPO for global parameter tuning | | Stable reward, action bounds, simpler baselines | Profiles/Bayesian optimization |
| Learned candidate ranker | | Human labels and multiple candidates | Rules/calibrated metrics |

### 7.5 Generative processing

`[OWNER TODO: Confirm that generation remains off by default and is limited initially to small missing background regions. Decide whether generative seam synthesis is rejected, parked, or separately opt-in.]`

### 7.6 Training workbench

`[OWNER TODO: Define when training code earns a place in the main application and which existing trainers/models must be audited or archived.]`

---

## 8. Final Roadmap Structure

### 8.1 Recommended document set

The reports differ between one short roadmap and several specialized roadmaps. Proposed compromise:

1. **`ROADMAP.md` — capability index and priority map**
   - product contract;
   - current release gate;
   - capability statuses;
   - immediate priorities;
   - links to specialized plans.
2. **`roadmaps/product.md`**
   - Hybrid workspace;
   - project model;
   - tutorials;
   - platform and packaging;
   - Image-Toolkit bridge.
3. **`roadmaps/engine.md`**
   - standalone packages;
   - engine API;
   - native module;
   - CPU/CUDA execution;
   - performance and reliability.
4. **`roadmaps/research.md`**
   - failure classes;
   - phase/selection work;
   - ML/optimization experiments;
   - entry/exit gates;
   - rejected directions.
5. **`EVALUATION.md` or `roadmaps/evaluation.md`**
   - corpus tiers;
   - human rating protocol;
   - comparator policy;
   - metrics;
   - release acceptance.
6. **`archive/`**
   - old roadmap session narratives;
   - dated benchmark reports;
   - superseded state documents;
   - rejected experiment postmortems.

`[OWNER TODO: Accept this set, choose a smaller set, or define another structure.]`

### 8.2 Capability candidates

Prioritize and assign status:

| Capability | Priority | Status | Release-blocking? | Notes |
| --- | ---: | --- | --- | --- |
| Human visual evaluation foundation | | | | |
| Standalone application foundation | | | | |
| Persistent project and undo model | | | | |
| HybridStitch main workspace | | | | |
| Auto-to-Hybrid handoff | | | | |
| Unified engine/benchmark API | | | | |
| Coherence-first vertical reconstruction | | | | |
| Photometric quality | | | | |
| Frame selection/phase grouping | | | | |
| Local model/runtime manager | | | | |
| Objective profiles and tutorials | | | | |
| Horizontal reconstruction | | | | |
| Diagonal/general 2D reconstruction | | | | |
| Training/research workbench | | | | |
| Bounded RL/math optimization | | | | |
| Optional generative background fill | | | | |
| Tauri or alternative frontend | | | | |
| Public/SFW corpus | | | | |

### 8.3 Proposed automatic release-gate wording

`[OWNER TODO: Select and edit.]`

Candidate A — numerical:

> On the agreed 97-case corpus, at least 95 cases are human-rated equal to or better than OpenCV, no case contains a critical structural-coherence failure, and fully automatic and manual-frame-selection tracks are reported separately.

Candidate B — strict:

> ASP must be human-rated equal to or better than OpenCV on all benchmark cases; any remaining case must be resolved by manual frame selection alone before release.

Candidate C — category-based:

> ASP must have zero critical coherence regressions, must be no worse than OpenCV on at least the agreed percentage of each corpus category, and must exceed OpenCV on ASP's declared advantages such as coverage and sharpness wherever a genuine ASP composite ships.

### 8.4 Fallback accounting

`[OWNER TODO: Decide explicitly.]`

Recommended distinction:

- **Product safety success:** ASP detects risk and returns a clearly labeled safe OpenCV fallback.
- **ASP algorithmic success:** ASP's genuine reconstruction is preferred to or equal to OpenCV.
- **Release accounting:** report both; do not silently merge them.

### 8.5 Work sequencing

`[OWNER TODO: Rank the first three owner tasks and first five agent work packages after the report is complete.]`

---

## 9. Keep, Change, Archive, and Reject

### 9.1 Keep

`[OWNER TODO: Confirm and add reasons.]`

Suggested baseline:

- benchmark corpus and visual evaluation tools;
- postmortems and negative research knowledge;
- HybridStitch correction tools;
- C++ kernels with measured value;
- classical fallback path;
- tutorials and samples;
- human-over-metric evaluation discipline;
- one-change/one-benchmark discipline.

### 9.2 Change

`[OWNER TODO: Confirm and rank.]`

Suggested baseline:

- package and dependency direction;
- automatic-to-Hybrid workflow;
- persistent project model;
- phase/source selection architecture;
- benchmark execution-path duplication;
- user-facing configuration;
- active roadmap size and status accuracy;
- model installation and provider handling.

### 9.3 Archive

`[OWNER TODO: List exact files/directories after agent inventory.]`

Include old session-level roadmap material, superseded reports, and rejected experiments. Preserve discoverability through an archive index.

### 9.4 Reject or freeze

`[OWNER TODO: Decide.]`

Candidates:

- new unmeasured gates;
- broad threshold-tuning sessions;
- wholesale resurrection of deleted RLHF/MFSR/generative stacks;
- complete language rewrite before profiling and product validation;
- second full UI implementation without a committed migration reason;
- mandatory cloud inference;
- default-on generative filling.

---

## 10. Risks and Constraints

For every accepted risk, name a mitigation and trigger.

| Risk | Likelihood | Impact | Mitigation | Trigger/revisit condition |
| --- | --- | --- | --- | --- |
| Proxy metrics reward visually incoherent output | | | | |
| Human ratings depend on one person | | | | |
| Research work displaces product usability | | | | |
| Product/packaging work displaces core quality | | | | |
| Standalone extraction causes integration regressions | | | | |
| Two UI stacks double maintenance | | | | |
| CUDA-first design neglects useful CPU operation | | | | |
| Model or dataset licenses block future distribution | | | | |
| Project format changes invalidate work | | | | |
| RL/optimization overfits the private corpus | | | | |
| Generative output violates fidelity expectations | | | | |
| Full 2D scope delays reliable vertical results | | | | |

---

## 11. Final Owner Decisions

This section should be concise and binding. Fill it after completing the review sections.

### 11.1 Accepted consensus

`[OWNER TODO]`

### 11.2 Accepted minority recommendations

`[OWNER TODO: Identify valuable recommendations even if only one report proposed them.]`

### 11.3 Rejected recommendations

`[OWNER TODO: Give a brief reason and revisit condition where appropriate.]`

### 11.4 Remaining experiments needed before decisions

`[OWNER TODO]`

### 11.5 Instructions to final-roadmap authors

`[OWNER TODO: State what documents to create/update/archive, which decisions are fixed, and what remains explicitly provisional.]`

---

## 12. Completion Checklist

### 12.1 Weekend MVP (required before final roadmap lock)

- [ ] Visual benchmark review completed or linked (§4.2–4.5, §4.9).
- [ ] Load-bearing conflicts reconciled (§5 / Appendix A: at least 2D, Tauri, composites, nearly-all, standalone, handoff).
- [ ] Ratings export path recorded (Appendix B).

### 12.2 Full report (required before calling this document “complete,” not before starting ratings)

- [ ] Owner executive summary completed.
- [ ] Each independent report reviewed separately.
- [ ] Shared findings accepted, qualified, or rejected.
- [ ] Manual frame-selection track sampled.
- [ ] Metric trust conclusions recorded.
- [ ] Product contract finalized (remaining OPEN rows).
- [ ] Automatic release gate quantified.
- [ ] Fallback accounting decided.
- [ ] UI strategy decided.
- [ ] Vertical/horizontal/diagonal scope decided.
- [ ] Standalone extraction priority decided.
- [ ] Project/undo scope decided.
- [ ] RL/optimization proposals classified.
- [ ] Generative policy confirmed.
- [ ] Final roadmap document set chosen.
- [ ] Archive policy and initial targets listed.
- [ ] Immediate owner and agent tasks ranked.
- [ ] Every contributor has added a changelog entry.

---

## 13. Collaborative Changelog

### Changelog rules

- Append new entries at the top of the table, immediately below the header.
- Use one row per editing session or logically atomic contribution.
- Do not edit or delete another contributor's row; add a correcting row if needed.
- Name exact sections changed and summarize material decisions or evidence added.
- Mark whether the edit changed an owner decision, added evidence, changed structure, or only corrected wording.
- When adding new content blocks or table rows outside §13, label them inline
  with `(added by <contributor>, <date>)` — so attribution is visible at the
  point of the edit, not only in this changelog.
- After any material edit, also update your contributor row in the Section
  Edit Map below (each contributor maintains only their own row).

### Section edit map (at-a-glance attribution)

One row per contributor; each contributor edits only their own row. This map
answers "who has touched what" without reading the full changelog.

| Contributor | Sections created | Sections materially edited | Sections with inline additions |
| --- | --- | --- | --- |
| ACFHarbinger (owner) | Original stub (title, metadata) | — | — |
| Codex/ChatGPT | §§1–12, Appendices A–B, §13 structure | §4.10, §13 | §4.10 (rating reliability safeguards) |
| Gemini | — | — | §13 (contribution notes) |
| Claude | §5.1, §13 edit map, Concurrent editing protocol (How-to-use) | §13 (changelog rules: inline-attribution + edit-map rules) | §3.2 (clarifications block), §5 (3 provisional rows), Appendix A (3 conflict rows) |
| Grok | §0; §2.2.1; §3.6; §5.2–5.3; Weekend MVP; §12.1/12.2 | How-to-use filling order + MVP; §2.2; §3.5; §4.1; §5; §12; §13; Appendix A handoff | §3.5, §4.1, §5, Appendix A–C |

| Timestamp (Europe/Lisbon) | Contributor | Role/model | Sections changed | Change type | Summary | Owner decision affected? |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-08-08 | Codex | OpenAI coding agent | §4.10, §13 | Evidence-quality safeguard | Final pass: added a compact visual-rating reliability protocol covering session splitting, blinding/randomization, confidence, repeat consistency, correctness-vs-aesthetics separation, and reviewer fatigue. No roadmap decision or one-session deadline was introduced. | No |
| 2026-08-08 | Grok | Agent reviewer (xAI) — final structure pass | Status; Weekend MVP; §12.1/12.2; Appendix A handoff; §13 | Structure (final-pass) | Re-read full admin report after peer edits. **Satisfied: structure is good enough to start owner ratings today.** Added Weekend MVP so ~100 OWNER TODOs do not block the rating pass; split checklist into MVP vs full; fixed stale handoff conflict (Claude conceded elevation). No further agent template expansion requested; remaining work is owner-only. | No |
| 2026-08-08 | Claude | Agent reviewer (Fable 5) | How-to-use (concurrent editing protocol), §13 edit map | Structure (final-pass review) | Final review pass over the full report including Grok's §0/§2.2.1/§3.5–3.6/§5.2–5.3/Appendix A–C additions: agree with all of them, no disputes filed. Added a concurrent-editing protocol (re-read before edit, append-only in shared tables, own-block editing, collision recovery) since four agent programs edit this file simultaneously. Confirmed satisfaction with the report structure; remaining work is owner-only. | No |
| 2026-08-08 | Grok | Agent reviewer (xAI) | How-to-use, §0, §2.2, §2.2.1, §3.5–3.7, §4.1, §5, §5.2–5.3, §13, Appendix A | Structure + evidence + owner guidance | After reading all four status reports and four roadmaps: added §0 owner writing brief (what to write vs skip; require visual §4; roadmap merge lean); filling-order guide; fixed Codex roadmap path to `.agent/cache/chat/...`; cross-roadmap consensus §2.2.1; Grok clarifications under §3.5 (2D/Tauri/composites/multi-output/standalone provenance); cross-agent synthesis table §3.6; strengthened §4.1 minimum-fill requirements; Grok-session Q&A as §5.2 + provisional contract rows (handoff, selection-first ML, options, SFW timing); Codex session pointer §5.3; Appendix A supersession note. No status flipped to DECIDED. | No |
| 2026-08-08 | Claude | Agent reviewer (Fable 5) | §3.2, §5, §5.1, §13, Appendix A | Evidence + structure | Added owner Q&A evidence from the Claude session as §5.1 plus three `PROVISIONAL` product-contract rows (docs toolchain, VRAM tiers, rating-pass timing); added Claude clarifications under §3.2 (VLM judge already answered; 2D sequencing conflict; concedes elevating auto→Hybrid handoff); added three Appendix A conflict rows (docs toolchain end-state, RL priority level, Tauri unfreeze trigger); added inline-attribution + section-edit-map rules and the edit map itself to §13. No status flipped to DECIDED. | No |
| 2026-08-08 | Gemini | Agent reviewer | §13 (Changelog and Detailed contribution notes) | Contribution record | Reviewed the consolidated report and added contribution notes/instructions for the owner regarding the proposed ML/Optimization roadmap items. | No |
| 2026-08-08 | Codex/ChatGPT | Agent reviewer | Entire document; especially §§2–8 and changelog | Structure + synthesis | Expanded the original 11-line owner stub into a collaborative report template; added report/roadmap provenance, consensus and conflict review, required visual benchmark section, product/architecture/research decision tables, proposed roadmap structure, completion checklist, and append-only changelog. No owner decision was changed. | No |
| 2026-08-08 | ACFHarbinger | Human owner | Title, metadata, initial `Roadmap Review` stub | Initial creation | Created the owner/admin roadmap-review report placeholder. | No |

### Detailed contribution notes

Contributors may add a subsection here when a table row is too short to explain their work.

#### Grok — 2026-08-08 (final structure pass)

- Re-read full admin report (~1160 lines) and changelog after peer contributions.
- **Verdict: sufficiently satisfied.** Format asks for the right scarce things
  (visual §4, conflict supersession, release-gate wording). Further agent
  expansion would add friction, not clarity. Owner should start ratings now.
- Remaining weaknesses accepted, not fixed: some §3 prompts still echo stale
  Claude handoff park (clarifications already correct it); Grok §0 guidance
  slightly overlaps How-to-use priority table; Gemini’s detailed contribution
  is thinner than peers — acceptable.
- Only structural adds this pass: Weekend MVP + §12.1/12.2 split + stale
  Appendix A handoff note + status line.

#### Grok — 2026-08-08 (initial synthesis pass)

- Read all four independent reports
  (`.agent/reports/{claude,chat,gemini,grok}/`) and all four proposed roadmaps
  (`.agent/cache/{claude,chat,gemini,grok}/`), plus the admin template as
  expanded by Codex and annotated by Claude/Gemini.
- **Reports:** Claude = best short status + critical path clarity; Codex =
  deepest product/architecture (standalone, project model, fallback
  accounting); Grok = deepest pipeline/benchmark archaeology + explicit
  product contract from owner Q&A; Gemini = research-forward short piece —
  useful as opportunity register, not as committed phases (PSO/DE BA, early
  PPO, generative seams conflict with postmortems and owner fidelity policy).
- **Roadmaps:** Converge on ratings → selection/coherence → Hybrid assist;
  diverge on standalone-first (Codex) vs quality/handoff-first (Grok), 2D
  scope, Tauri timing, VLM judge, and Gemini’s Phase-1 solver replacement.
  Claude later correctly elevated handoff after seeing Grok P3/P4.
- **What I want the owner to write:** (1) §4 visual review or linked ratings
  export — **required**; (2) supersede conflicting Q&A rows in §5 / Appendix A
  (especially 2D, Tauri, composite aggressiveness, nearly-all definition);
  (3) short §3 accept/qualify/reject per report — not re-analysis; (4) §8.3
  release-gate wording + §11 instructions to final roadmap authors; (5)
  optional but high value: §4.7 manual frame-selection experiment.
- **What I do not want bloated:** re-deriving import graphs, stage tables, or
  pre-trim session logs inside this admin doc.
- **Merge lean for final roadmaps (non-binding):** multi-doc or ≤350 index OK;
  parallel Q/H/S tracks; selection-first RL/math-opt; handoff elevated;
  Codex fallback accounting; Claude VLM-after-ratings only if owner DECIDES;
  Gemini items hard-gated research backlog; standalone not critical path if
  launch-bridge remains the product decision.
- Did not fill `[OWNER TODO]` or flip any status to `DECIDED`.

#### Claude — 2026-08-08

- Read all four independent reports (`.agent/reports/{claude,chat,gemini,grok}/`)
  and all four proposed roadmaps (`.agent/cache/{claude,chat,gemini,grok}/`).
- Assessment of convergence: Claude, Codex, and Grok agree on essentially every
  load-bearing conclusion (assets to keep, coherence/selection as root cause,
  HybridStitch as spine, no C++ rewrite, ratings pass as critical path, roadmap
  hygiene). The real merge work is the ~15 conflicts in Appendix A, most of
  which trace to the owner giving different emphasis to different agents in
  parallel Q&A sessions — the owner reconciling those answers matters more
  than any further agent analysis.
- Position on Gemini's proposals: I side with Codex's assessment — PSO/DE
  bundle adjustment, early PPO parameter tuning, and diffusion-based seam
  generation are research hypotheses that contradict recorded evidence
  (GNC-TLS is not the documented failure locus; the pre-trim RLHF/generative
  deletions are settled negative history; owner fidelity policy). They belong
  in a research register with entry gates, not in committed phases. Gemini's
  Avenue D (interactive in-app guidance) is the most salvageable item, but
  should start as simple contextual suggestions (old Phase 6.4) before any
  embedded LLM copilot.
- Position updates after reading peers: (1) elevate auto→Hybrid handoff to
  product spine (Grok H1 sequencing; my roadmap had it parked); (2) adopt
  Codex's fallback-accounting distinction (safety success ≠ algorithmic
  success) into the release gate — my proposal under-specified this; (3) my
  weekend-rating-pass + VLM-tripwire critical path stands and now has explicit
  owner commitment recorded in §5.1.
- Deliberately did not fill any `[OWNER TODO]`, flip any status, or resolve
  any Appendix A conflict — per contribution rule 7.

#### Gemini — 2026-08-08

- Read and analyzed the admin report structure established by Codex.
- Reviewed the conflicts identified by Codex regarding my aggressive proposals for PSO/DE Bundle Adjustment, PPO parameter tuning, and generative in-painting.
- Provided direct feedback to the owner on what to address in §3.4 and §4, specifically requesting that the visual benchmark review determine whether local minima (structural drift) and ghosting are severe enough to warrant unblocking my proposed ML/Optimization research paths.
- Did not mutate the core document structure as it is already well-organized for the final synthesis.

#### Codex/ChatGPT — 2026-08-08

- Compared the Claude, Codex/ChatGPT, Gemini, and Grok status reports.
- Compared all four proposed roadmaps.
- Marked shared conclusions separately from conflicting recommendations.
- Added prompts to reconcile inconsistent owner-answer interpretations across agent sessions.
- Recommended that the owner include a direct visual benchmark review, a manual-frame-selection experiment, and metric-trust assessment because automatic metrics do not adequately encode structural coherence.
- Treated Gemini's PSO/PPO/generative-first ideas as research hypotheses requiring evidence rather than consensus roadmap commitments.
- Preserved the owner as the sole authority for final product and visual-quality decisions.
- Final pass: added §4.10 so the owner review records confidence, review
  conditions, a small repeat-consistency sample, and fatigue/blinding caveats
  before its ratings become optimization targets.

---

## Appendix A — Conflict Register

Resolve each conflict in the main report and record the final location.

**Supersession rule (added by Grok, 2026-08-08):** When the same owner gave
different emphasis in parallel agent Q&A sessions, the resolution is **not**
“average the agents.” Pick one row status (`DECIDED`) in §5, note the
superseded session answer in *Owner resolution*, and point final-roadmap
authors at that single cell. Agents must not keep both as active requirements.

| Conflict | Position A | Position B | Owner resolution | Recorded in |
| --- | --- | --- | --- | --- |
| Release exception count | Codex proposes provisional 95/97 | Claude/Grok leave “nearly all” for owner; strict 97/97 remains possible | `[OWNER TODO]` | |
| Fallback accounting | Safe fallback is product success but not ASP algorithmic success | Existing roadmap can mechanically improve verdict counts through fallback | `[OWNER TODO]` | |
| Composite policy | Conservative safety first | Grok proposes more aggressive true composites after ratings | `[OWNER TODO]` | |
| Manual frame selection | Separate assisted benchmark track | May be folded into the release gate | `[OWNER TODO]` | |
| Vertical/horizontal/diagonal scope | Codex Q&A: vertical first, horizontal active, diagonal later | Grok Q&A: horizontal and diagonal are v1 must-haves | `[OWNER TODO]` | |
| UI strategy | Claude/Codex: PySide6 now; Tauri frozen or evidence-gated | Grok/Gemini: Tauri is eventual/release UI | `[OWNER TODO]` | |
| Standalone priority | Codex: foundational and early | Grok: deprioritized versus quality/handoff | `[OWNER TODO]` | |
| Auto-to-Hybrid timing | Codex/Grok: product-spine priority | Claude *original* park (later **conceded elevation** in §3.2 clarifications) | `[OWNER TODO — likely DECIDED elevate unless owner objects]` | |
| VLM judge | Claude: calibrated routine verdict source with human tripwire | Other reports: human authority; VLM role less committed | `[OWNER TODO]` | |
| Undo scope | Ordering minimally requested | Codex recommends all edit parameters be reversible | `[OWNER TODO]` | |
| Bundle adjustment research | Gemini: replace LM/GNC with PSO/DE | Others: no evidence this is the dominant failure; keep robust BA | `[OWNER TODO]` | |
| RL sequencing | Gemini: PPO parameter tuning early | Others: selection-first and only after human-calibrated rewards | `[OWNER TODO]` | |
| Generative seams | Gemini: replace blend with diffusion | Owner/Codex: optional small background fill only, off by default | `[OWNER TODO]` | |
| Roadmap form | One ≤350-line active roadmap | Several capability-specific roadmaps plus index | `[OWNER TODO]` | |
| Docs toolchain end-state | Owner-to-Claude: keep Vue site as presentation layer ingesting MkDocs+Sphinx output; drop Structurizr+Doxygen | Codex: consolidate to one portal plus API docs; "unused documentation build systems" listed for removal | `[OWNER TODO]` | |
| RL/math-opt priority level | Owner-to-Claude + Grok P12: important means, near-the-point, must-have research track gated only on ratings/judge | Codex: research workbench, hard-gated behind named failure class, baselines, and product foundations | `[OWNER TODO]` | |
| Tauri unfreeze trigger | Grok: quality-progress gate (possibly pre-v1.0); Gemini: restart now as premium UI | Claude/Codex: stays frozen until after the release bar / measured migration reason | `[OWNER TODO]` | |

---

## Appendix B — Suggested Evidence Attachments

Link rather than embed large assets where possible:

- current benchmark summary JSON;
- owner ratings export;
- selected worst/win/borderline montage directory;
- frame-selection manifests used in the manual-selection experiment;
- metric-versus-human correlation report;
- fallback reason histogram;
- source/provider/model manifest;
- standalone dependency/import audit;
- roadmap/archive migration manifest.

### B.1 Known artifact pointers (fill/correct)

| Artifact | Expected location / notes | Status |
| --- | --- | --- |
| Full-corpus checkpoint (2026-08-07) | `anime_stitch_20260807_045552.json` (under ASP `backend/benchmark/output/` or local `dump/`) | `[OWNER/AGENT TODO: exact path on this machine]` |
| Prior full-corpus (2026-07-28) | `anime_stitch_20260728_013215.json` | `[OWNER/AGENT TODO]` |
| Human ratings export | `data/benchmarks/asp_evaluations_*.json` or `data/human_ratings/asp_ratings_*.json` (per roadmap tooling) | `[OWNER TODO after rating pass]` |
| State of pipeline | `submodules/ASP/.agent/cache/asp_state_of_the_pipeline.md` | Exists |
| Critical evaluation | `submodules/ASP/docs/reports/ASP_Critical_Evaluation_2026-07-08.md` | Exists |
| Agent status reports | `.agent/reports/{claude,chat,gemini,grok}/` | Exists |
| Agent roadmap proposals | `.agent/cache/{claude,chat,gemini,grok}/` | Exists |
| This admin report | `.agent/reports/admin/asp_20260808_status_report.md` | Live |

---

## Appendix C — Owner scratch pad (optional)

*Empty by design. Owner may dump raw notes, case IDs, or rating-session
thoughts here before promoting them into §4 structured tables. Agents should
not edit this appendix unless invited.*

```
[OWNER TODO: freeform notes]
```
