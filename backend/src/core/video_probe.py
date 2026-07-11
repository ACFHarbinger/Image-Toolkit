import subprocess
from typing import Optional, Tuple


def probe_codecs(video_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Returns (video_codec, audio_codec) for the first video/audio stream, via a single ffprobe call."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name,codec_type",
                "-of",
                "csv=p=0",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode != 0:
            return None, None

        video_codec: Optional[str] = None
        audio_codec: Optional[str] = None
        for line in result.stdout.strip().splitlines():
            parts = [p.strip().lower() for p in line.split(",")]
            if len(parts) != 2:
                continue
            codec_name, codec_type = parts
            if codec_type == "video" and video_codec is None:
                video_codec = codec_name or None
            elif codec_type == "audio" and audio_codec is None:
                audio_codec = codec_name or None
        return video_codec, audio_codec
    except (OSError, subprocess.TimeoutExpired):
        return None, None


def probe_video_codec(video_path: str) -> Optional[str]:
    return probe_codecs(video_path)[0]


def probe_audio_codec(video_path: str) -> Optional[str]:
    return probe_codecs(video_path)[1]
