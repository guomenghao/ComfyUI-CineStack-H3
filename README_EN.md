# CineStack H3

[中文](README.md) · [Migration](docs/migration.md) · [Publishing](docs/publishing.md)

CineStack is a planned local cinematic production workflow platform. This repository is its first H3 generation module for ComfyUI, **not the complete future platform**.

Maintained by **guomenghao**. Source attribution and applicable licenses are documented in [NOTICE](NOTICE) and [the upstream archive](docs/upstream/README_EN.md).

## Features

- Multi-segment H3 audiovisual timelines, external groups and Director packs.
- Optional fixed first-pass seed per segment (blank inherits global; zero is valid).
- Strict `refine_only`: validate selected cached AV latents before sampling. Missing, mismatched or corrupt caches report specific reasons and never trigger first-pass sampling.
- Independent `CineStackH3Director*` node IDs, HTTP routes and progress events, with legacy workflow conversion.
- Upstream Refine, SelfLift, Semantic Bridge and FaceRefine capabilities.

## Low RAM disk delivery (0.3.0)

Enable **Low RAM · save to disk** in Director output settings. It persists selected clips and first-pass AV caches, retains predecessor continuity data until consumed, then releases old RGB storage. First/final stages merge from disk.
Full IMAGE/AUDIO sockets are blocked in this mode; use the file paths and `manifest.json` in the report. Only checked segments are delivered. Fixed seeds and strict second-pass reuse remain supported. The toggle defaults off for legacy workflows.
See [disk-mode details](docs/low-memory-mode.txt). Real GPU/server memory acceptance remains pending.

## Install

Use a ComfyUI environment with official MiniMax H3 support (upstream minimum 0.30.0).

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/guomenghao/ComfyUI-CineStack-H3.git
python -m pip install -r ComfyUI-CineStack-H3/requirements.txt
```

Restart ComfyUI; nodes appear under `CineStack/H3`. Model weights are not included.

Fix each segment's seed, generate and approve first-pass results, then select the segments,
connect Refine SIGMAS and enable `refine_only`. Changing the global seed leaves fixed segment seeds unchanged.
Use `refine` or `upscale`; FL2V requires `skip_fl2v=false`.

Legacy UI workflows migrate in memory when upstream nodes are absent. With both plugins installed,
use the explicit converter to select CineStack. API prompts require explicit conversion.
The legacy cache path `output/minimax_seg_cache/` is preserved; use separate cache names for simultaneous installations.

## Release status

Version 0.3.0 includes low-memory disk delivery plus the Director segment workbench, official H3 import fix, and cache/queue/strict-failure review fixes. CPU and real-editor browser fixture tests are provided.

The workbench shows effective seeds, checked run scope, first-pass metadata and rendered-cache existence.
Execution choices are Follow graph (legacy default), First pass only (save first-pass cache; skip refinement/face refinement),
and Second pass only (matching cache required; never regenerate first passes). Queue submits the current ComfyUI workflow.
Execution intent is stored in optional timeline JSON, without changing node IDs, connections or positional widgets.
Cache labels are metadata checks; latent validation still runs before execution. Rendered-cache existence is not proof of a completed second pass.
Actual ComfyUI and GPU/model generation acceptance remains pending; Registry publication is not yet completed.
Publication is manually triggered after configuring your own publisher identity and Registry secret.
