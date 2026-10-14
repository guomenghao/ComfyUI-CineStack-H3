# Changelog

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
