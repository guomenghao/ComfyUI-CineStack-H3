"""Assemble saved video ranges with bounded FFmpeg buffers, never IMAGE tensors."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import wave

from .video_export import _ffmpeg_bin


def _run(command):
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace")[-2000:])


def compose_ranges(clips, destination, fps):
    """Decode/re-encode one saved range at a time; concatenate video by stream copy.

    PCM is streamed in small blocks into one WAV and encoded once. Sample counts
    use the cumulative frame timeline, avoiding per-clip AAC priming/drift.
    """
    destination = Path(destination)
    width, height = max(c["width"] for c in clips), max(c["height"] for c in clips)
    ffmpeg = _ffmpeg_bin()
    total = sum(c["frames"] for c in clips)
    has_audio = any(c.get("audio", False) for c in clips)
    # Adjacent ranges from the same immutable video can be read in one pass.
    grouped = []
    for clip in clips:
        if (grouped and all(grouped[-1].get(k) == clip.get(k) for k in ("path", "width", "height", "audio"))
                and grouped[-1]["start_frame"] + grouped[-1]["frames"] == clip["start_frame"]):
            grouped[-1]["frames"] += clip["frames"]
        else:
            grouped.append(dict(clip))
    with tempfile.TemporaryDirectory(prefix=".rolling_merge_", dir=destination.parent) as temporary:
        root = Path(temporary)
        wav_path = root / "timeline.wav"
        wav = wave.open(str(wav_path), "wb") if has_audio else None
        if wav:
            wav.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
        paths, frame_cursor, sample_cursor = [], 0, 0
        try:
            for index, clip in enumerate(grouped):
                start = clip["start_frame"] / fps
                duration = clip["frames"] / fps
                source = ["-ss", f"{start:.12f}", "-i", str(clip["path"])]
                path = root / f"{index:05d}.mp4"
                # FrameStream's Matroska timestamps have millisecond precision.
                # Time seeking at a rounded boundary can drop a frame; trim by
                # decoded frame index instead. FFmpeg buffers stay bounded.
                trim = f"trim=start_frame={clip['start_frame']}:end_frame={clip['start_frame'] + clip['frames']},setpts=PTS-STARTPTS"
                _run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(clip["path"]),
                      "-map", "0:v:0", "-an", "-vf", trim + f",pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
                      "-r", str(fps), "-frames:v", str(clip["frames"]), "-c:v", "libx264",
                      "-threads", "2", "-filter_threads", "1", "-pix_fmt", "yuv420p",
                      "-preset", "veryfast", "-crf", "18", str(path)])
                # Verify the saved range really contains the promised frame count.
                # Decoding remains in FFmpeg; stdout only contains progress fields.
                result = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-map", "0:v:0",
                    "-progress", "pipe:1", "-f", "null", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                counts = [int(line.split("=", 1)[1]) for line in result.stdout.decode().splitlines()
                          if line.startswith("frame=")]
                if result.returncode or not counts or counts[-1] != clip["frames"]:
                    raise RuntimeError(f"第 {clip['segment']} 段已有视频帧数不足或损坏，未补跑生成。")
                paths.append(path)
                frame_cursor += clip["frames"]
                target = round(frame_cursor / fps * 48000)
                remaining = (target - sample_cursor) * 4
                sample_cursor = target
                if wav and clip.get("audio", False):
                    with (root / "audio.log").open("w+b") as errors:
                        proc = subprocess.Popen([ffmpeg, "-v", "error", *source, "-map", "0:a:0", "-vn",
                            "-t", f"{duration:.12f}", "-ar", "48000", "-ac", "2", "-f", "s16le", "pipe:1"],
                            stdout=subprocess.PIPE, stderr=errors)
                        try:
                            while True:
                                block = proc.stdout.read(65536)
                                if not block:
                                    break
                                take = min(remaining, len(block))
                                wav.writeframesraw(block[:take])
                                remaining -= take
                            if proc.wait():
                                errors.seek(0)
                                raise RuntimeError(errors.read().decode(errors="replace")[-2000:])
                        finally:
                            proc.stdout.close()
                            if proc.poll() is None:
                                proc.kill()
                                proc.wait()
                if wav:
                    while remaining:
                        take = min(remaining, 65536)
                        wav.writeframesraw(b"\0" * take)
                        remaining -= take
        finally:
            if wav:
                wav.close()
        listing = root / "concat.txt"
        # Generated filenames only: no user paths in concat syntax (Windows-safe).
        listing.write_text("".join(f"file '{p.name}'\n" for p in paths), encoding="utf-8")
        merged = root / "timeline.mp4"
        command = [ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing)]
        if has_audio:
            command += ["-i", str(wav_path)]
        command += ["-map", "0:v:0", "-c:v", "copy"]
        command += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k"] if has_audio else ["-an"]
        command += ["-t", f"{total / fps:.12f}", "-movflags", "+faststart", str(merged)]
        _run(command)
        os.replace(merged, destination)
