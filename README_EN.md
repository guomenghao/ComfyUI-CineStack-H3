# CineStack H3

[中文](README.md) · [Migration](docs/migration.md) · [Publishing](docs/publishing.md)

CineStack is a planned local cinematic production workflow platform. This repository is its first H3 generation module for ComfyUI, **not the complete future platform**.

Maintained by **guomenghao**. Source attribution and applicable licenses are documented in [NOTICE](NOTICE) and [the upstream archive](docs/upstream/README_EN.md).

## Standard All export memory fix (0.6.8)

Allocate the combined image buffer once and correct seams in its owned views instead of retaining corrected whole-clip copies. Source tensors and cache identities remain unchanged. Standard All export now records allocation, copy and seam diagnostics under `output/cinestack_diagnostics/<time_run>/memory_diagnostics.jsonl`. IMAGE delivery still requires full-film RAM; use rolling file VIDEO outputs for long timelines. Downstream SR/NR/interpolation memory is outside this fix. See [details](docs/standard-merge-memory.txt).

## Rolling video delivery (0.6.7)

The Director workbench now shows separate first-pass/final file previews, downloads and server locations. Two appended VIDEO outputs (`first_pass_video`, `final_video`) connect directly to official SaveVideo; use different filename prefixes and format/codec `auto` to preserve compatible streams. No CreateVideo or IMAGE-based Video Combine is needed. The original eight output indices stay unchanged.

All export delivers the full timeline, while Segment export delivers only selected segments. An unproduced stage is explicitly unavailable. Partial refinement can compose the full first-pass comparison from saved ranges; missing first-pass files block only that comparison, never trigger first-pass generation or masquerade selected-only video as a complete film. See [delivery scope and checks](docs/rolling-video-delivery.txt).

## Sampling host/pinned buffer lifecycle (0.6.6)

Run ComfyUI's prefetch-then-cast cleanup after every internal sampling pass, including failures, before dropping model patchers or optional unloading. Dynamic patch HostBuffers are released while base-weight pin caches and unload policy remain intact. First/refine/SelfLift calls share this path. Older hosts feature-detect the APIs.

New sampler checkpoints report separate Comfy pinned, per-model weight/patch HostBuffers, optional PyTorch host allocator statistics and cast/prefetch counts. This fixes a confirmed lifecycle omission; attribution of the entire observed ~1.7 GiB/segment needs the next real-server trace. See [evidence and acceptance](docs/host-memory-lifecycle.txt).

## Postprocessing memory peak fix (0.6.5)

Rolling/disk generation reuses the isolated export buffer produced by opening grade for the 12-frame additive seam correction, releasing obsolete decoder aliases beforehand. Identical cropped views are deduplicated; different guides/views and borrowed cached inputs remain isolated. Legacy functional callers keep their input-preserving behavior.

New diagnostic checkpoints bracket CPU conversion, opening grade, reference release, optional face refinement, seams, segment/boundary caches and export staging. Seeds, strict refinement, junctions and old workflow defaults remain unchanged. This removes a verified temporary-copy peak; real GPU/RAM validation on the user's 19-shot workload is still required. No Registry publication.

## Stage memory diagnostics (0.6.4)

Rolling generation now enables read-only stage observations by default. Search the console for `CineStack MEM:` and collect `memory_diagnostics.jsonl` beside this run's output. The trace covers conditioning, sampling/cache reuse, refinement passes, decode, stream encoding, reference cleanup and merge. It reports process memory, deduplicated visible tensor storages, available glibc allocator counters, cgroup memory and model record counts. It never trims allocators, unloads models or changes sampling. These observations diagnose growth; they do not themselves release memory. Set `CINESTACK_MEMORY_DIAGNOSTICS=0` before starting ComfyUI to disable. See [scope and interpretation](docs/memory-diagnostics.txt).

## Visible execution controls (0.6.3)

The segment workbench now offers **First pass only / Second pass only / Follow graph** buttons with a visible selected state, next to **Check and run**, plus the selected segment count and output scope. Existing workflows keep their execution intent.

Rolling All export with legacy confirm-first behavior shows an inline explanation and stage-selection actions before submission. Recovery actions change settings only; they never queue automatically. Strict refinement offers cache retry and per-segment differences without first-pass fallback. Both the workbench and main ComfyUI Run route use preflight; inactive and unrelated standard-graph nodes do not block other outputs. Backend validation remains authoritative, including latent and junction checks. Restart ComfyUI and reload after updating. No Registry publication.

## Frontend cache invalidation (0.6.2)

All plugin modules and dependencies share a `v<version>-<content fingerprint>/` URL directory. Old fixed-URL proxy/browser entries are bypassed after a server restart and page reload. The version endpoint reports `frontend_asset_version`, matching resource paths returned by `/extensions`. Host ComfyUI modules keep their canonical URLs.

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

Version 0.6.8 includes bidirectional junction constraints, rolling generation, low-memory disk delivery, the Director segment workbench, official H3 import fix, and cache/queue/strict-failure review fixes. CPU and real-editor browser fixture tests are provided.

The workbench shows effective seeds, checked run scope, first-pass metadata and rendered-cache existence.
Execution choices are Follow graph (legacy default), First pass only (save first-pass cache; skip refinement/face refinement),
and Second pass only (matching cache required; never regenerate first passes). Queue submits the current ComfyUI workflow.
Execution intent is stored in optional timeline JSON, without changing node IDs, connections or positional widgets.
Cache labels are metadata checks; latent validation still runs before execution. Rendered-cache existence is not proof of a completed second pass.
Actual ComfyUI and GPU/model generation acceptance remains pending; Registry publication is not yet completed.
Publication is manually triggered after configuring your own publisher identity and Registry secret.
