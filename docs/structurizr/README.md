# Structurizr C4 Model — Image Toolkit

This directory contains the [Structurizr DSL](https://structurizr.com/help/dsl) C4 architecture model for Image Toolkit.

## Levels modelled

| Level | View name | Description |
|-------|-----------|-------------|
| 1 — System Context | `SystemContext` | Image Toolkit vs. external users and systems |
| 2 — Containers | `Containers` | All independently deployable units |
| 3 — Components (Python Backend) | `PythonBackendComponents` | ASP Pipeline, ML Models, VaultManager, ImageDB |
| 3 — Components (Rust Core) | `RustCoreComponents` | Math Backbone, Image Processing, Web Crawlers, FS Scanner |
| 3 — Components (Django API) | `DjangoApiComponents` | DRF Views, Celery Workers, OpenAPI Endpoints |

## Rendering locally with Structurizr Lite

```bash
docker run -it --rm -p 8080:8080 \
  -v "$(pwd)/docs/structurizr:/usr/local/structurizr" \
  structurizr/lite
```

Then open <http://localhost:8080>. The DSL is reloaded automatically on file save.

## Exporting to Mermaid / PlantUML

Install the [Structurizr CLI](https://github.com/structurizr/cli/releases):

```bash
# Export all views as Mermaid diagrams
structurizr-cli export \
  -workspace docs/structurizr/workspace.dsl \
  -format mermaid \
  -output docs/structurizr/diagrams/

# Export as PlantUML
structurizr-cli export \
  -workspace docs/structurizr/workspace.dsl \
  -format plantuml \
  -output docs/structurizr/diagrams/
```

Exported `.mmd` files can be embedded directly in MkDocs pages using the Mermaid superfences extension:

````markdown
```mermaid
<paste content of diagrams/SystemContext.mmd here>
```
````

## Editing the model

The model lives entirely in [`workspace.dsl`](workspace.dsl). Key concepts:

- **People** — actors who interact with the system (lines with `= person`)
- **Software Systems** — external dependencies (marked `"External"` in styles)
- **Containers** — deployable units within Image Toolkit
- **Components** — internal modules within each container
- **Relationships** — `source -> destination "description"` lines in the `model {}` block
- **Views** — which elements to include in each diagram (`container`, `component`, `systemContext` blocks in `views {}`)

The C4 Model specification: <https://c4model.com>
