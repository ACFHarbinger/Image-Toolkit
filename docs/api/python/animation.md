# ASP / Animation Module API

The ASP pipeline documentation is part of these docs
([ASP home](../../guides/stitching.md)). The former standalone portal remains at
<https://acfharbinger.github.io/Anime-Stitch-Pipeline/app/>.

Image-Toolkit keeps its local stitch-feedback helpers in
`middleware/src/animation/`. They are intentionally not rendered through
`mkdocstrings`: this namespace has no package initializer, so static API
collection would make the documentation build depend on runtime path setup.
