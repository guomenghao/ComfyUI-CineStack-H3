"""Fail closed before a refine-only batch can sample or alter caches."""

from __future__ import annotations


def validate_refine_only_cache(node_id, plan) -> None:
    from .refine_pack import refine_sigmas_override, refine_will_sample
    from .segment_cache import first_pass_cache_problem, load_first_pass_cache

    pack = getattr(plan, "refine", None) or {}
    if not pack.get("enabled") or pack.get("mode") not in {"refine", "upscale"}:
        raise ValueError("仅二采需要已连接的 Refine，且 mode 为 refine 或 upscale；未执行一采。")
    if refine_sigmas_override(pack) is None:
        raise ValueError("仅二采需要有效的二采 SIGMAS；未执行一采。")
    selected = getattr(plan, "run_indices", None)
    segments = [s for s in plan.segments if selected is None or s.index in selected]
    if not segments:
        raise ValueError("仅二采未选中任何片段；未执行一采。")
    errors = []
    for seg in segments:
        label = f"第 {seg.timeline_index + 1} 段"
        if not refine_will_sample(plan, seg):
            errors.append(f"{label}：被 skip_fl2v 跳过，无法执行二采")
            continue
        problem = first_pass_cache_problem(node_id, seg, plan)
        if problem:
            errors.append(f"{label}：{problem}")
            continue
        # Validate all payloads before the first sample; do not retain a batch
        # of huge AV latents in RAM. The executor revalidates each one on use.
        try:
            cached = load_first_pass_cache(node_id, seg, plan, include_frames=False, raise_on_error=True)
            if cached is None:
                errors.append(f"{label}：一采缓存已变化或 AV latent 无效")
            del cached
        except Exception as exc:
            errors.append(f"{label}：{exc}")
    if errors:
        raise ValueError("仅二采已停止，未执行任何一采或二采：\n" + "\n".join(errors)
                         + "\n请恢复对应参数/分段 seed，或关闭仅二采后明确选择需要重做的段。")
