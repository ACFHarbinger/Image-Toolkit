# HIE session restoration dispatch — 2026-08-12

Extended `PipelineSession` with an injectable `RestorationPipeline` and
`submit_restoration()` method. Frontends can now submit cancellable deblur or
masked-inpainting previews through the same stateful session boundary used for
policy proposals, while hosts/tests can inject a fake dispatcher. Updated the
Phase 3.11 roadmap, changelog, and session tests. Grok's model work and
Claude's brush environment were not modified.
