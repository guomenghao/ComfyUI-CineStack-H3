"""Disk-backed video delivery. Keep paths/metadata here, never IMAGE tensors."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile

from ..lib.video_export import _ffmpeg_bin
from .segment_mp4_export import VIDEO_EXPORT_TASKS, segment_mp4_path
from .segment_seed import resolve_segment_seed

log = logging.getLogger("ComfyUI-CineStack-H3.director.memory")


def validate_low_memory(plan, node_id):
    if not node_id:
        raise ValueError("低内存落盘需要有效的节点缓存标识。")
    if any(seg.task_key not in VIDEO_EXPORT_TASKS for seg in plan.segments):
        raise ValueError("低内存落盘仅支持视频片段；图片任务请关闭该开关。")
    if not _ffmpeg_bin():
        raise RuntimeError("低内存落盘需要 FFmpeg；请安装 imageio-ffmpeg 或系统 FFmpeg。未开始采样。")


def ram_snapshot():
    """Current process RSS, not a never-decreasing high-water mark or page cache."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except OSError:
        pass
    try:
        import psutil
    except ImportError:
        return None
    try:
        return psutil.Process().memory_info().rss
    except (psutil.Error, OSError):
        return None


def _run(command):
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-2000:])


def _has_audio(path):
    # Header inspection only: no output, no decoding, ffprobe is not required.
    result = subprocess.run([_ffmpeg_bin(), "-hide_banner", "-i", str(path)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return b"Audio:" in result.stderr


def _publish_copy(source, dest):
    import shutil
    with tempfile.TemporaryDirectory(prefix=".cinestack_copy_", dir=dest.parent) as temporary:
        staging = Path(temporary) / "clip.mp4"
        shutil.copy2(source, staging)
        os.replace(staging, dest)


def merge_disk_clips(clips, dest, fps):
    """Normalize at most one file at a time, then concatenate using FFmpeg buffers."""
    dest = Path(dest)
    if len(clips) == 1:
        _publish_copy(Path(clips[0]["path"]), dest)
        return
    width = max(c["width"] for c in clips)
    height = max(c["height"] for c in clips)
    ffmpeg = _ffmpeg_bin()
    audio_flags = [_has_audio(c["path"]) for c in clips]
    audio = any(audio_flags)
    with tempfile.TemporaryDirectory(prefix=".cinestack_merge_", dir=dest.parent) as temporary:
        root = Path(temporary)
        paths = []
        for index, (clip, has_audio) in enumerate(zip(clips, audio_flags)):
            path = Path(clip["path"])
            duration = clip["frames"] / fps
            if clip["width"] != width or clip["height"] != height or has_audio != audio:
                normalized = root / f"{index:04d}.mp4"
                command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-filter_threads", "1", "-i", str(path)]
                if audio and not has_audio:
                    command += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                command += ["-map", "0:v:0"]
                if audio:
                    command += ["-map", "0:a:0" if has_audio else "1:a:0", "-af", "apad", "-ar", "48000", "-ac", "2", "-c:a", "aac"]
                else:
                    command += ["-an"]
                command += ["-vf", f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
                            "-r", str(fps), "-frames:v", str(clip["frames"]), "-t", f"{duration:.9f}",
                            "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "18", str(normalized)]
                _run(command)
                path = normalized
            paths.append((path, duration))
        listing = root / "concat.txt"
        listing.write_text("".join("file '" + str(p.resolve()).replace("\\", "/").replace("'", "'\\''")
                                   + f"'\nduration {duration:.9f}\n" for p, duration in paths), encoding="utf-8")
        merged = root / "merged.mp4"
        command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                   "-map", "0:v:0", "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "18",
                   "-r", str(fps), "-frames:v", str(sum(c["frames"] for c in clips))]
        if audio:
            command += ["-map", "0:a:0", "-af", "aresample=48000:async=1:first_pts=0,apad", "-ac", "2", "-c:a", "aac",
                        "-t", f"{sum(c['frames'] for c in clips) / fps:.9f}"]
        else:
            command += ["-an"]
        command += ["-movflags", "+faststart", str(merged)]
        _run(command)
        os.replace(merged, dest)


class LowMemoryRun:
    def __init__(self, plan, root):
        if root is None:
            raise RuntimeError("低内存落盘：视频目录创建失败，未开始采样。")
        self.plan, self.root = plan, Path(root)
        self.entries = {}
        self.merged = {}
        self.status = "running"
        self.write_manifest()

    def write_manifest(self):
        payload = {"version": 1, "status": self.status, "frame_rate": self.plan.frame_rate,
                   "scope": "executed_segments", "segments": list(self.entries.values()), "merged": self.merged}
        staging = self.root / ".manifest.tmp"
        staging.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(staging, self.root / "manifest.json")

    def record(self, seg, frames, pre, *, hold, first_only, refined, face_refined, refine_passes=1):
        def clip(path, tensor):
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"低内存落盘：第 {seg.timeline_index + 1} 段视频未保存，停止释放画面：{path}")
            return {"path": str(path), "frames": int(tensor.shape[0]),
                    "width": max(2, int(tensor.shape[2]) + int(tensor.shape[2]) % 2),
                    "height": max(2, int(tensor.shape[1]) + int(tensor.shape[1]) % 2)}
        primary = clip(segment_mp4_path(self.root, seg, suffix="pre" if hold else ""), frames)
        final = None if first_only or hold else primary
        if hold or first_only or (not refined and not face_refined):
            first = primary
        elif refined:
            first = clip(segment_mp4_path(self.root, seg, suffix="pre"), pre)
        else:
            first = None
        self.entries[seg.index] = {"segment": seg.timeline_index + 1, "index": seg.index,
                                   "first_pass_seed": str(resolve_segment_seed(seg, self.plan)),
                                   "hold": hold, "refine_passes": int(refine_passes),
                                   "first": first, "final": final}
        self.write_manifest()

    def trim_previous(self, seg, frame_count):
        """Intermediate passes have been flushed; trim files without retaining RGB tensors."""
        for path in self.root.glob(f"seg_{seg.index:04d}_p*.mp4"):
            with tempfile.TemporaryDirectory(prefix=".cinestack_trim_", dir=self.root) as temporary:
                output = Path(temporary) / "trim.mp4"
                _run([_ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
                      "-frames:v", str(frame_count), "-t", f"{frame_count / self.plan.frame_rate:.9f}",
                      "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", str(output)])
                os.replace(output, path)
        if seg.index in self.entries:
            for stage in ("first", "final"):
                if self.entries[seg.index][stage]:
                    self.entries[seg.index][stage]["frames"] = frame_count
            self.write_manifest()

    def finish(self):
        notes = []
        entries = [self.entries[i] for i in sorted(self.entries)]
        if not entries:
            raise RuntimeError("低内存落盘：没有成功保存的片段。")
        previous_paths = None
        for stage, name in (("first", "first_pass.mp4"), ("final", "final.mp4")):
            if not all(e[stage] for e in entries):
                notes.append(f"{stage}: 部分选中段未生成此阶段，本轮不混合一/二采合并。")
                continue
            clips = [e[stage] for e in entries]
            dest = self.root / name
            try:
                paths = [c["path"] for c in clips]
                if previous_paths == paths:
                    _publish_copy(Path(self.merged["first"]), dest)
                else:
                    merge_disk_clips(clips, dest, float(self.plan.frame_rate))
                self.merged[stage] = str(dest)
                previous_paths = paths
            except Exception as exc:
                raise RuntimeError(f"低内存落盘合并失败：{exc}；已保存分段及缓存保留在 {self.root}") from exc
        self.status = "completed"
        self.write_manifest()
        return [f"低内存落盘：仅交付本轮运行的 {len(entries)} 段，视频目录：{self.root}",
                "IMAGE/AUDIO 输出已阻断；完整视频、各段精修轮次和 manifest.json 从磁盘查看。",
                *[f"{stage}: {path}" for stage, path in self.merged.items()], *notes]
