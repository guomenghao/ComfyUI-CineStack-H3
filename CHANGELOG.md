# Changelog

## 0.6.2 — 2026-10-14

- Serve all frontend modules and assets from one immutable version-and-content-fingerprinted directory discovered through ComfyUI WEB_DIRECTORY. Fixed old URLs are no longer advertised, so stale proxy/browser copies cannot mix with new dependencies.
- Keep relative plugin dependencies in the same versioned tree and normalize host app/api imports to canonical ComfyUI URLs, avoiding duplicate module instances. Build in OS temporary storage without modifying installed sources or workflows.
- Expose frontend_asset_version in the running version endpoint. Add real-browser stale-cache/discovery tests and checks for nested imports, fingerprints and process-lifetime snapshots. No Registry publication.

## 0.6.1 — 2026-10-14

- Read the installed package version from pyproject.toml once at server startup and expose it through a non-cacheable /cinestack/h3/version endpoint. Updating files without restarting cannot falsely report the new runtime version.
- Refresh version metadata for existing CineStack workflows, legacy migrations, nested graphs, newly created nodes and pasted nodes. Preserve seeds, inputs, links and unrelated/upstream nodes; retain saved metadata if the version endpoint is unavailable.
- Remove hard-coded migration versions from both browser and CLI paths, refresh bundled examples, and validate example version alignment during release checks. No Registry publication.

## 0.6.0 — 2026-10-14

- Interpret existing timeline links as junction constraints: previous exported tail and unselected next exported head for partial first-pass rebuilds; selected islands remain sequential. Disconnected edges skip both conditioning and rolling seam processing.
- Preflight missing neighbour boundaries before cache pruning/sampling. Add bounded exported head/tail sidecars; mmap legacy RGB or stream exact indexed video ranges. Never hydrate whole unselected neighbour AV/pixels for junctions.
- Freeze right endpoint pixels in first-pass AV and both link states in handoff metadata. Strict refinement reuses its own confirmed prefix/right lock, re-encodes the right lock after upscale, and rejects changed links or corrupt snapshots without first-pass fallback. Preserve legacy workflows and legacy first-pass cache readability.
- Connected edges take precedence over manual stills; retain manual endpoints only on unconnected sides during upscale. Update Chinese/English tooltips and cache diagnostics. No Comfy Registry publication.

## 0.5.0 — 2026-10-14

- Honor All export + Rolling as full-timeline disk composition: generate only selected segments and reuse saved video ranges for all unchecked segments. Segment export + Rolling still delivers only selected segments.
- Atomically maintain per-cache video provenance, stage/range metadata and file stamps after successful delivery. Reject missing, mismatched or modified unchecked results before sampling; never fall back to regeneration or mix first/final stages.
- Add explicit 0.4.x full rolling manifest import when no indexed result exists. Preserve origin metadata and explain the older format’s identity-validation limits.
- Assemble consecutive saved ranges with bounded FFmpeg buffers, frame-index cuts, continuous PCM timing and final video stream copy. Never build a full IMAGE tensor. Full exports are timeline_first_pass.mp4 or timeline_final.mp4.
- Preserve unselected predecessor handoff records and saved video lengths; retain selected-segment continuity and strict per-segment seeds. Report full frame counts, generated/reused sources and seam-review boundaries.
- Restore All/Segment selection in rolling UI, add bilingual scope explanations and an optional legacy manifest path. Retain manual-only Registry publishing. See docs/rolling-full-export.txt for migration, costs and validation.

## 0.4.1 — 2026-10-14

- Release per-segment file-backed reference PCM again after deferred rolling export, including failures; preserve shared/global audio slots. Fix accumulation when source/fallback audio is rematerialized after sampling cleanup.
- Validate strict first-pass handoff frame fields before any batch refinement. Reject strings, fractions, booleans and negative frame values with segment/field diagnostics; retain legacy missing-field compatibility.
- Close encoder logs and clear WAV handles even if audio finalization fails (for example, disk full).
- Add seven regressions for real reference-audio export/release, invalid later handoffs, disk-full cleanup, nonadjacent selection, cancellation/shared slots, fractional FPS/odd canvases and 20 refined segments with bounded pixel retention.
- See docs/retest-0.4.1-2026-10-14.txt for verification scope and remaining hardware limitations.

## 0.4.0 — 2026-10-14

- Add optional `output.rollingGeneration`, with current/predecessor working data and no full-timeline RGB concat. Preserve the 0.3.0 disk mode and legacy defaults.
- Delay predecessor output until successor guidance, phase trimming and seam correction finish. Continuously encode each stage, then mux audio with video stream copy. Reuse encoding when unrefined first/final output is identical.
- Persist first/final AV and handoff data, skip full RGB caches, avoid intermediate refine-pass decoding/MP4 export, and update only small metadata/PCM after phase trimming.
- Preserve committed first-pass phase cuts during strict second-pass reuse. Reconstruct only the required predecessor from AV for partial runs without RGB caches.
- Keep exact independent seeds, strict mismatch rejection, selected-run scope, face-before output and external-group/pack settings. Report partial stage output explicitly rather than mixing first/final stages.
- Close continuous encoders on exceptions/interruption; retain first AV caches and available Matroska/PCM fragments. Final MP4s require successful completion; GPU/RSS/wall-time acceptance remains device-specific.
- Add real FFmpeg, 20-segment bounded-storage/one-encoder, continuity pixel/length, first-to-second phase, audio, geometry, partial-run, failure and browser regressions. See docs/rolling-generation.txt.

## 0.3.0 — 2026-10-14

- Add opt-in `output.lowMemoryMode` (default off) across Director UI, external groups and packs. Existing positional widgets, node IDs and normal output behavior remain intact.
- Deliver selected segments to disk, with atomic AV persistence before RGB decode, per-frame MP4 conversion, disk-only first/final merges and a manifest containing exact per-segment seeds.
- Block full IMAGE/AUDIO sockets in disk mode; keep FPS/count/report outputs. Explicitly report file-only delivery and selected-only scope in Chinese and English.
- Keep predecessor frames/AV/audio until continuity and phase trimming finish; apply the original seam operations per pair and release old full-frame storage. Flush intermediate refine passes without retaining their RGB batches.
- Stop on cache/video write failure, unavailable FFmpeg or refinement failure in disk mode; retain successful first AV results even when later decoding fails. Never regenerate first passes on strict cache mismatch.
- Remove redundant first-pass confirmation decode in disk mode; drop stale RGB previews when replacing an AV cache without pixels.
- Add real codec, bounded storage, 22-frame continuity, seam pixel comparison, legacy compatibility and browser toggle regressions. See docs/low-memory-mode.txt for file layout, output semantics and hardware validation limits.

## 0.2.1 — 2026-10-14

- Include active segment LoRA order, exact strengths and file size/mtime in first-pass and final cache identities. Empty/disabled stacks retain legacy metadata compatibility; old active-stack caches require an explicit first-pass rebuild.
- Make strict second-pass sampler failures propagate with segment/cause instead of returning first-pass or partial-pass output. Preserve the legacy fallback when strict mode is off.
- Preserve explicit zero CFG/shift values in metadata and inspection; reject malformed/nonfinite/negative wired SIGMAS instead of silently ignoring them or falling back to another first-pass schedule.
- Lock submission before async preflight, reject stale settings and mode changes, and stop claiming success when the Comfy queue API returns false.
- Refresh workbench status for Refine changes; share cycle-safe Reroute resolution with the Refine panel. Disable inaccurate numeric-global-seed pinning and fit narrow nodes using container queries.
- Run full CPU discovery (including audio host adapters), install FFmpeg on CI, and require CPU/browser CI before the manual publishing job. No publication was triggered.
- Add review regression tests and document remaining model/media identity and GPU validation limits in docs/review-2026-10-14.txt.

## 0.2.0 — 2026-10-14

- Add a collapsible Director segment workbench with navigation, thumbnails, frame duration and checked-run scope.
- Show inherited versus fixed effective seeds; support fixing the current value, exact uint64 input and synchronized original card controls.
- Show per-segment first-pass metadata and rendered-cache existence; include bounded cached/current mismatch values and reject stale UI requests.
- Add optional `executionMode` in timeline JSON: legacy (default), first pass only, strict cached second pass only. No positional widgets or node IDs change.
- First pass only skips Refine/FaceRefine and always writes a first-pass cache, including inherited seeds. Second pass only validates before sampling/pruning.
- Preserve execution intent through external groups and Director pack round trips; retain ComfyUI queue semantics and graph connections.
- Add real-editor browser interaction coverage and CPU execution-mode regression checks. GPU generation remains pending.

## 0.1.1 — 2026-10-13

- Fix official ComfyUI H3 imports in conditioning, both SigmaShift sampling paths
  and SelfLift: external module names remain `comfy_extras.nodes_minimax_h3`.
- Restore the third-party `sol_attn_minimax_v5` identity used by continuity compatibility checks.
- Include the original dependency import error in conditioning failures.
- Add CPU regression checks for official conditioning/sampling entry points and external identities to CI.

The fix addresses the reported Node 56 import failure on ComfyUI 0.39.2.
CPU host fixtures verify dispatch; GPU generation still requires validation on the user's device.

## 0.1.0 — 2026-10-13

Initial independent CineStack H3 release, derived from AIMixer Director commit
`8151b291fcacee5ddb70c6493eaed4f831bc6867`.

- Optional fixed `first_pass_seed` per segment, including zero and the full uint64 range.
- Seed persistence through all timeline modes, external groups and Director packs.
- `refine_only`: preflight selected first-pass caches; reject missing, mismatched or corrupt caches before sampling.
- Detailed cache mismatch diagnostics; inherited seed behavior and legacy cache layout preserved.
- `CineStackH3Director*` node IDs, `/cinestack/h3/*` routes and CineStack progress events.
- Legacy workflow/API migration with preserved widgets, seeds, graph IDs and links.
- Independent Registry metadata, manual publication workflow, CI and publishing guide.

Validation covers CPU control flow and browser UI fixtures. GPU model generation and
live ComfyUI integration still require release acceptance on a compatible NVIDIA host.
