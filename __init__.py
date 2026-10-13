# Modified for CineStack on 2026-10-13; see CHANGELOG.md and NOTICE.
"""ComfyUI CineStack H3 Director — timeline plugin for MiniMax-H3 AV generation.

Based on ComfyUI official MiniMax H3 support (PR #15224 / #15228).
Licensed under the Apache License, Version 2.0. See LICENSE.
"""

from .nodes.conditioning import (
    CineStackH3DirectorConditioning,
    CineStackH3DirectorPlannerConditioning,
)
from .nodes.director import CineStackH3Director
from .nodes.director_refine import CineStackH3DirectorRefine
from .nodes.director_selflift import CineStackH3DirectorSelfLift
from .nodes.director_semantic_bridge import CineStackH3DirectorSemanticBridge
from .nodes.director_face_refine import CineStackH3DirectorFaceRefine
from .nodes.director_groups import (
    CineStackH3DirectorGroupImageToVideo,
    CineStackH3DirectorGroupReferenceToVideo,
    CineStackH3DirectorGroupsCombine,
)

NODE_CLASS_MAPPINGS = {
    "CineStackH3Director": CineStackH3Director,
    "CineStackH3DirectorRefine": CineStackH3DirectorRefine,
    "CineStackH3DirectorSelfLift": CineStackH3DirectorSelfLift,
    "CineStackH3DirectorSemanticBridge": CineStackH3DirectorSemanticBridge,
    "CineStackH3DirectorFaceRefine": CineStackH3DirectorFaceRefine,
    "CineStackH3DirectorConditioning": CineStackH3DirectorConditioning,
    "CineStackH3DirectorPlannerConditioning": CineStackH3DirectorPlannerConditioning,
    "CineStackH3DirectorGroupImageToVideo": CineStackH3DirectorGroupImageToVideo,
    "CineStackH3DirectorGroupReferenceToVideo": CineStackH3DirectorGroupReferenceToVideo,
    # Must stay in NODE_CLASS_MAPPINGS: ComfyUI skips comfy_entrypoint when
    # NODE_CLASS_MAPPINGS is present (if/elif in load_custom_node).
    "CineStackH3DirectorGroupsCombine": CineStackH3DirectorGroupsCombine,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CineStackH3Director": "CineStack H3 Director",
    "CineStackH3DirectorRefine": "CineStack H3 Director Refine",
    "CineStackH3DirectorSelfLift": "CineStack H3 Director SelfLift",
    "CineStackH3DirectorSemanticBridge": "CineStack H3 Director Semantic Bridge",
    "CineStackH3DirectorFaceRefine": "CineStack H3 Director FaceRefine",
    "CineStackH3DirectorConditioning": "CineStack H3 Director Conditioning",
    "CineStackH3DirectorPlannerConditioning": "CineStack H3 Director Planner Conditioning",
    "CineStackH3DirectorGroupImageToVideo": "CineStack H3 Director Group (Image to Video)",
    "CineStackH3DirectorGroupReferenceToVideo": "CineStack H3 Director Group (Reference to Video)",
    "CineStackH3DirectorGroupsCombine": "CineStack H3 Director Groups Combine",
}

WEB_DIRECTORY = "./web/js"

import logging

_log = logging.getLogger("ComfyUI-CineStack-H3")

try:
    from .director.http_routes import register_routes as _register_director_routes

    if not _register_director_routes():
        _log.warning(
            "CineStack H3 Director HTTP routes deferred (PromptServer not ready). "
            "Restart ComfyUI if /cinestack/h3/* returns 404."
        )
except Exception as _director_routes_exc:
    _log.warning("CineStack H3 Director HTTP routes failed to load: %s", _director_routes_exc)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
