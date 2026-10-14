"""One predecessor waits for phase/seam correction; older frames are streamed out."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

from ..lib.frame_stream import FrameStream
from .audio_export import prepare_segment_audio_for_file_export, resolve_audio_mode
from .low_memory import merge_disk_clips
from .segment_seed import resolve_segment_seed


class RollingRun:
    def __init__(self, plan, root):
        if root is None:
            raise RuntimeError("滚动生成：无法创建视频目录，未开始采样。")
        self.plan, self.root = plan, Path(root)
        self.pending, self.entries, self.parts = {}, {}, {}
        self.status = "running"
        self.merged = {}
        self.shared_stages = not (plan.refine or {}).get("enabled") and not (plan.face_refine or {}).get("enabled")
        self.write_manifest()

    def write_manifest(self):
        payload = {"version": 2, "mode": "rolling", "status": self.status,
                   "scope": "executed_segments", "frame_rate": self.plan.frame_rate,
                   "segments": list(self.entries.values()), "pending": list(self.pending),
                   "merged": self.merged}
        staging = self.root / ".manifest.tmp"
        staging.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(staging, self.root / "manifest.json")

    def stage(self, seg, *, hold, first_only, refined, face_refined, handoff):
        self.pending[seg.index] = {"hold": hold, "first_only": first_only,
                                   "refined": refined, "face_refined": face_refined,
                                   "handoff": dict(handoff)}
        self.write_manifest()

    def _append(self, stage, seg, frames, audio):
        parts = self.parts.setdefault(stage, [])
        geometry = (max(2, int(frames.shape[2]) + int(frames.shape[2]) % 2),
                    max(2, int(frames.shape[1]) + int(frames.shape[1]) % 2))
        if not parts or parts[-1]["geometry"] != geometry:
            if parts:
                parts[-1]["path"] = str(parts[-1]["writer"].finish())
            name = f"{stage}_{len(parts):03d}"
            writer = FrameStream(self.root, name, width=geometry[0], height=geometry[1],
                                 fps=self.plan.frame_rate, audio_enabled=resolve_audio_mode(self.plan) != "mute")
            parts.append({"writer": writer, "geometry": geometry})
        writer = parts[-1]["writer"]
        start = sum(p["writer"].frames for p in parts)
        prepared = prepare_segment_audio_for_file_export(self.plan, seg, audio_dict=audio,
                                                       frame_count=int(frames.shape[0]))
        writer.append(frames, prepared)
        return {"start_frame": start, "frames": int(frames.shape[0]),
                "width": geometry[0], "height": geometry[1]}

    def flush(self, seg, frames, pre, face_pre, audio):
        flags = self.pending[seg.index]
        first = frames if flags["hold"] or flags["first_only"] else (
            pre if flags["refined"] else (None if flags["face_refined"] else frames))
        final = None if flags["hold"] or flags["first_only"] else frames
        entry = {"index": seg.index, "segment": seg.timeline_index + 1,
                 "first_pass_seed": str(resolve_segment_seed(seg, self.plan)), "first": None, "final": None}
        if first is not None:
            entry["first"] = self._append("first", seg, first, audio)
        if final is not None:
            entry["final"] = entry["first"] if self.shared_stages and final is first else self._append("final", seg, final, audio)
        if face_pre is not None and flags["face_refined"]:
            entry["face_pre"] = self._append("face_pre", seg, face_pre, audio)
        self.entries[seg.index] = entry
        self.pending.pop(seg.index)
        self.write_manifest()

    def finish(self):
        if self.pending:
            raise RuntimeError("滚动生成：仍有未交付片段，不能结束。")
        entries = list(self.entries.values())
        if not entries:
            raise RuntimeError("滚动生成：没有成功输出的片段。")
        notes = []
        for stage, parts in self.parts.items():
            for part in parts:
                if "path" not in part:
                    part["path"] = str(part["writer"].finish())
            key = "first_pass" if stage == "first" else stage
            complete = all(e.get(stage) is not None for e in entries)
            dest = self.root / f"{key}{'' if complete else '.partial'}.mp4"
            if len(parts) == 1:
                os.replace(parts[0]["path"], dest)
            else:
                clips = [{"path": p["path"], "width": p["geometry"][0], "height": p["geometry"][1],
                          "frames": p["writer"].frames} for p in parts]
                merge_disk_clips(clips, dest, float(self.plan.frame_rate))
                for part in parts:
                    Path(part["path"]).unlink(missing_ok=True)
                notes.append(f"{stage}: 画布发生变化，额外统一画布后合并。")
            self.merged[stage] = {"path": str(dest), "complete": complete}
        if self.shared_stages and "final" not in self.merged and all(e.get("final") for e in entries):
            dest = self.root / "final.mp4"
            source = self.merged["first"]["path"]
            try:
                os.link(source, dest)
            except OSError:
                shutil.copy2(source, dest)
            self.merged["final"] = {"path": str(dest), "complete": True}
        self.status = "completed"
        self.write_manifest()
        return [f"滚动生成：当前段＋上一段；已输出 {len(entries)} 个选中段。目录：{self.root}",
                "交接、裁剪、接缝完成后才写入持续编码器；不保存逐段 MP4/中间精修视频/完整 RGB 缓存。",
                "IMAGE/AUDIO 已阻断；一采 AV 缓存保留，支持独立 seed 与仅二采。",
                *[f"{key}{'' if value['complete'] else '（部分段）'}: {value['path']}" for key, value in self.merged.items()], *notes]

    def abort(self):
        for parts in self.parts.values():
            for part in parts:
                part["writer"].abort()
        if self.status != "completed":
            self.status = "interrupted"
            try:
                self.write_manifest()
            except OSError:
                pass
