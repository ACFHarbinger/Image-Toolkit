# HIE IPC Service — Chat

Date: 2026-08-12

Added `IpcService` as a deterministic in-memory implementation behind the
versioned IPC envelopes. It supports `open_media`, `export_document`, and
`notify`, returns structured errors, and creates one-frame document records
without making filesystem or pixel-decoding decisions. Hosts can replace its
storage policy while preserving the request/response contract.
