"""Connected timeline boundaries, with bounded pixel reads for unselected neighbours.

The right segment still owns each link (old workflow schema). Only a selected
island's right edge reads future cached pixels; internal edges run forwards.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import torch

from .segment_continuity import is_continuity_active
from .h3_motion_context import CONTEXT_FRAME_CHOICES, snap_context_frames

BOUNDARY_FRAMES = max(CONTEXT_FRAME_CHOICES)
LOCK_KEY = "cinestack_junction_lock"


def links(plan, seg):
    i = seg.index
    return {"left": is_continuity_active(plan, seg),
            "right": i + 1 < len(plan.segments) and is_continuity_active(plan, plan.segments[i + 1])}


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _stamp(path):
    st = Path(path).stat()
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}


def save_boundary(node_id, seg, plan, frames, audio=None, *, first_pass=False):
    """Store only the actual exported head/tail, never a view retaining a clip."""
    from . import segment_cache as cache
    root = cache._cache_root(node_id) if node_id else None
    if root is None or frames is None or not len(frames):
        return
    stem = root / (f"seg_{seg.index:04d}" + (".pre" if first_pass else ""))
    meta = Path(str(stem) + ".meta.json")
    handoff = Path(str(stem) + ".handoff.json")
    if not meta.is_file():
        return
    def compact(x):
        return cache._frames_to_disk(x).clone()
    payload = {"version": 1, "identity": _json(meta),
               "handoff": _json(handoff) if handoff.is_file() else {},
               "frames": len(frames), "head": compact(frames[:1]),
               "tail": compact(frames[-BOUNDARY_FRAMES:])}
    av = Path(str(stem) + ".av.pt")
    payload["av_stamp"] = _stamp(av) if av.is_file() else None
    if isinstance(audio, dict) and torch.is_tensor(audio.get("waveform")):
        sr = int(audio.get("sample_rate") or 0)
        if sr > 0:
            n = max(1, round(BOUNDARY_FRAMES / float(plan.frame_rate) * sr))
            payload["audio"] = {"sample_rate": sr,
                                "waveform": audio["waveform"][..., -n:].detach().cpu().clone()}
    cache._write_via_temp(Path(str(stem) + ".boundary.pt"), lambda p: torch.save(payload, p))


def _video_window(path, start, count, width, height):
    """Decode exact frame indices. FFmpeg discards the prefix; Python sees <=56f."""
    from ..lib.video_export import _ffmpeg_bin
    if start < 0 or count < 1 or count > BOUNDARY_FRAMES:
        raise ValueError("无效的衔接帧区间")
    cmd = [_ffmpeg_bin(), "-v", "error", "-threads", "2", "-i", str(path),
           "-vf", f"trim=start_frame={start}:end_frame={start + count},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
           "-an", "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode or len(proc.stdout) != count * width * height * 3:
        raise ValueError(f"衔接视频帧读取失败：{Path(path).name}：{proc.stderr.decode(errors='replace')[-400:]}")
    return torch.frombuffer(bytearray(proc.stdout), dtype=torch.uint8).reshape(count, height, width, 3).float().div_(255)


def load_boundary(node_id, seg, plan, side, *, entries=None):
    """Read a small sidecar, mmap old RGB, or stream a saved video range.

    Never fall back to loading/decoding a whole neighbouring AV latent.
    Metadata changes caused by sampling options are allowed, source changes aren't.
    """
    from . import segment_cache as cache
    root = cache._cache_dir_or_none(node_id) if node_id else None
    if root is None:
        raise ValueError("缓存目录不存在")
    from .execution_mode import director_execution_mode
    first_pass = director_execution_mode(plan) == "first_pass"
    stem = root / (f"seg_{seg.index:04d}" + (".pre" if first_pass else ""))
    meta_path = Path(str(stem) + ".meta.json")
    expected = cache.first_pass_cache_fingerprint(seg, plan) if first_pass else cache.segment_cache_fingerprint(seg, plan)
    meta = _json(meta_path) if meta_path.is_file() else None
    if meta is not None and cache.source_identity_changed(meta, expected):
        raise ValueError("源视频已变化，邻段缓存不属于当前源视频")
    path = Path(str(stem) + ".boundary.pt")
    n = snap_context_frames(plan.continuity_overlap_frames) if side == "tail" else 1
    if path.is_file():
        data = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
        handoff_path = Path(str(stem) + ".handoff.json")
        handoff = _json(handoff_path) if handoff_path.is_file() else {}
        av = Path(str(stem) + ".av.pt")
        if (data.get("version") != 1 or data.get("identity") != meta or data.get("handoff") != handoff
                or data.get("av_stamp") != (_stamp(av) if av.is_file() else None)):
            raise ValueError("首尾缓存与生成结果/裁剪记录不一致，请重新生成该邻段或恢复配套缓存")
        pixels = data.get(side)
        if (not torch.is_tensor(pixels) or pixels.dtype != torch.uint8 or pixels.ndim != 4
                or pixels.shape[-1] != 3 or not 0 < len(pixels) <= BOUNDARY_FRAMES):
            raise ValueError("首尾缓存内容损坏")
        pixels = pixels[-n:] if side == "tail" else pixels[:1]
        sound = data.get("audio") if side == "tail" else None
        if sound is not None:
            sound = dict(sound)
            count = max(1, round(len(pixels) / float(plan.frame_rate) * sound["sample_rate"]))
            sound["waveform"] = sound["waveform"][..., -count:].clone()
        return pixels.float().div_(255), sound
    raw = Path(str(stem) + ".pt")
    if meta is not None and raw.is_file():
        # Old torch.save zip caches support mmap. Refuse legacy non-mappable
        # formats rather than silently allocating the entire neighbouring clip.
        data = torch.load(raw, map_location="cpu", weights_only=True, mmap=True)
        if not torch.is_tensor(data) or data.ndim != 4 or not len(data):
            raise ValueError("旧画面缓存损坏")
        if first_pass:
            hp = Path(str(stem) + ".handoff.json")
            handoff = _json(hp) if hp.is_file() else {}
            start = int(handoff.get("trim_frames") or 0)
            length = int(handoff.get("export_frames") or (len(data) - start))
            data = data[start:start + length]
        pixels = (data[-n:] if side == "tail" else data[:1]).clone()
        return cache._frames_from_disk(pixels), None
    movie = Path(str(stem) + ".frames.mkv")
    if meta is not None and movie.is_file():
        hp = Path(str(stem) + ".handoff.json")
        handoff = _json(hp) if hp.is_file() else {}
        length = int(handoff.get("export_frames") or 0)
        if length > 0:
            count = min(n, length)
            return _video_window(movie, (int(handoff.get("trim_frames") or 0) if first_pass else 0) + (length - count if side == "tail" else 0),
                                 count, int(plan.width), int(plan.height)), None
    if entries is None:
        index = root / "rolling_videos.json"
        entries = _json(index).get("segments", {}) if index.is_file() else {}
    record = entries.get(str(seg.index), {})
    if cache.source_identity_changed(record.get("identity"), expected):
        raise ValueError("滚动视频源身份与当前源视频不一致")
    clip = record.get("first") if first_pass else (record.get("final") or record.get("first"))
    if clip:
        source = Path(clip["path"])
        if not source.is_file() or _stamp(source) != clip.get("stamp"):
            raise ValueError("邻段滚动视频文件缺失或已被替换")
        length = int(clip["frames"])
        count = min(n, length)
        start = int(clip["start_frame"]) + (length - count if side == "tail" else 0)
        return _video_window(source, start, count, int(plan.width), int(plan.height)), None
    raise ValueError("缺少可读取的首尾画面缓存；只有 AV latent 不会整段解码，请恢复旧视频索引/完整 manifest 或先生成该邻段")


def constraint_problem(node_id, seg, plan):
    """New caches bind both link states; old caches remain refine-compatible."""
    from .segment_cache import _cache_dir_or_none
    root = _cache_dir_or_none(node_id) if node_id else None
    path = root / f"seg_{seg.index:04d}.pre.handoff.json" if root else None
    if path is None or not path.is_file():
        return None
    try:
        saved = _json(path).get("junction_links")
        if saved is not None and saved != links(plan, seg):
            return "一采缓存失配：左右连接线状态已变化；请恢复连接线或明确重做本段一采"
    except (OSError, ValueError, AttributeError):
        return "一采 handoff 接点记录损坏"
    return None


def preflight(node_id, plan, *, entries=None):
    from .refine_pack import refine_only_enabled, confirm_first_pass_enabled, refine_will_sample
    from .segment_cache import first_pass_cache_problem
    from .face_refine.pack import face_refine_enabled
    if refine_only_enabled(plan):
        return  # Uses frozen first-pass constraints, not today's neighbours.
    selected = set(range(len(plan.segments))) if plan.run_indices is None else set(plan.run_indices)
    errors = []
    for seg in plan.segments:
        if seg.index not in selected:
            continue
        if ((confirm_first_pass_enabled(plan) and refine_will_sample(plan, seg)) or face_refine_enabled(plan)):
            if first_pass_cache_problem(node_id, seg, plan) is None:
                continue
        state = links(plan, seg)
        for side, offset, part in (("left", -1, "tail"), ("right", 1, "head")):
            other = seg.index + offset
            if not state[side] or other in selected:
                continue
            try:
                window = load_boundary(node_id, plan.segments[other], plan, part, entries=entries)
                del window
            except Exception as exc:
                errors.append(f"第 {seg.index + 1} 段{'左' if side == 'left' else '右'}接点，需要第 {other + 1} 段缓存：{exc}")
    if errors:
        raise ValueError("段间连接检查失败，未开始采样：\n" + "\n".join(errors)
                         + "\n请恢复对应缓存、将该邻段纳入生成，或明确断开对应连接线。")


def apply_end_lock(positive, latent, frame, vae, *, frame_index=None):
    """One exported neighbour head as a target keyframe, also for R2V refs."""
    import node_helpers
    from ..lib.image_prep import fit_canvas
    from .h3_motion_context import video_from_latent, pixel_frames_for_latent_t
    from .h3_context_patches import CTX_FRAME_KEY, ensure_layout_patch, ensure_payload_patch
    ensure_layout_patch()
    ensure_payload_patch()
    video = video_from_latent(latent)
    total = pixel_frames_for_latent_t(video.shape[2])
    at = total - 1 if frame_index is None else int(frame_index)
    if not 0 <= at < total:
        raise ValueError(f"右接点帧 {at} 超出采样范围 {total}")
    encoded = vae.encode(fit_canvas(frame[:1], int(video.shape[4]) * 16, int(video.shape[3]) * 16))
    if encoded.ndim != 5 or encoded.shape[2] != 1:
        raise ValueError("右接点首帧 VAE 编码无效")
    result = []
    for tensor, meta in positive:
        # Existing end stills yield to the connected neighbour. Keep head guide.
        kfs = [dict(k) for k in meta.get("minimax_keyframes", [])
               if not k.get("cinestack_right_lock") and int(k.get(CTX_FRAME_KEY, k.get("resolved_frame_index", -1))) < at]
        kfs.append({"resolved_frame_index": at, CTX_FRAME_KEY: at,
                    "latent": encoded, "cinestack_right_lock": True})
        updated = node_helpers.conditioning_set_values([[tensor, meta]],
                   {"minimax_keyframes": kfs, "minimax_frame_count": total})
        result.extend(updated)
    return result
