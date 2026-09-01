// Hand-curated (not generated) from .agent/AGENTS.md §4 and docs/ARCHITECTURE.md's
// module dependency graph — feeds the "Module Explorer" hub panel
// (the React home-page module explorer).
import type { ModuleCard } from "../interfaces/types";

export const moduleCards: ModuleCard[] = [
  {
    slug: "base",
    title: "base/",
    tagline: "C++ core engine",
    description:
      "High-performance image processing, crawling, and sync logic. Built with CMake + pybind11; exposes file_system, image_converter, image_merger, image_finder, video_converter, wallpaper, and the Selenium-backed crawlers (danbooru, gelbooru, sankaku).",
    stack: ["C++", "pybind11", "CMake", "OpenMP"],
    path: "/ARCHITECTURE",
    docSource: "docs/ARCHITECTURE.md",
    layer: "engine",
  },
  {
    slug: "backend",
    title: "backend/",
    tagline: "Python orchestrator",
    description:
      "Wraps the C++ core, owns the pgvector database (image_database.py), the VaultManager security layer, and the pure-Python/PyTorch ML models. Thin wrappers only — heavy logic stays in base/.",
    stack: ["Python", "PyTorch", "pgvector", "Hydra"],
    path: "/api/python/core",
    docSource: "docs/api/python/core.md",
    layer: "engine",
  },
  {
    slug: "api",
    title: "api/ & tasks/",
    tagline: "Django/Celery bridge",
    description:
      "Synchronous REST API (Django) and idempotent Celery workers that bridge the API surface to backend/src without embedding business logic in the tasks themselves.",
    stack: ["Django", "Celery", "REST"],
    path: "/api/rest-api",
    docSource: "docs/api/rest-api.md",
    layer: "interface",
  },
  {
    slug: "gui",
    title: "gui/",
    tagline: "Desktop interface",
    description:
      "PySide6 (Qt for Python) desktop app. Feature tabs (convert, wallpaper, merge…) run heavy work off the main thread via QThread workers, communicating back through Qt signals.",
    stack: ["PySide6", "Qt", "QThread"],
    path: "/tutorials/index",
    docSource: "docs/tutorials/index.md",
    layer: "interface",
  },
  {
    slug: "frontend",
    title: "frontend/",
    tagline: "React + Tauri hybrid",
    description:
      "React 19 + TypeScript, shipped as a Tauri desktop app (with an Electron dev mode). Secure IPC via preload.js, no nodeIntegration. Also home to the math backbone TypeDoc'd on this site.",
    stack: ["React 19", "TypeScript", "Tauri", "Electron"],
    path: "/api/typescript/readme",
    docSource: "docs/api/typescript/readme.md",
    layer: "interface",
  },
  {
    slug: "app",
    title: "app/",
    tagline: "Mobile (Android / iOS)",
    description:
      "Native mobile clients: Jetpack Compose/XML + Coroutines on Android (Kotlin), SwiftUI + Swift Concurrency on iOS. MVVM on both, with secure credential storage.",
    stack: ["Kotlin", "Jetpack Compose", "Swift", "SwiftUI"],
    path: "/api/kotlin/index",
    docSource: "docs/api/kotlin/index.md",
    layer: "interface",
  },
  {
    slug: "extension",
    title: "extension/",
    tagline: "Browser extension",
    description:
      "Manifest V3 helper extension adding a context-menu \"Save Image\" action. Service workers only — no persistent background pages — and sanitizes all inputs.",
    stack: ["Manifest V3", "Service Workers"],
    path: "/tutorials/web_integration",
    docSource: "docs/tutorials/web_integration.md",
    layer: "interface",
  },
  {
    slug: "cryptography",
    title: "cryptography/",
    tagline: "Kotlin security module",
    description:
      "Encrypts/decrypts .vault files with AES-256-GCM. Zero trace of sensitive data left in memory; backs VaultManager's credential storage across every interface.",
    stack: ["Kotlin", "AES-256-GCM"],
    path: "/ARCHITECTURE",
    docSource: "docs/ARCHITECTURE.md",
    layer: "security",
  },
  {
    slug: "data",
    title: "PostgreSQL + pgvector",
    tagline: "Data layer",
    description:
      "Unified schema for image metadata, group/image integrity via transactions, and semantic vector search via pgvector — the backbone every interface ultimately reads and writes through.",
    stack: ["PostgreSQL", "pgvector", "SQL"],
    path: "/database/unified_schema",
    docSource: "docs/database/unified_schema.md",
    layer: "data",
  },
];
