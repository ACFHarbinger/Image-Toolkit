# HIE Multi-Modal IPC — Chat

Date: 2026-08-12

Extended `IpcService.open_media` to support both still sources and explicit
multi-frame sequences. Sequence payloads validate frame sources, durations,
metadata, and FPS, preserving the HIE document model's image-as-one-frame
architecture while enabling video-ready transport.
