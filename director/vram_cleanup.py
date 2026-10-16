# Modified for CineStack on 2026-10-13; see CHANGELOG.md and NOTICE.
"""Release GPU memory between CineStack H3 Director segment runs."""

from __future__ import annotations

import gc
import logging

log = logging.getLogger("ComfyUI-CineStack-H3.director.vram")


def _evict_dead_loaded_models() -> int:
    """Pop Comfy LoadedModel slots that ``free_memory`` will skip forever.

    ``is_dead()`` means the ModelPatcher weakref is gone while the shared
    MiniMaxH3 module is still alive (graph MODEL / Sage cycle). Those slots
    log ``Potential memory leak detected with model MiniMaxH3`` and then sit
    in ``current_loaded_models``, so later unloads cannot touch them.
    Evicting the slot does not copy weights; it restores unload bookkeeping.
    """
    try:
        import comfy.model_management as mm
    except Exception:
        return 0
    models = getattr(mm, "current_loaded_models", None)
    if not models:
        return 0
    evicted = 0
    for i in range(len(models) - 1, -1, -1):
        cur = models[i]
        try:
            if not cur.is_dead():
                continue
            name = "?"
            try:
                real = cur.real_model()
                name = type(real).__name__ if real is not None else "?"
            except Exception:
                pass
            models.pop(i)
            evicted += 1
            log.info("CineStack H3 Director: evicted dead LoadedModel slot (%s)", name)
        except Exception:
            continue
    return evicted


def cleanup_sampling_buffers() -> dict:
    """Run Comfy's node-boundary buffer cleanup between internal sampling calls.

    Drain prefetch BEFORE reset (which synchronizes streams and releases dynamic
    patch host buffers). Do this while loaded patchers are still reachable, before
    optional model unloading. Never manually unregister pins or trim allocators.
    Older/non-AIMDO hosts keep their existing prefetch-only path.
    """
    from importlib import import_module
    result = {"prefetch": "unavailable", "cast_buffers": "not_applicable"}
    try:
        mm = import_module("comfy.model_management")
        memory = import_module("comfy.memory_management")
    except ImportError:
        memory = None
        try:
            mm = import_module("comfy.model_management")
        except ImportError:
            return result
    dynamic = bool(getattr(memory, "aimdo_enabled", False))
    if dynamic:
        result["cast_buffers"] = "pending"
    try:
        prefetch = import_module("comfy.model_prefetch")
    except ImportError:
        prefetch = None
    drain = getattr(prefetch, "cleanup_prefetch_queues", None)
    reset = getattr(mm, "reset_cast_buffers", None)
    try:
        if callable(drain):
            drain()
            result["prefetch"] = "cleared"
        if dynamic:
            if not callable(drain) or not callable(reset):
                result["cast_buffers"] = "unsupported"
                log.warning("CineStack host buffer cleanup unavailable: AIMDO host lacks prefetch/reset API")
            else:
                reset()
                result["cast_buffers"] = "reset"
    except Exception as exc:
        # Do not mask a sampler/interruption error. Surface failure in the trace.
        if dynamic:
            result["cast_buffers"] = "failed"
        result["error"] = type(exc).__name__
        log.warning("CineStack host buffer cleanup failed: %s", exc)
    return result


def cleanup_segment_vram(*, enabled: bool = True, unload_models: bool = True) -> None:
    """Release segment GPU memory: gc, optional unload of ComfyUI models, empty CUDA cache.

    Finish prefetch/cast cleanup before optional model unloading, while dynamic
    patchers are still reachable. Sampling also does this at each pass boundary
    even when the optional inter-segment model unload is disabled.
    """
    if not enabled:
        return
    gc.collect()
    try:
        import comfy.model_management as mm

        cleanup_sampling_buffers()
        mm.cleanup_models_gc()
        _evict_dead_loaded_models()
        if unload_models:
            mm.unload_all_models()
            mm.cleanup_models()
        _evict_dead_loaded_models()
        gc.collect()
        mm.soft_empty_cache()
    except Exception as exc:
        log.warning("Segment VRAM cleanup failed: %s", exc)
        return
    if unload_models:
        log.debug("CineStack H3 Director: segment VRAM cleanup (models unloaded, cache cleared)")
    else:
        log.debug("CineStack H3 Director: segment VRAM cleanup (cache cleared, models kept loaded)")


def release_models_for_export() -> dict:
    """End of inference: unload through Comfy, then discard reloadable host pins.

    Keep strong patcher references across unload (the manager may remove its
    records). Never touch weight dictionaries, mmap backing files or disk caches.
    Older static patchers have a no-op partially_unload_ram implementation.
    """
    result = {"status": "unavailable", "released_host_bytes": 0}
    try:
        import comfy.model_management as mm
        buffers = cleanup_sampling_buffers()
        if buffers.get("error") or buffers.get("cast_buffers") in {"failed", "unsupported"}:
            return {**result, "status": "buffer_cleanup_failed"}
        patchers = [r.model for r in getattr(mm, "current_loaded_models", ())
                    if getattr(r, "model", None) is not None]
        mm.unload_all_models()
        # Complete outstanding device work before truncating host buffers.
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        seen = set()
        for patcher in patchers:
            if id(patcher) in seen:
                continue
            seen.add(id(patcher))
            release = getattr(patcher, "partially_unload_ram", None)
            if callable(release):
                result["released_host_bytes"] += int(release(1e32) or 0)
        mm.soft_empty_cache()
        result["status"] = "released"
    except ImportError:
        return result
    except Exception as exc:
        result.update(status="failed", error=type(exc).__name__)
        log.warning("Export model handoff cleanup failed: %s", exc)
    gc.collect()
    return result
