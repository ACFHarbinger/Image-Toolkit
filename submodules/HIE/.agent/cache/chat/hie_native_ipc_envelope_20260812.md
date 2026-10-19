# HIE Native IPC Envelope — Chat

Date: 2026-08-12

Aligned the Tauri Rust command bridge with the middleware IPC contract. Native
commands now accept request IDs and return versioned `IpcResponse` envelopes;
the TypeScript host checks error status before resolving operations. Media and
export commands report `available: false` until host-owned handlers are wired.
