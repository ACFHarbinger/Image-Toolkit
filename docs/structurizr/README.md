# Structurizr C4 models

Image-Toolkit keeps the absorbed projects' architecture models as Structurizr DSL.

| Project | Workspace |
| --- | --- |
| Cel-Shaded Generator | [cel/workspace.dsl](cel/workspace.dsl) |
| Hybrid Image Editor | [editor/workspace.dsl](editor/workspace.dsl) |

Rendering uses the Structurizr Lite and Structurizr CLI images. Java 17 or Docker is required. Neither image is a Python package, so the docs group records that requirement beside the Sphinx packages and does not pin a stand-in library.

Preview one workspace with Structurizr Lite:

```bash
docker run -it --rm -p 8080:8080 \
  -v "$(pwd)/docs/structurizr/cel:/usr/local/structurizr" \
  structurizr/lite
```

Open <http://localhost:8080>. Swap `cel` for `editor` to view the other model.

Export Mermaid with the CLI image:

```bash
docker run --rm -v "$(pwd)/docs/structurizr:/usr/local/structurizr" \
  structurizr/cli export \
  -workspace cel/workspace.dsl \
  -format mermaid \
  -output cel/diagrams
```

A local install is `structurizr-cli` from the [Structurizr CLI releases](https://github.com/structurizr/cli/releases), also on Java 17.
