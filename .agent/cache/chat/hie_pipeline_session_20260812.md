# HIE Pipeline Session — Chat

Date: 2026-08-12

Added `PipelineSession` to combine an active `DocumentHistory`, default HIE
capabilities, policy preview, and explicit proposal acceptance. The session
keeps preview side-effect free and records accepted proposals through undoable
history, giving PySide6/Tauri hosts one stateful orchestration boundary.
