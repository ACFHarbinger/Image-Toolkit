# P-01 Convert Pilot — Service Parity Audit (#894)

**Date:** 2026-10-23
**Agent:** Grok team (taking over from Kimi)

## Existing Convert service

`middleware/src/services/convert/` already provides:
- `ConvertService` implementing `ConvertServiceProtocol`
- `convert_single` / `convert_batch`
- Handlers and commands for single and batch conversion

## Qt Convert tab

The legacy PySide6 Convert tab lives in `gui/src/tabs/core/convert_tab.py` (Format / Codec / Sampler subtabs). `gui/src` is frozen for this pilot.

## Parity target for the pilot

The HostClient-driven `system.convert` view must cover the core single and batch conversion paths that the Qt tab exposes, using the existing service. Full visual parity of every subtab control is not required for the pilot success criterion (first Rust duplicate deleted + guide written).

## Residual

Any controls present in the Qt tab that are not yet exposed through the bridge contracts are noted here for later waves. The pilot focuses on proving the capability pattern end-to-end.

— Grok team
