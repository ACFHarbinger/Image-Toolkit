# AGENT_BUS.md — Hybrid Image Editor (HIE) Multi-Agent Communication Bus

Welcome to the **Hybrid Image Editor (HIE)** agentic coordination hub. All agents (Gemini, Chat, Claude, Grok) working on `submodules/HIE` and cross-submodule tasks post updates here.

---

## Task Delegation & Coordination (Website & Pipeline Integration)

### Submodule Website Creation & Navigation Link Handoff

| Submodule | Target Location | Lead Agent | Status | Key Features |
|---|---|---|:---:|---|
| **ASP** | `submodules/ASP/docs/website/` | **Gemini** | 🚀 In Progress | Panorama Stitching, Motion Model $[t_x, t_y, s]$, GNC-TLS, Cel Barrier |
| **CRE** | `submodules/CRE/docs/website/` | **Chat** | 🚀 In Progress | Local-First pgvector Hybrid Semantic Recommendation Engine |
| **CSG** | `submodules/CSG/docs/website/` | **Chat** | 🚀 In Progress | Manga Colorization, Layer Canvas, Mesh Overlay, Puppeteering |
| **HIE** | `submodules/HIE/docs/website/` | **Gemini** | 🚀 In Progress | ML (BiRefNet, Real-ESRGAN), RL Brush Assistant, Exact DP/PSO Pipeline |

### Key Requirements
1. **Theme Consistency:** Follow Image-Toolkit dark-cyberpunk theme (`#0a0a0c` dark bg, `#00f0ff` cyan accent, `#ff0055` pink highlights, clean typography).
2. **Back Link:** Every submodule website must feature a visible **"Back to Image-Toolkit"** button/icon linking to `https://acfharbinger.github.io/Image-Toolkit/`.
3. **Pipeline Page Integration:** Update `docs/website/src/pages/Pipeline.tsx` and `docs/website/src/constants/submodules.ts` on the main Image-Toolkit website to add a **Submodules** section allowing users to select and open any submodule's website.
