# HIE IPC Contract — Chat

Date: 2026-08-12

Added versioned JSON-safe `IpcRequest` and `IpcResponse` contracts under
`middleware/src/hie_middleware/ipc.py`. They validate request IDs, protocol
version, supported host methods (`open_media`, `export_document`, `notify`),
and explicit error responses. Tauri documentation now references this shared
contract while leaving payload semantics host-owned.
