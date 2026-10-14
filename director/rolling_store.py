"""Durable per-segment references into immutable rolling output videos."""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..lib.video_ranges import compose_ranges
from .execution_mode import director_execution_mode, rolling_full_export
from .segment_cache import _cache_root, first_pass_cache_fingerprint
from .audio_export import resolve_audio_mode
from .low_memory import _has_audio


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"滚动导出记录无法读取：{path}：{exc}") from exc


def _stamp(path):
    info = Path(path).stat()
    return {"size": info.st_size, "mtime_ns": info.st_mtime_ns}


class RollingStore:
    def __init__(self, plan, node_id):
        self.plan = plan
        root = _cache_root(node_id)
        if root is None:
            raise ValueError("滚动生成：无法打开成片索引目录。")
        self.path = root / "rolling_videos.json"
        self.selected = set(range(len(plan.segments))) if plan.run_indices is None else set(plan.run_indices)
        self.full = rolling_full_export(plan)
        self.stage = "first" if director_execution_mode(plan) == "first_pass" else "final"
        self.entries = {}
        self.imported = False
        if self.path.exists():
            payload = _read(self.path)
            if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("segments"), dict):
                raise ValueError("滚动成片索引格式无效；请指定已有完整 manifest 或使用新的缓存名。")
            self.entries = payload["segments"]
        source = str((plan.raw.get("output") or {}).get("rollingBaseManifest") or "").strip()
        if self.full and source and any(seg.index not in self.selected and str(seg.index) not in self.entries
                                        for seg in plan.segments):
            self._import_manifest(Path(source).expanduser())
        if self.full:
            pack = plan.refine or {}
            if director_execution_mode(plan) == "legacy" and pack.get("enabled") and pack.get("confirm_first_pass"):
                raise ValueError("滚动全部导出：先确认一采模式请明确选择“仅一采”或“仅二采”，避免混合交付阶段。")
            self._validate_unselected()

    def _import_manifest(self, path):
        if path.is_dir():
            path = path / "manifest.json"
        payload = _read(path)
        if not isinstance(payload, dict) or payload.get("mode") != "rolling" or payload.get("status") != "completed":
            raise ValueError("已有结果必须是成功完成的滚动生成 manifest.json。")
        if float(payload.get("frame_rate", 0)) != float(self.plan.frame_rate):
            raise ValueError("已有结果帧率与当前时间轴不一致。")
        # Prefer a new full manifest; v2 selected-run manifests must cover all slots.
        full = payload.get("full_export")
        if full:
            rows = full["segments"]
        else:
            rows = payload.get("segments", [])
        numbers = [row.get("segment") for row in rows]
        if sorted(numbers) != list(range(1, len(self.plan.segments) + 1)):
            raise ValueError("已有 manifest 未覆盖当前完整时间轴，或段数/顺序不符。")
        for seg in self.plan.segments:
            if seg.index in self.selected or str(seg.index) in self.entries:
                continue  # An explicit base fills missing slots, never rolls back newer work.
            row = next(r for r in rows if r["segment"] == seg.timeline_index + 1)
            fp = first_pass_cache_fingerprint(seg, self.plan)
            if str(row.get("first_pass_seed")) != str(fp["seed"]):
                raise ValueError(f"第 {seg.timeline_index + 1} 段旧结果 seed 与当前不符。")
            record = {"identity": row.get("identity", fp), "audio_mode": resolve_audio_mode(self.plan),
                      "imported_from": str(path.resolve()),
                      "identity_origin": row.get("identity_origin", "manifest" if row.get("identity") else "user_selected_legacy_manifest")}
            for stage in ("first", "final", "face_pre"):
                info = row.get(stage)
                merged = payload.get("merged", {}).get(stage)
                if full:
                    merged = full.get("merged", {}).get(stage)
                if info and merged:
                    # Resolve beside the manifest first, supporting moved output folders.
                    name = Path(str(merged["path"]).replace("\\", "/")).name
                    candidate = path.parent / name
                    source = candidate if candidate.is_file() else Path(merged["path"])
                    if source.is_file():
                        record[stage] = {**info, "path": str(source.resolve()), "stamp": _stamp(source),
                                         "audio": _has_audio(source), "segment": seg.timeline_index + 1}
            self.entries[str(seg.index)] = record
        self.imported = True

    def _validate_unselected(self):
        problems = []
        for seg in self.plan.segments:
            if seg.index in self.selected:
                continue
            label = f"第 {seg.timeline_index + 1} 段"
            record = self.entries.get(str(seg.index), {})
            clip = record.get(self.stage)
            if not clip:
                problems.append(f"{label}：缺少{'一采' if self.stage == 'first' else '最终'}视频记录")
                continue
            expected = first_pass_cache_fingerprint(seg, self.plan)
            stored = record.get("identity", {})
            diff = [k for k in sorted(set(expected) | set(stored)) if expected.get(k) != stored.get(k)]
            if diff:
                problems.append(f"{label}：已有结果身份不符（{', '.join(diff)}）")
            if record.get("audio_mode") != resolve_audio_mode(self.plan):
                problems.append(f"{label}：音频模式已变化")
            try:
                if _stamp(clip["path"]) != clip["stamp"]:
                    problems.append(f"{label}：视频文件被替换或修改")
                for key in ("start_frame", "frames", "width", "height"):
                    if type(clip[key]) is not int or clip[key] < (0 if key == "start_frame" else 1):
                        raise ValueError(f"{key} 无效")
            except (OSError, KeyError, TypeError, ValueError) as exc:
                problems.append(f"{label}：视频缺失或记录损坏（{exc}）")
        if problems:
            raise ValueError("滚动全部导出已停止，未开始采样：\n" + "\n".join(problems)
                             + "\n可指定旧版完整输出的 manifest.json，或改为分段导出；不会自动补跑未选段。")

    def commit(self, run):
        if self.full:
            self._validate_unselected()  # Detect files removed/replaced during sampling too.
        entries = {k: v for k, v in self.entries.items() if int(k) < len(self.plan.segments)}
        audio_flags = {}
        for index, row in run.entries.items():
            seg = self.plan.segments[index]
            record = {"identity": first_pass_cache_fingerprint(seg, self.plan),
                      "audio_mode": resolve_audio_mode(self.plan), "identity_origin": "generated"}
            row["identity"] = record["identity"]
            for stage in ("first", "final", "face_pre"):
                if row.get(stage) and stage in run.merged:
                    path = str(Path(run.merged[stage]["path"]).resolve())
                    if path not in audio_flags:
                        audio_flags[path] = _has_audio(path)
                    record[stage] = {**row[stage], "path": path, "stamp": _stamp(path),
                                     "audio": audio_flags[path], "segment": seg.timeline_index + 1}
                    # A geometry-changing run has already padded the whole stage.
                    for axis in ("width", "height"):
                        record[stage][axis] = max(e[stage][axis] for e in run.entries.values() if e.get(stage))
            # Replacing first pass invalidates that slot's old final stage too.
            entries[str(index)] = record
        notes = []
        if self.full:
            clips, rows, cursor = [], [], 0
            for seg in self.plan.segments:
                record = entries.get(str(seg.index), {})
                clip = record.get(self.stage)
                if not clip:
                    raise ValueError(f"滚动全部导出：第 {seg.timeline_index + 1} 段没有本轮要求的阶段，未混用一/二采。")
                clips.append(clip)
                rows.append({"segment": seg.timeline_index + 1, "index": seg.index,
                             "first_pass_seed": str(record["identity"]["seed"]), "identity": record["identity"],
                             "identity_origin": record.get("identity_origin", "generated"),
                             "reused": seg.index not in self.selected, "source": dict(clip),
                             self.stage: {"start_frame": cursor, "frames": clip["frames"],
                                          "width": max(c["width"] for c in clips), "height": max(c["height"] for c in clips)}})
                cursor += clip["frames"]
            dest = run.root / ("timeline_first_pass.mp4" if self.stage == "first" else "timeline_final.mp4")
            if len(self.selected) == len(self.plan.segments) and self.stage in run.merged:
                import shutil
                try:
                    os.link(run.merged[self.stage]["path"], dest)
                except OSError:
                    shutil.copy2(run.merged[self.stage]["path"], dest)
            else:
                compose_ranges(clips, dest, float(self.plan.frame_rate))
            for row in rows:
                row[self.stage].update(width=max(c["width"] for c in clips), height=max(c["height"] for c in clips))
            run.full_export = {"segments": rows, "frames": cursor,
                               "merged": {self.stage: {"path": str(dest), "complete": True}}}
            notes += [f"全部导出：新生成 {len(self.selected)} 段，复用 {len(rows) - len(self.selected)} 段，共 {cursor} 帧 → {dest}",
                      "未选段复用保存画面；不会重新采样或重算其接缝。替换段可能需要人工检查前后接点。"]
            if any(entries[str(seg.index)].get("identity_origin") == "user_selected_legacy_manifest" for seg in self.plan.segments):
                notes.append("旧 manifest 由用户显式指定；旧版缺少完整参数身份，请确认段序与素材版本。")
        staging = self.path.with_suffix(".tmp")
        staging.write_text(json.dumps({"version": 1, "segments": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(staging, self.path)
        return notes
