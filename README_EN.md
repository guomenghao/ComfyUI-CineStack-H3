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

Initial independent version 0.1.0. CPU and browser fixture regression tests are provided.
Actual ComfyUI and GPU/model generation acceptance remains pending; Registry publication is not yet completed.
Publication is manually triggered after configuring your own publisher identity and Registry secret.
