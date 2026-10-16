"""Ownership handoff after all export seam operations and cache writes."""
from .segment_continuity import export_frame_view_key


def merged_segment_views(sources, merged, selected):
    """Keep geometry and selection order; share the output's single storage.

    Never mutate sources: cached segment files and caller-owned tensors remain
    unchanged. Only exact source views can be rebound (not overlapping slices).
    """
    lookup = {}
    offset = 0
    for source in sources:
        count, h, w, _ = source.shape
        y, x = (merged.shape[1] - h) // 2, (merged.shape[2] - w) // 2
        lookup[export_frame_view_key(source)] = merged[offset:offset + count, y:y + h, x:x + w]
        offset += count
    return [lookup.get(export_frame_view_key(frame), frame) for frame in selected]
