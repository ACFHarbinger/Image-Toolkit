import contextlib
import multiprocessing
import os
import re
import subprocess
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict

import cv2
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips
from PySide6.QtCore import QObject, QRunnable, Signal


def run_extraction_in_process(config: Dict[str, Any]) -> Dict[str, Any]:  # noqa: C901
    def natural_sort_key(s):
        return [
            int(text) if text.isdigit() else text.lower()
            for text in re.split(r"(\d+)", s)
        ]

    t_type = config.get("type")
    video_path = config.get("video_path")
    start_ms = config.get("start_ms")
    end_ms = config.get("end_ms")
    output_dir = config.get("output_dir")
    target_resolution = config.get("target_resolution")
    cuts_ms = config.get("cuts_ms", [])
    frame_interval = config.get("frame_interval", 1)
    smart_extract = config.get("smart_extract", False)
    smart_method = config.get("smart_method", "")
    fps = config.get("fps", 24)
    mute_audio = config.get("mute_audio", False)
    use_ffmpeg = config.get("use_ffmpeg", True)
    speed = float(config.get("speed", "1.0"))

    def get_keep_regions(t_start: float, t_end: float):
        if not cuts_ms:
            return [(0.0, t_end - t_start)]
        sorted_cuts = sorted(
            [(max(t_start, c[0] / 1000.0), min(t_end, c[1] / 1000.0)) for c in cuts_ms]
        )
        merged_cuts = []
        for c in sorted_cuts:
            if c[0] >= c[1]:
                continue
            if not merged_cuts:
                merged_cuts.append(c)
            else:
                last = merged_cuts[-1]
                if c[0] <= last[1]:
                    merged_cuts[-1] = (last[0], max(last[1], c[1]))
                else:
                    merged_cuts.append(c)
        keep = []
        current = t_start
        for c_start, c_end in merged_cuts:
            if c_start > current:
                keep.append((current - t_start, c_start - t_start))
            current = max(current, c_end)
        if current < t_end:
            keep.append((current - t_start, t_end - t_start))
        return keep

    def get_video_fps(path):
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return 23.976
        f = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        return f if f > 0 else 23.976

    try:
        if t_type in ("range", "single"):
            video_name = Path(video_path).stem
            t_start = start_ms / 1000.0
            detected_fps = get_video_fps(video_path)

            if smart_extract:
                t_end = end_ms / 1000.0
                duration = t_end - t_start
                cmd = ["ffmpeg", "-y", "-ss", str(t_start)]
                if t_type == "range" and end_ms != -1:
                    cmd.extend(["-t", str(duration)])
                cmd.extend(["-i", video_path])

                filters = []
                keep_regions = get_keep_regions(t_start, t_end)
                if cuts_ms and keep_regions:
                    select_expr = "+".join(
                        [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                    )
                    filters.append(f"select='{select_expr}'")
                if frame_interval > 1:
                    filters.append(f"select='not(mod(n,{frame_interval}))'")
                if "mpdecimate" in smart_method:
                    filters.append("mpdecimate")
                elif "scene" in smart_method:
                    match = re.search(r"\((.*?)\)", smart_method)
                    val = match.group(1) if match else "0.4"
                    filters.append(f"select='gt(scene,{val})'")
                if target_resolution:
                    w, h = target_resolution
                    filters.append(f"scale={w}:{h}:flags=lanczos")
                if filters:
                    cmd.extend(["-vf", ",".join(filters)])
                if t_type == "single":
                    cmd.extend(["-vframes", "1"])
                cmd.extend(
                    [
                        "-sws_flags",
                        "spline+accurate_rnd+full_chroma_int",
                        "-pix_fmt",
                        "rgb48be",
                        "-vsync",
                        "vfr",
                        "-frame_pts",
                        "1",
                    ]
                )

                temp_id = int(time.time() * 1000) % 100000
                out_pattern = os.path.join(
                    output_dir, f"{video_name}_smart_tmp_{temp_id}_%08d.png"
                )
                cmd.append(out_pattern)

                subprocess.run(
                    cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

                prefix = f"{video_name}_smart_tmp_{temp_id}_"
                tmp_files = sorted(
                    [
                        f
                        for f in os.listdir(output_dir)
                        if f.startswith(prefix) and f.endswith(".png")
                    ],
                    key=natural_sort_key,
                )

                saved_files = []
                for f in tmp_files:
                    match = re.search(r"_(\d+)\.png$", f)
                    if not match:
                        continue
                    pts = int(match.group(1))
                    current_ms = start_ms + int(pts * 1000.0 / detected_fps)
                    new_name = f"{video_name}_smart_{current_ms}ms.png"
                    final_path = os.path.join(output_dir, new_name)
                    if os.path.exists(final_path):
                        final_path = os.path.join(
                            output_dir,
                            f"{video_name}_smart_{current_ms}ms_{temp_id}.png",
                        )
                    os.rename(os.path.join(output_dir, f), final_path)
                    saved_files.append(final_path)
                return {"status": "success", "saved_files": saved_files}
            else:
                cmd = ["ffmpeg", "-y", "-ss", str(t_start)]
                if t_type == "range" and end_ms != -1:
                    duration = (end_ms - start_ms) / 1000.0
                    cmd.extend(["-t", str(duration)])
                cmd.extend(["-i", video_path])

                filters = []
                if cuts_ms:
                    keep_regions = get_keep_regions(
                        t_start, (end_ms / 1000.0 if end_ms != -1 else t_start + 1)
                    )
                    if keep_regions:
                        select_expr = "+".join(
                            [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                        )
                        filters.append(f"select='{select_expr}'")
                if frame_interval > 1:
                    filters.append(f"select='not(mod(n,{frame_interval}))'")
                if target_resolution:
                    w, h = target_resolution
                    filters.append(f"scale={w}:{h}:flags=lanczos")
                if filters:
                    cmd.extend(["-vf", ",".join(filters)])
                if t_type == "single":
                    cmd.extend(["-vframes", "1"])
                cmd.extend(
                    [
                        "-sws_flags",
                        "spline+accurate_rnd+full_chroma_int",
                        "-vsync",
                        "vfr",
                        "-q:v",
                        "2",
                    ]
                )

                out_pattern = os.path.join(output_dir, f"{video_name}_tmp_%05d.png")
                cmd.append(out_pattern)

                subprocess.run(
                    cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

                tmp_files = sorted(
                    [
                        f
                        for f in os.listdir(output_dir)
                        if f.startswith(f"{video_name}_tmp_") and f.endswith(".png")
                    ],
                    key=natural_sort_key,
                )
                saved_files = []
                for i, f in enumerate(tmp_files):
                    current_ms = start_ms + int(
                        i * frame_interval * (1000.0 / detected_fps)
                    )
                    new_name = f"{video_name}_{current_ms}ms.png"
                    final_path = os.path.join(output_dir, new_name)
                    if os.path.exists(final_path):
                        final_path = os.path.join(
                            output_dir, f"{video_name}_{current_ms}ms_{i}.png"
                        )
                    os.rename(os.path.join(output_dir, f), final_path)
                    saved_files.append(final_path)
                return {"status": "success", "saved_files": saved_files}

        elif t_type == "gif":
            t_start = start_ms / 1000.0
            t_end = end_ms / 1000.0
            output_path = os.path.join(
                output_dir,
                f"{Path(video_path).stem}_{int(start_ms)}ms_{int(end_ms)}ms.gif",
            )

            if use_ffmpeg:
                duration = t_end - t_start
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(t_start),
                    "-t",
                    str(duration),
                    "-i",
                    video_path,
                ]

                filter_chain = []
                keep_regions = get_keep_regions(t_start, t_end)
                if cuts_ms and keep_regions:
                    select_expr = "+".join(
                        [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                    )
                    filter_chain.append(f"select='{select_expr}'")
                    filter_chain.append("setpts=N/FRAME_RATE/TB")
                filter_chain.append(f"fps={fps}")
                if target_resolution:
                    w, h = target_resolution
                    filter_chain.append(f"scale={w}:{h}:flags=lanczos")
                if speed != 1.0:
                    pts_mult = 1.0 / speed
                    filter_chain.append(f"setpts={pts_mult}*PTS")

                base_filters = ",".join(filter_chain)
                complex_filter = (
                    f"{base_filters},split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
                )
                cmd.extend(["-vf", complex_filter])
                cmd.append(output_path)

                subprocess.run(
                    cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                return {"status": "success", "output_path": output_path}
            else:
                base_clip = VideoFileClip(video_path).subclip(t_start, t_end)
                keep_regions = get_keep_regions(t_start, t_end)
                if cuts_ms and keep_regions:
                    clips = []
                    for start_sec, end_sec in keep_regions:
                        if end_sec > start_sec:
                            clips.append(base_clip.subclip(start_sec, end_sec))
                    clip = concatenate_videoclips(clips) if clips else base_clip
                else:
                    clip = base_clip
                if target_resolution:
                    clip = clip.resize(newsize=target_resolution)
                if speed != 1.0:
                    clip = clip.speedx(speed)
                clip.write_gif(output_path, fps=fps, logger=None)
                clip.close()
                base_clip.close()
                return {"status": "success", "output_path": output_path}

        elif t_type == "video":
            t_start = start_ms / 1000.0
            t_end = end_ms / 1000.0
            output_path = os.path.join(
                output_dir,
                f"{Path(video_path).stem}_{int(start_ms)}ms_{int(end_ms)}ms.mp4",
            )

            if use_ffmpeg:
                keep_regions = get_keep_regions(t_start, t_end)
                if cuts_ms and keep_regions:
                    kept_duration = sum(r[1] - r[0] for r in keep_regions)
                    if kept_duration <= 0:
                        kept_duration = t_end - t_start
                else:
                    kept_duration = t_end - t_start
                duration = kept_duration / speed

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(t_start),
                    "-t",
                    str(t_end - t_start),
                    "-i",
                    video_path,
                ]
                filters = []
                if cuts_ms and keep_regions:
                    select_expr = "+".join(
                        [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                    )
                    filters.append(f"select='{select_expr}'")
                    filters.append("setpts=N/FRAME_RATE/TB")
                if target_resolution:
                    w, h = target_resolution
                    filters.append(f"scale={w}:{h}")
                if speed != 1.0:
                    pts_mult = 1.0 / speed
                    filters.append(f"setpts={pts_mult}*PTS")
                if filters:
                    cmd.extend(["-vf", ",".join(filters)])

                cmd.extend(["-c:v", "libx264", "-movflags", "+faststart"])
                if mute_audio:
                    cmd.append("-an")
                else:
                    audio_filters = []
                    if cuts_ms and keep_regions:
                        aselect_expr = "+".join(
                            [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                        )
                        audio_filters.append(f"aselect='{aselect_expr}'")
                        audio_filters.append("asetpts=N/SR/TB")
                    if speed != 1.0:
                        s = speed
                        while s > 2.0:
                            audio_filters.append("atempo=2.0")
                            s /= 2.0
                        while s < 0.5:
                            audio_filters.append("atempo=0.5")
                            s /= 0.5
                        audio_filters.append(f"atempo={s}")
                    if audio_filters:
                        cmd.extend(["-af", ",".join(audio_filters)])
                    cmd.extend(["-c:a", "aac", "-b:a", "128k"])

                cmd.extend(["-t", str(duration), "-shortest", output_path])
                subprocess.run(
                    cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                return {"status": "success", "output_path": output_path}
            else:
                base_clip = VideoFileClip(video_path)
                original_audio_clip = None
                if mute_audio or base_clip.audio is None:
                    base_clip.audio = None
                    audio_codec = None
                else:
                    try:
                        original_audio_clip = AudioFileClip(video_path)
                        base_clip.audio = original_audio_clip
                    except Exception:
                        pass
                    audio_codec = "aac"

                subclipped_base = base_clip.subclip(t_start, t_end)
                keep_regions = get_keep_regions(t_start, t_end)
                if cuts_ms and keep_regions:
                    clips = []
                    for start_sec, end_sec in keep_regions:
                        if end_sec > start_sec:
                            clips.append(subclipped_base.subclip(start_sec, end_sec))
                    clip = concatenate_videoclips(clips) if clips else subclipped_base
                else:
                    clip = subclipped_base

                if target_resolution:
                    clip = clip.resize(newsize=target_resolution)
                if speed != 1.0:
                    clip = clip.speedx(speed)
                if clip.duration is not None and clip.audio is not None:
                    clip.audio = clip.audio.set_duration(clip.duration)

                ffmpeg_params = ["-movflags", "faststart"]
                if audio_codec is not None:
                    ffmpeg_params.extend(["-b:a", "128k"])

                temp_audio_path = f"temp-audio-{int(time.time() * 1000)}.m4a"
                clip.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec=audio_codec,
                    temp_audiofile=temp_audio_path,
                    remove_temp=True,
                    ffmpeg_params=ffmpeg_params,
                    verbose=False,
                    logger=None,
                )
                if original_audio_clip:
                    original_audio_clip.close()
                clip.close()
                base_clip.close()
                if os.path.exists(temp_audio_path):
                    with contextlib.suppress(OSError):
                        os.remove(temp_audio_path)
                return {"status": "success", "output_path": output_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class _QueueWorkerSignals(QObject):
    started = Signal()
    progress = Signal(int)
    item_completed = Signal(int, dict)
    finished = Signal(list)
    error = Signal(str)


class QueueExecutionWorker(QRunnable):
    def __init__(self, queue_items: list, parallel: bool = False):
        super().__init__()
        self.queue_items = queue_items
        self.parallel = parallel
        self.signals = _QueueWorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        self.signals.started.emit()
        results = []

        if self.parallel:
            num_cores = min(multiprocessing.cpu_count(), len(self.queue_items))
            if num_cores < 1:
                num_cores = 1

            self.signals.progress.emit(10)
            try:
                with Pool(processes=num_cores) as pool:
                    async_results = [
                        pool.apply_async(run_extraction_in_process, (item,))
                        for item in self.queue_items
                    ]

                    completed = 0
                    total = len(self.queue_items)

                    while completed < total:
                        if self._is_cancelled:
                            pool.terminate()
                            self.signals.error.emit(
                                "Parallel queue extraction cancelled by user."
                            )
                            return

                        new_completed = 0
                        for r in async_results:
                            if r.ready():
                                new_completed += 1

                        if new_completed > completed:
                            completed = new_completed
                            progress_val = int(10 + (completed / total) * 90)
                            self.signals.progress.emit(min(99, progress_val))

                        time.sleep(0.5)

                    for i, r in enumerate(async_results):
                        res = r.get()
                        results.append(res)
                        self.signals.item_completed.emit(i, res)
            except Exception as e:
                self.signals.error.emit(f"Parallel processing error: {e}")
                return
        else:
            total = len(self.queue_items)
            for i, item in enumerate(self.queue_items):
                if self._is_cancelled:
                    self.signals.error.emit(
                        "Sequential queue extraction cancelled by user."
                    )
                    return

                self.signals.progress.emit(int((i / total) * 100))
                res = run_extraction_in_process(item)
                results.append(res)
                self.signals.item_completed.emit(i, res)

        self.signals.progress.emit(100)
        self.signals.finished.emit(results)
