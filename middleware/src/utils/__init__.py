"""Shared backend utility modules: `data/` (safetensors metadata),
`decorators/` (cross-cutting validation), and `display/` (slideshow daemons),
all used internally across the app.

Standalone CLI tools invoked only by justfiles/scripts live outside this
package as direct children of `middleware/`: `middleware/validation/`,
`middleware/docs/`, `middleware/scripts/`, `middleware/migrations/`.
"""
