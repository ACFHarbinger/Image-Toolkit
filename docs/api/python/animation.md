# ASP / Animation Module API

The active ASP pipeline is maintained in the Anime-Stitch-Pipeline submodule.
Its source and generated reference are available from the
[ASP documentation portal](https://acfharbinger.github.io/Anime-Stitch-Pipeline/app/).

Image-Toolkit keeps its local stitch-feedback helpers in
`backend/src/animation/`. They are intentionally not rendered through
`mkdocstrings`: this namespace has no package initializer, so static API
collection would make the documentation build depend on runtime path setup.
