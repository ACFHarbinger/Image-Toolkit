import os
import subprocess
from typing import Optional, Callable


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
        if target_width and target_height:
            if target_width > 128 and target_height > 128:
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
