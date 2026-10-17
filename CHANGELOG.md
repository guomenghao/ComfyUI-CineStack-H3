# Changelog

## Documentation update — 2026-10-17 (package remains 0.6.10)

- Reorganize Chinese and English homepages around selective rework, approved first-pass refinement and complete delivery. Add production-oriented walkthroughs, file-output wiring and explicit capability limits.
- Move the former homepage release notes into the bilingual archive below; retain the existing chronological engineering history.
- Document companion DLSS 0.2.1 cadence/audio validation. DLSS is installed and updated separately; this is not an H3 runtime change or a GPU quality benchmark.
- No code, workflow, cache identity or Registry publication changes.

## 0.6.10 — 2026-10-16

- Preserve rolling, disk mode, diagnostic and manifest output fields when loading saved timelines. Flush current editor state during API serialization as well as queue submission.
- Preflight compares serialized execution/rolling/export settings with the editor and rejects ordinary-mode file VIDEO connections with an explicit Enable rolling action.
- Backend validates file VIDEO links before Director preparation/sampling; consumer topology invalidates Comfy output reuse without changing any disk-cache fingerprint or file. Legacy IMAGE workflows and strict-refine/continuity/rolling behavior remain.
- Add browser round-trip/queue tests and backend guard/compatibility tests. No Registry publication.

## 0.6.9 — 2026-10-16

- End-of-inference model handoff: drain internal sampler buffers, unload via ComfyUI, synchronize and release reloadable host pins before export allocations.
- Normal merged IMAGE exports return segment views into merged storage, avoiding duplicate retention in the downstream node cache. Source and first-pass cache files remain unchanged.
- Added model-release and frame-handoff diagnostics; rolling, seeds, strict refine and connected boundaries retain existing interfaces.
- Companion DLSS 0.2.0 streams VIDEO-only output through one worker and a frame-sized encoder. No Registry release.

## 0.6.8 — 2026-10-16

- Fix standard All export seam/concatenation peaks: allocate one destination, copy each native-size clip into its centered output view, then correct seams in owned storage. Avoid whole-clip additive-luma clones and the accumulated corrected-clip list. Preserve source/cache tensors, mixed-size/dtype behavior, disconnected boundaries and output layout.
- Enable standard All export memory diagnostics by default, in a separate diagnostics-only directory. Trace output allocation requests, per-segment copy and seam boundaries, output branches and final merge. Finish progress only after merge succeeds. Explicit diagnostic opt-outs remain supported.
- Add pixel-equivalence, allocation-bound, alias/mixed-shape, failure-path, independent-seed/strict-refine, cache-integrity and executor diagnostic regressions. Normal IMAGE export still needs complete-film RAM; no guarantee for downstream DLSS or real GPU peak usage. No Registry publication.

## 0.6.7 — 2026-10-15

- Append separate file-backed first/final VIDEO outputs after the original eight ports. Return structured completed-file UI metadata and show lazy native preview, direct download and server location in the Director workbench. Preserve old links and ordinary IMAGE/AUDIO behavior; feature-detect older host video APIs.
- Full rolling exports expose full-timeline files; selected exports expose only executed ranges. Partial final/refine runs additionally compose a full first-pass comparison from validated saved ranges when available. Missing comparison sources are explicit and never regenerate or substitute partial footage. Preserve the actual pre-face first pass when face refinement is the only final operation.
- Add disk-delivery and real-browser regressions for scopes, strict refinement, missing stages/files, port compatibility, lazy media lifecycle, downloads and unsafe locators. No full-frame rehydration and no Registry publication.

## 0.6.6 — 2026-10-15

- Apply ComfyUI prefetch/cast buffer cleanup after each internal sampling pass, including exceptions, while patchers remain reachable. Release dynamic patch host buffers before optional model unloading; preserve base-weight pins and older-host fallback. Cover first/refine/SelfLift through their common sampler.
- Add bounded per-model weight/patch HostBuffer and registered-pin counts, Comfy pinned totals, optional PyTorch host allocator statistics, cast/prefetch cache counts and pre/post cleanup checkpoints. Keep telemetry read-only and isolate run context on exit.
- Add CPU lifecycle, seed/output, failure, compatibility, ownership and diagnostic regressions. Preserve strict refinement, rolling export, continuity and workflow/cache identities. Real GPU host allocation/residency acceptance remains pending. No Registry publication.

## 0.6.5 — 2026-10-14

- Release obsolete decoded RGB aliases after opening grade, before seams, cache writes and export. Reuse owned export buffers for additive opening luma instead of cloning full clips again. Keep the initial grade isolation copy.
- Deduplicate identical cropped views by storage, offset, shape, dtype and stride. Preserve isolation for distinct guides/views, missing-guide consumers, cached frames and buffers also used as guides. Preserve functional defaults for legacy callers.
- Add postprocessing memory checkpoints and tests for pixel equivalence, 277-frame clone bounds, alias isolation, decoder lifetime and partial traces on seam failure. Preserve rolling export, independent seeds, strict refinement and continuity. No Registry publication.

## 0.6.4 — 2026-10-14

- Enable read-only memory diagnostics by default for rolling generation. Write bounded console summaries and per-run JSONL observations across conditioning, sample/cache reuse, refinement passes, decode, encode, cleanup and merge. Keep partial traces on exceptions.
- Count supplied backing tensor storages once across aliases and slices; report category totals, largest allocations, incomplete traversal, process RSS/anonymous/file/swap, available glibc counters, cgroup usage and model record counts. Do not retain tensors, read tensor contents, synchronize CUDA, force allocator trimming or change model unloading.
- Preserve old workflow defaults, seed/cache identities, strict refinement and rolling continuity. Clarify the old release message as reference removal, not proof of returned RAM. Add diagnostic unit/executor regressions. No Registry publication.

## 0.6.3 — 2026-10-14

- Replace the execution dropdown with visible, keyboard-accessible First pass / Second pass / Follow graph buttons and a run summary. Preserve legacy timeline values and wired Refine settings.
- Show actionable rolling-All/confirm-first conflicts before queuing; offer explicit stage changes, cache retries and problem-segment details. Recovery never automatically starts generation.
- Apply preflight to the main ComfyUI Run entry as well as the workbench; honor output dependencies and partial-run targets, skip inactive nodes, recheck strict caches and cancel on settings changes. Keep backend validation and improve its recovery instructions.
- Add browser and backend regressions; retain versioned frontend resources. No Registry publication.

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


## Archived homepage release notes / 原首页版本说明

These notes describe their respective release dates; consult the current README for present-day usage. 以下保留当时的修复说明，当前使用入口见 README。

<details>
<summary>中文版本说明（原首页）</summary>

## 工作流设置与文件接线检查（0.6.10）

修复重新载入工作流时丢失滚动生成、低内存和诊断设置的问题。保存/API 导出时同步编辑器最新设置；提交前检查实际执行方式、滚动和导出方式是否与界面一致。

`first_pass_video` / `final_video` 是滚动文件输出。普通模式接这两个端口时，运行前明确提示，并提供“开启滚动生成”按钮；不会自动切换或生成。绕过前端时，后端在导演台准备/采样前报错。原 IMAGE/AUDIO 工作流继续使用旧行为。已有一采要只跑二采时，请明确选择“仅二采”，不要依赖“跟随工作流”的缓存自动选择。详见 [设置与接线检查](docs/submission-settings.txt)。

## 导演台 → DLSS 内存交接（0.6.9）

生成完成后，先通过 ComfyUI 卸载模型并释放可重新加载的动态 host/pinned 缓冲，再合并视频；合并后的分段输出共享整片存储，避免下游缓存再保留一套分段像素。阶段日志新增 `export_model_release_*` 和 `export_frame_handoff_after`。

配合 [DLSS 插件 0.2.1](https://github.com/guomenghao/ComfyUI-DLSS-NeuralRender-Linux)，只连接 DLSS 的 VIDEO 输出时自动逐帧处理并输出文件视频。0.2.1 修复临时封装导致帧率漂移、视频加速及音轨截短的问题；**必须更新 DLSS 仓库，仅更新导演台不包含该修复**。普通 IMAGE 工作流仍保留整片张量；需要随段数保持较低内存时，使用「全部导出＋滚动生成」，将导演台 `final_video` 直接接到 DLSS `video`，`first_pass_video` 单独接 SaveVideo。详见 [交接说明](docs/dlss-handoff.txt) 和 [时间轴与分阶段保存](docs/dlss-timing-0.2.1.txt)。

## 普通全部导出内存修复（0.6.8）

普通模式合并改为一次分配最终画面，再在输出中修正接缝；避免为开头 12 帧累积整段副本。保留输入画面和已有缓存，结果与旧算法逐像素对比验证。普通全部导出默认增加阶段内存诊断，保存在 `output/cinestack_diagnostics/<时间_运行ID>/memory_diagnostics.jsonl`。

普通 IMAGE 输出仍需要整片画面驻留内存；超分、NR、补帧的内存由下游插件管理。长片仍建议使用滚动生成和文件 VIDEO 输出。参见 [普通合并与诊断](docs/standard-merge-memory.txt)。

## 滚动视频保存与预览（0.6.7）

滚动生成完成后，在导演台 **分段工作台 → 滚动视频 · 最近完成结果** 分别查看一采和最终视频，点击 **预览视频** 或 **下载到本机**；展开 **服务器保存位置** 可查看已有文件位置。

需要使用保存视频节点时，直接连接导演台新增的 **一采视频 · 文件（first_pass_video）** / **最终视频 · 文件（final_video）** 到官方 **SaveVideo** 的 VIDEO 输入。两路分别连接两个 SaveVideo，并设置不同文件名前缀；格式与编码选择 `auto`。不经过 CreateVideo，也不要使用需要 IMAGE 输入的 Video Combine。这是对已保存 MP4 的文件传递，兼容流时只重新封装，不把整片帧加载成张量。

全部导出提供完整时间轴；分段导出只提供本轮选中段。仅一采的最终入口明确显示未生成。局部二采可复用各段已有一采视频合成完整对比片，若一采文件不足会列出缺失段，保留最终片并阻断一采 VIDEO 口，不偷偷生成或用部分视频冒充全片。原 8 个输出位置不变；普通模式继续使用旧 IMAGE/AUDIO 接线。详见 [接线与验证](docs/rolling-video-delivery.txt)。

## 采样阶段 Host/pinned 缓冲区修复（0.6.6）

补齐导演台内部每次采样后的 ComfyUI 预取与 cast 缓冲区清理：在动态模型仍可访问时释放临时补丁 HostBuffer，保留基础权重 pinned 缓存及原模型卸载策略。一采、二采/N采和 SelfLift 共用此路径，异常退出也执行；不依赖是否勾选段间卸载。

新增 `sampler_execute_before/after` 与 `sampler_buffers_before/after`，区分基础权重、补丁 HostBuffer、Comfy 注册 pinned、PyTorch host allocator 和底层预取/cast 缓存。更新后重启，按原 19 段配置复跑并收集 JSONL，以核实实机释放量。代码已定位缺少的生命周期步骤，实际约 1.7 GiB 增量的全部归属仍待新日志确认。见 [原因、证据与验收](docs/host-memory-lifecycle.txt)。

## 后处理内存峰值修复（0.6.5）

滚动／低内存生成时，色调匹配保留必要的一份独立导出副本；随后释放过期解码引用，开头 12 帧的亮度接缝修正直接复用该副本，避免再次复制整段画面。相同裁剪视图的重复分支只处理一次；不同引导、不同视图或借用的一采缓存仍保留隔离，避免串改画面。

新增 CPU 转换、色调匹配、原始画面引用释放、修脸、接缝、缓存／边界保存和导出阶段诊断。旧工作流无需修改，独立 seed、仅二采、连接线约束及滚动导出规则不变。此修复针对已确认的临时副本峰值，不保证 64 GiB 环境承载任意模型／分辨率，也未将 CPU 回归视为真实 19 段 GPU 验证。见 [验证记录](docs/retest-0.6.5-2026-10-14.txt)。

## 阶段级内存诊断（0.6.4）

滚动生成默认启用只读诊断，无需修改旧工作流。控制台搜索 `CineStack MEM:`，每次运行的输出目录同步保存 `memory_diagnostics.jsonl`，中途异常也保留已有记录。更新并重启服务后复跑，将该文件与生成日志一起提供即可。

诊断记录条件编码、一采/缓存复用、精修轮次、VAE 解码、持续编码、引用清理及合并阶段的内存变化；统计导演台可见的底层张量存储并去重，补充 Linux 匿名/文件内存、glibc 分配器、容器内存及模型管理记录数量。不会主动卸载模型、调用 malloc_trim 或改变采样。统计范围和日志读法见 [内存诊断说明](docs/memory-diagnostics.txt)。这次增加定位能力，不宣称已修复真实模型的 RAM 增长。

## 执行按钮与运行前提示（0.6.3）

导演台时间轴上方的「分段工作台」现在直接显示 **仅一采 / 仅二采 / 跟随工作流** 三个按钮，选中状态可见；旁边是「检查并运行」。本轮段数、滚动生成和导出范围也会显示。

- 旧工作流保留原执行方式；「跟随工作流」就是原来的「按原接线」，不会自动改成一采或二采。
- 「滚动生成＋全部导出」遇到「先确认一采」时，界面提前说明冲突，提供「改为仅一采 / 改为仅二采」。这些按钮只修改设置，不自动提交任务。
- 仅二采缺少或失配缓存时，可点击「查看问题段」展开差异，或「重新检查缓存」；不会自动重跑一采。
- 工作台与 ComfyUI 顶部运行均接入预检查；标准图中未参与输出、静音/绕过及局部运行范围外的导演台不会阻挡其他任务。后端仍执行完整校验，浏览器缓存检查不能替代 latent、连接数据等运行时校验。

更新后重启 ComfyUI，再刷新浏览器。没有发布到 Comfy Registry。

## 前端缓存更新（0.6.2）

影栈脚本及其依赖使用 `v版本号-内容指纹/文件名.js` 路径，更新后自动避开旧固定地址的代理/浏览器缓存。请先 `git pull --ff-only`，再重启 ComfyUI、刷新页面。版本接口还会返回 `frontend_asset_version`，可与 `/extensions` 返回的资源路径核对。见 [前端缓存验证](docs/frontend-cache.md)。

## 工作流版本显示（0.6.1）

旧工作流打开、新建或粘贴影栈节点时，节点版本标记会同步为当前 ComfyUI 服务加载的插件版本。保存工作流后会保留更新后的标记；seed、参数和连线不变。更新代码后需重启 ComfyUI，再刷新浏览器并重新打开工作流。版本接口不可用时保留原标记并输出浏览器警告，不猜测版本。

可在服务器执行 `curl -fsS http://127.0.0.1:8188/cinestack/h3/version` 核对运行版本（端口按实际设置调整）。此版本号不代表已经发布到 Comfy Registry。详见 [迁移说明](docs/migration.md)。

## 连接线与局部重做（0.6.0）

开启“段间引导”，只勾选第 4 段重做一采：3—4 相连时读取第 3 段导出尾部；4—5 相连且第 5 段未选中时，用第 5 段导出首帧约束第 4 段结尾。断开哪侧，就取消哪侧的接点约束。连线优先于手动首尾图。连续选中多段时组内顺序生成，只有组选区边界读取未选邻段。缺缓存会提前列出段号和左右接点，不自动重跑邻段。

未选邻段只读取首尾小缓存（左侧通常 22 帧、右侧 1 帧），不整段加载/解码邻段 AV。旧 RGB 缓存用 mmap/FFmpeg 读取区间，已有滚动视频用索引定位；旧版若只剩 AV 且没有可读的视频/画面缓存，需要恢复对应结果或明确重做邻段。仅二采保留当前段一采时的约束快照，改变连接线须先明确重做一采。旧工作流不改变节点 ID 或控件位置，原连线字段继续有效；旧一采缓存可继续二采，但不会追补原本没有的右侧约束。

右侧目前是画面首帧约束，不是未来音频或运动窗口的反向生成。画面动作、声音接缝仍需 GPU 实测验收。详见 [使用与兼容说明](docs/bidirectional-junctions.txt)。

## 滚动生成与完整导出（0.5.0 起）

开启 **滚动生成（当前段＋上一段）**，再选择导出方式：

- **全部导出＋滚动生成**：只生成勾选段，按时间轴顺序复用未选段已有视频，输出 `timeline_first_pass.mp4`（仅一采）或 `timeline_final.mp4`（仅二采/自动最终结果）。
- **分段导出＋滚动生成**：只输出本轮勾选段，沿用 `first_pass.mp4` / `final.mp4`；不会补齐未选段。

首次复用 0.4.x 已有整片时，在“旧版完整结果 manifest（可选）”填写服务器上对应的完整滚动输出目录或 `manifest.json` 路径。新版本之后按同一缓存名和节点自动记录；不要删除被复用的源视频目录。缺少阶段、文件丢失、身份不符时会说明段号并停止，不自动生成其他段。

采样保留当前段和上一段的必要数据，整片合并由 FFmpeg 从磁盘逐区间处理，不把全部画面加载到 Python 内存。部分重做的整片导出需要读取和重编码视频，有额外 CPU/磁盘耗时；不是零成本拼接。
独立 seed、严格仅二采继续保留；完整 IMAGE/AUDIO 接口阻断，使用报告中的文件路径。未选段不重算接缝，替换段两侧需要检查连贯性。
未开启滚动的旧工作流和旧低内存模式保持原导出方式；连接线使用上述接点语义。已开启滚动且选“全部导出”的旧工作流会采用新的完整导出语义。详见 [滚动说明](docs/rolling-generation.txt)。

## 低内存落盘（0.3.0）

在输出设置中勾选 **低内存落盘**，逐段保存视频和一采缓存，保留必要的上一段连贯数据后释放旧段画面；从磁盘分别合并一采/成片。
**此模式只交付本轮勾选段，并阻断完整 IMAGE/AUDIO 输出口。** 视频和 `manifest.json` 位于报告中的 `output/minimax_seg_export/时间戳/`；下游无需再用 CreateVideo/SaveVideo 保存。
每段独立 seed、仅二采和 22 帧连贯保留。开关默认关闭，关闭后继续原导出方式；已有工作流不会自动改变。
详见 [低内存使用说明](docs/low-memory-mode.txt)。


</details>

<details>
<summary>English release notes (former homepage)</summary>

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


## Low RAM disk delivery (0.3.0)

Enable **Low RAM · save to disk** in Director output settings. It persists selected clips and first-pass AV caches, retains predecessor continuity data until consumed, then releases old RGB storage. First/final stages merge from disk.
Full IMAGE/AUDIO sockets are blocked in this mode; use the file paths and `manifest.json` in the report. Only checked segments are delivered. Fixed seeds and strict second-pass reuse remain supported. The toggle defaults off for legacy workflows.
See [disk-mode details](docs/low-memory-mode.txt). Real GPU/server memory acceptance remains pending.

</details>
