import os
import subprocess
from typing import Callable, Optional

# Target codec -> (ffmpeg encoder, extra fixed args). Keys match the codec
# names ffprobe reports for these encoders (h264, hevc, av1, vp9), so a
# probed source codec can be compared directly against a target key.
VIDEO_CODEC_ENCODERS = {
    "h264": ("libx264", ["-pix_fmt", "yuv420p"]),
    "hevc": ("libx265", ["-pix_fmt", "yuv420p", "-tag:v", "hvc1"]),
    "av1": ("libsvtav1", ["-pix_fmt", "yuv420p"]),
    "vp9": ("libvpx-vp9", ["-pix_fmt", "yuv420p", "-b:v", "0"]),
}

AUDIO_CODEC_ENCODERS = {
    "aac": ("aac", ["-b:a", "192k"]),
    "opus": ("libopus", ["-b:a", "128k"]),
    "mp3": ("libmp3lame", ["-q:a", "2"]),
    "flac": ("flac", []),
}

# Speed level 0 (fastest/lowest quality) .. 4 (slowest/best quality), mapped
# to each encoder's own preset vocabulary.
_SPEED_PRESETS = {
    "h264": {0: "ultrafast", 1: "faster", 2: "medium", 3: "slow", 4: "veryslow"},
    "hevc": {0: "ultrafast", 1: "faster", 2: "medium", 3: "slow", 4: "veryslow"},
    # libsvtav1: lower preset number = slower/better.
    "av1": {0: "12", 1: "10", 2: "8", 3: "5", 4: "2"},
    # libvpx-vp9: lower -cpu-used = slower/better.
    "vp9": {0: "8", 1: "6", 2: "4", 3: "2", 4: "0"},
}

_MAX_CRF = {"h264": 51, "hevc": 51, "av1": 63, "vp9": 63}


class VideoFormatConverter:
    """
    Utilities for converting video formats using FFmpeg (via subprocess).
    """

    @classmethod
    def convert_video(
        cls,
        input_path: str,
        output_path: str,
        delete: bool = False,
        process_callback: Optional[Callable[[subprocess.Popen], None]] = None,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
        aspect_ratio: Optional[float] = None,
        ar_mode: str = "crop",
    ) -> bool:
        """
        Converts a video file using FFmpeg via subprocess.
        Allows for safe cancellation via process_callback.
        Supports aspect ratio resizing (crop/pad/stretch).
        """
        if not os.path.exists(input_path):
            print(f"Error: Input file '{input_path}' not found.")
            return False

        print(
            f"Converting '{os.path.basename(input_path)}' to '{os.path.basename(output_path)}' using Native Backend (ffmpeg)..."
        )

        cmd = [
            "ffmpeg",
            "-y",  # Overwrite
            "-i",
            input_path,
        ]



        filters = []

        # Heuristic: If target dimensions are tiny (e.g. 16x9), assume they are Ratio info passed as dimensions by mistake
        # and ignore them if we have explicit aspect_ratio logic coming in, or just ignore them anyway.
        valid_scaling = False
        if target_width and target_height and target_width > 128 and target_height > 128:
            valid_scaling = True

        if aspect_ratio:
            # Use crop or pad
            # We need to use valid FFmpeg expressions.
            # a = iw / ih
            # If ar_mode == 'crop':
            #   if (a > AR) -> width is too big, crop width -> new_w = ih * AR
            #   else        -> height is too big, crop height -> new_h = iw / AR
            ar = float(aspect_ratio)

            if "pad" in str(ar_mode).lower():
                # Pad logic:
                # If image is too wide (a > AR), we need to pad height.
                # If image is too tall (a < AR), we need to pad width.
                # However, the standard pad filter logic is:
                # ow = max(iw, ih*AR)
                # oh = max(ih, iw/AR)
                # This ensures the output bounding box covers the target aspect ratio while containing the input.
                filters.append(f"pad='max(iw,ih*{ar})':'max(ih,iw/{ar})':(ow-iw)/2:(oh-ih)/2:black")
            elif "stretch" in str(ar_mode).lower():
                # Stretch logic:
                # Resize to target aspect ratio.
                # To avoid upscaling artifacts on width, we keep width constant and adjust height?
                # Or we can just blindly scale to match AR.
                # Let's keep input width and calculate height = width / AR.
                # trunc(iw/AR/2)*2 ensures even height (needed for yuv420p).
                # setsar=1 ensures players treat pixels as square.
                filters.append(f"scale=iw:trunc(iw/{ar}/2)*2,setsar=1")
            else:
                # Crop logic (default)
                # if a > AR (too wide), crop to ih*AR
                # if a < AR (too tall), crop to iw/AR
                # crop=w:h:x:y
                filters.append(f"crop='if(gt(a,{ar}),ih*{ar},iw)':'if(gt(a,{ar}),ih,iw/{ar})':(iw-ow)/2:(ih-oh)/2")

        elif valid_scaling:
             # Only scale if no aspect ratio custom logic and dimensions look real
            filters.append(f"scale={target_width}:{target_height}")

        if filters:
            cmd.extend(["-vf", ",".join(filters)])

        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-crf",
                "23",
                "-preset",
                "medium",
                "-c:a",
                "aac",
                output_path,
            ]
        )

        process = None
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if process_callback:
                process_callback(process)

            process.wait()
            success = process.returncode == 0

            if success and delete:
                try:
                    os.remove(input_path)
                except Exception as e:
                    print(f"Failed to delete original file: {e}")

            return success

        except Exception as e:
            print(f"Error converting video: {e}")
            return False
        finally:
            pass  # Popen object cleanup is handled by GC or explicit termination externally

    @classmethod
    def convert_codec(
        cls,
        input_path: str,
        output_path: str,
        video_codec: Optional[str] = None,
        audio_codec: Optional[str] = None,
        crf: int = 28,
        speed: int = 2,
        delete: bool = False,
        process_callback: Optional[Callable[[subprocess.Popen], None]] = None,
    ) -> bool:
        """
        Re-encodes a video's video and/or audio stream to a different codec via
        FFmpeg, leaving the other stream (and container) untouched. Passing
        ``None`` (or "copy") for either codec stream-copies it unchanged.

        ``speed`` is a generic 0 (fastest) .. 4 (best quality) dial, mapped
        internally to each target encoder's own preset vocabulary since x264/
        x265, libsvtav1, and libvpx-vp9 all use different scales.
        """
        if not os.path.exists(input_path):
            print(f"Error: Input file '{input_path}' not found.")
            return False

        cmd = ["ffmpeg", "-y", "-i", input_path]

        vcodec_key = (video_codec or "copy").strip().lower()
        if vcodec_key in ("copy", "", "none"):
            cmd += ["-c:v", "copy"]
        else:
            encoder = VIDEO_CODEC_ENCODERS.get(vcodec_key)
            if encoder is None:
                print(f"Unsupported video codec: {video_codec}")
                return False
            encoder_name, extra_args = encoder
            clamped_crf = max(0, min(crf, _MAX_CRF.get(vcodec_key, 51)))
            speed_val = _SPEED_PRESETS.get(vcodec_key, {}).get(speed, "medium")

            cmd += ["-c:v", encoder_name, "-crf", str(clamped_crf)]
            if vcodec_key == "vp9":
                cmd += ["-deadline", "good", "-cpu-used", str(speed_val)]
            else:
                cmd += ["-preset", str(speed_val)]
            cmd += extra_args

        acodec_key = (audio_codec or "copy").strip().lower()
        if acodec_key in ("copy", "", "none"):
            cmd += ["-c:a", "copy"]
        else:
            audio_encoder = AUDIO_CODEC_ENCODERS.get(acodec_key)
            if audio_encoder is None:
                print(f"Unsupported audio codec: {audio_codec}")
                return False
            encoder_name, extra_args = audio_encoder
            cmd += ["-c:a", encoder_name, *extra_args]

        cmd.append(output_path)

        print(
            f"Re-encoding '{os.path.basename(input_path)}' "
            f"(video={vcodec_key}, audio={acodec_key}) -> '{os.path.basename(output_path)}'..."
        )

        process = None
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if process_callback:
                process_callback(process)

            process.wait()
            success = process.returncode == 0

            if success and delete:
                try:
                    os.remove(input_path)
                except Exception as e:
                    print(f"Failed to delete original file: {e}")

            return success

        except Exception as e:
            print(f"Error re-encoding video codec: {e}")
            return False

    @classmethod
    def convert_to_gif(
        cls,
        input_path: str,
        output_path: str,
        delete: bool = False,
        process_callback: Optional[Callable[[subprocess.Popen], None]] = None,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
        fps: int = 15,
    ) -> bool:
        """
        Converts a video to a high-quality GIF using FFmpeg's palettegen/paletteuse filters.
        """
        if not os.path.exists(input_path):
            print(f"Error: Input file '{input_path}' not found.")
            return False

        print(
            f"Converting '{os.path.basename(input_path)}' to GIF '{os.path.basename(output_path)}'..."
        )

        # Base filter: fps control
        # We can also add scaling here
        filter_str = f"fps={fps}"

        if target_width and target_height:
            # Scale if requested
            filter_str += f",scale={target_width}:{target_height}:flags=lanczos"
        else:
            # Default scaling to something reasonable if source is huge?
            # For now, keep original resolution or let user define.
            # But we enable lanczos scaling for quality if scaling happens elsewhere.
            pass

        # Complex filter for high quality GIF:
        # [0:v] split [a][b];[a] palettegen [p];[b][p] paletteuse
        # We prepend our fps/scale filters to the stream before splitting.
        complex_filter = f"[0:v]{filter_str},split[a][b];[a]palettegen[p];[b][p]paletteuse"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-filter_complex",
            complex_filter,
            output_path,
        ]

        process = None
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if process_callback:
                process_callback(process)

            process.wait()
            success = process.returncode == 0

            if success:
                if delete:
                    try:
                        os.remove(input_path)
                    except Exception as e:
                        print(f"Failed to delete original file: {e}")
            else:
                 print("FFmpeg returned non-zero exit code for GIF conversion.")

            return success

        except Exception as e:
            print(f"Error converting video to GIF: {e}")
            return False
