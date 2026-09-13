"""Codec/speed option maps and source-codec filter-button lists.

Extracted from ``codec_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

# Target codec label -> internal key. "copy" means "leave this stream alone".
VIDEO_CODEC_OPTIONS = {
    "Keep Original (No Re-encode)": "copy",
    "H.264": "h264",
    "H.265 / HEVC": "hevc",
    "AV1": "av1",
    "VP9": "vp9",
}
AUDIO_CODEC_OPTIONS = {
    "Keep Original (No Re-encode)": "copy",
    "AAC": "aac",
    "Opus": "opus",
    "MP3": "mp3",
    "FLAC": "flac",
}
SPEED_OPTIONS = {
    "Fastest": 0,
    "Fast": 1,
    "Balanced": 2,
    "Slow": 3,
    "Best Quality": 4,
}

# Common codecs offered as source-filter toggle buttons. Not exhaustive --
# any file whose probed codec isn't in the active filter set is simply
# excluded, so obscure codecs are still handled correctly, just without a
# dedicated button.
COMMON_SOURCE_VIDEO_CODECS = [
    "h264",
    "hevc",
    "vp9",
    "av1",
    "mpeg4",
    "mpeg2video",
    "vc1",
    "prores",
]
COMMON_SOURCE_AUDIO_CODECS = [
    "aac",
    "mp3",
    "ac3",
    "dts",
    "opus",
    "flac",
    "vorbis",
    "pcm_s16le",
]

__all__ = [
    "VIDEO_CODEC_OPTIONS",
    "AUDIO_CODEC_OPTIONS",
    "SPEED_OPTIONS",
    "COMMON_SOURCE_VIDEO_CODECS",
    "COMMON_SOURCE_AUDIO_CODECS",
]
