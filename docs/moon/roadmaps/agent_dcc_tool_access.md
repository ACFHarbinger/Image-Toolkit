# Agent DCC Tool Access (MCP or equivalent)

## Status

Noted future work (2026-08-20, Harbinger). Not scoped, not scheduled, no
phase assignment yet. Recorded here so it isn't lost, not as a commitment
to a design.

## Goal

Give AI coding-assistant agents (Claude, Gemini, etc. — the same
multi-agent team that works this codebase) direct tool-use access to
Krita, Blender, and OpenToonz, via an MCP server or an equivalent
tool-calling service, hosted in this submodule (CSG).

## Why here, not a new submodule

CSG already owns the Krita plugin relationship (see
[Engine Architecture Roadmap](engine_architecture.md) — "Krita plugin
first, Blender and future desktop clients later") and the standalone
engine boundary this would sit behind. An agent-facing tool layer for
these three DCC apps is a natural extension of that boundary, not a new
concern.

## Forward integration target

Designed so it can later be wired into `~/Repositories/Repos/Coding-Assistants`
(a separate app, not part of Image-Toolkit) — i.e. the tool surface should
not be hard-coupled to CSG's own agent workflow. Concretely, this likely
means: a standard MCP server (or an equivalent typed tool-calling protocol)
process per application, speaking to Krita/Blender/OpenToonz through their
existing scripting/plugin APIs (Krita's Python scripting API, Blender's
`bpy` Python API, OpenToonz's plugin/scripting surface), rather than
UI automation — so the same server binary/process can be pointed at by
either this codebase's agents or Coding-Assistants' agents without
CSG-specific assumptions baked in.

## Open questions (not answered yet)

- One MCP server per app, or one server multiplexing all three?
- How this relates to the existing/planned Krita plugin process boundary
  in [Engine Architecture Roadmap](engine_architecture.md) — same process,
  sibling process, or fully independent?
- Auth/sandboxing model when a second, separate app (Coding-Assistants)
  is also a client.
- Whether OpenToonz's plugin surface is sufficient for meaningful agent
  control, or whether pattern/read-only access is the realistic v1 scope.

## Non-goals (for now)

- Replacing CSG's own in-progress standalone engine/editor work (Phase 5).
- A finished Coding-Assistants integration — that app is out of scope for
  this repo; this only needs to not preclude it.
