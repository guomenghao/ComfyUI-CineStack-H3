# Modified for CineStack on 2026-10-13; see CHANGELOG.md and NOTICE.
"""First-pass SelfLift (progressive dual-resolution) for CineStack H3 Director."""

from .pack import (
    MMX_DIR_SELFLIFT,
    selflift_enabled,
    selflift_fingerprint,
    selflift_report_line,
    selflift_will_run,
)
from .sample import sample_selflift_stage

__all__ = [
    "MMX_DIR_SELFLIFT",
    "selflift_enabled",
    "selflift_fingerprint",
    "selflift_report_line",
    "selflift_will_run",
    "sample_selflift_stage",
]
