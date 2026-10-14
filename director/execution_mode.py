"""Optional Director UI execution intent; absent fields retain legacy behavior."""
from __future__ import annotations


def rolling_enabled(plan) -> bool:
    output = (getattr(plan, "raw", None) or {}).get("output") or {}
    return output.get("rollingGeneration", False) is True


def low_memory_enabled(plan) -> bool:
    output = (getattr(plan, "raw", None) or {}).get("output") or {}
    return output.get("lowMemoryMode", False) is True or rolling_enabled(plan)


def disk_export_enabled(plan) -> bool:
    return low_memory_enabled(plan) or getattr(plan, "export_mode", "all") == "segments"


def director_execution_mode(plan) -> str:
    mode = str((getattr(plan, "raw", None) or {}).get("executionMode") or "legacy")
    if mode not in {"legacy", "first_pass", "refine_only"}:
        raise ValueError(f"未知导演台执行模式：{mode}")
    return mode


def apply_director_execution_mode(plan) -> str:
    """Apply to this execution plan only, never mutate a wired Refine pack."""
    mode = director_execution_mode(plan)
    if mode == "first_pass":
        plan.refine = {**(plan.refine or {}), "enabled": False, "refine_only": False}
        plan.face_refine = {**(plan.face_refine or {}), "enabled": False}
    elif mode == "refine_only":
        if not isinstance(plan.refine, dict) or not plan.refine.get("enabled"):
            raise ValueError("仅二采已停止：请连接并启用影栈 Refine 节点。未执行一采。")
        if plan.refine.get("mode") not in {"refine", "upscale"}:
            raise ValueError("仅二采已停止：Refine 必须使用 refine 或 upscale 模式。未执行一采。")
        plan.refine = {**plan.refine, "refine_only": True, "confirm_first_pass": False}
    return mode
