# CineStack H3

[中文](README.md) · [Migration](docs/migration.md) · [Publishing](docs/publishing.md)

CineStack is a planned local cinematic production workflow platform. This repository is its first H3 generation module for ComfyUI, **not the complete future platform**.

Maintained by **guomenghao**. Source attribution and applicable licenses are documented in [NOTICE](NOTICE) and [the upstream archive](docs/upstream/README_EN.md).

## Workflow version labels (0.6.1)

Existing, migrated, nested, newly created and pasted CineStack nodes now display the package version loaded by the current server. Save the workflow to retain refreshed metadata. Seeds, parameters and links are unchanged. Restart ComfyUI after updating, refresh the browser, and reopen the workflow. An unavailable version endpoint preserves saved metadata and emits a browser warning.

Check the running version with `curl -fsS http://127.0.0.1:8188/cinestack/h3/version` (adjust the port). This is the installed runtime version, not a claim of Registry publication.

## Connected junctions (0.6.0)

With Segment continuity on, rebuilding only clip 4 uses clip 3's exported tail when 3–4 is connected, and clip 5's exported first frame when 4–5 is connected and clip 5 is unselected. Disconnect either edge to remove that constraint. Links override manual start/end stills. Selected islands generate forwards internally; only outside boundaries read unselected neighbours. Missing boundary caches stop with segment/side diagnostics before sampling.

Small exported boundary sidecars hold at most 56 tail frames plus one head frame; reads normally use 22 + 1 frames. Legacy RGB is mmap/range decoded; indexed rolling videos are streamed by frame range. No whole unselected neighbour AV decode. AV-only legacy caches without usable pixels/video need restored output/index or an explicitly requested neighbour rebuild. Strict second pass uses the first-pass constraint snapshot, not edited neighbour results. Changing links invalidates new first-pass snapshots; legacy first-pass caches remain readable without retroactively adding a right constraint.

Right constraints are visual stills, not reverse audio/motion conditioning. GPU, appearance and audio seam acceptance remain pending. Workflow node IDs, seeds, export scopes and manual-only Registry publishing remain unchanged. See [details](docs/bidirectional-junctions.txt).

## Rolling export (since 0.5.0)

Enable **Rolling generation**, then choose the existing export scope:

- **All + Rolling:** sample checked segments only, reuse saved video ranges for unchecked segments, and write `timeline_first_pass.mp4` or `timeline_final.mp4`.
- **Segments + Rolling:** export only checked segments, retaining `first_pass.mp4` / `final.mp4` behavior.

A durable index under the same node/cache key tracks saved stages and ranges. Missing, mismatched or modified results stop the run instead of regenerating unchecked segments. For a 0.4.x full rolling result, explicitly supply its server-side output folder or manifest.json in the optional legacy field; older manifests lack full identity metadata, so verify their segment order and assets. Keep referenced output videos on disk.

Composition reads and re-encodes bounded ranges in FFmpeg and streams PCM, without a full-timeline Python IMAGE tensor. This adds CPU/disk work, not model inference. Unselected video lengths and handoffs are preserved; review replacement seams. Full IMAGE/AUDIO sockets remain blocked. Independent seeds and strict second pass remain supported.

Non-rolling workflows and old disk mode are unchanged. Existing rolling workflows set to All now use full-timeline semantics. See [usage and migration](docs/rolling-full-export.txt) and [rolling internals](docs/rolling-generation.txt). Registry publishing remains manual; GPU acceptance is pending.

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

Version 0.6.1 includes bidirectional junction constraints, rolling generation, low-memory disk delivery, the Director segment workbench, official H3 import fix, and cache/queue/strict-failure review fixes. CPU and real-editor browser fixture tests are provided.

The workbench shows effective seeds, checked run scope, first-pass metadata and rendered-cache existence.
Execution choices are Follow graph (legacy default), First pass only (save first-pass cache; skip refinement/face refinement),
and Second pass only (matching cache required; never regenerate first passes). Queue submits the current ComfyUI workflow.
Execution intent is stored in optional timeline JSON, without changing node IDs, connections or positional widgets.
Cache labels are metadata checks; latent validation still runs before execution. Rendered-cache existence is not proof of a completed second pass.
Actual ComfyUI and GPU/model generation acceptance remains pending; Registry publication is not yet completed.
Publication is manually triggered after configuring your own publisher identity and Registry secret.
