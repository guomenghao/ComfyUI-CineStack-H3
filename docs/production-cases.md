# 影栈制作案例 / Production walkthroughs

[中文首页](../README.md) · [English homepage](../README_EN.md)

以下操作来自项目中的局部返工、内存排查及后处理对比需求。五段场景是便于复现的操作说明，不代表公开展示的完整 GPU 实测，不包含节省时间或画质提升承诺。

## 五段完成，只重做第 3 段

**准备：** 五段已存在可用一采缓存和最终视频；保留相同导演台节点、缓存名及源视频路径。使用独立分段 seed，确认 Refine 模型、SIGMAS 与相关素材就绪。开始前保存工作流副本。

1. 开启滚动生成与段间引导，只勾选第 3 段。保留 2—3、3—4 连接线，修改第 3 段的一采 seed，不改其他段。
2. 选择“仅一采＋分段导出”，检查并运行。左侧读取第 2 段尾部，右侧读取未选第 4 段首帧。若提示边界缓存缺失，恢复对应文件或明确决定重做相关段；不会自动重跑邻段。
3. 从 `first_pass_video` 或工作台预览检查新的一采。尚未满意时继续只改第 3 段。预览确认不等于写入一个自动审批状态，后续阶段由你明确选择。
4. 满意后保持一采 seed、提示词、素材、模型及连接关系等条件，选择“仅二采”。保持只选第 3 段，切换“全部导出＋滚动生成”。
5. 检查其余段最终视频可复用，再运行。第 3 段使用匹配的一采缓存精修，其余段复用已有视频，完整结果从 `final_video` 接 SaveVideo。
6. 看日志确认仅选中段发生采样，检查整片顺序和第 2—3、第 3—4 接缝，以及音轨和总时长。完整合并可能重编码已有视频；“不重采样”不等于“无 CPU/磁盘开销”。

独立 seed 不是缓存唯一条件。仅二采不会因失配退回一采；改连接线应明确重做一采，不能期待二采自动换用新的约束。右侧是静态首帧，不是反向运动/声音窗口。

## 二采满意，只重试后处理

1. 先单独保存 `final_video`，作为二采原片；不要把已发生变速或截短的后处理片当作基准。
2. 在独立后处理图中用 LoadVideo 加载它，不接导演台或模型采样节点。
3. 按需经过 SR、NR、补帧；分别保存阶段结果。使用开关时，阶段保存接在对应开关输出之后，避免被额外保存节点强制执行关闭的分支。
4. 如安装配套 DLSS 0.2.1，最终输出经过 `DLSSNR_VideoTimingGuard`，`reference_video` 接原片、`video` 接处理后视频，再接最终 SaveVideo。
5. 同场景、同时间点对比原片及各阶段。时长检查通过不代表画质一定提高；快速动作尤其需要观察拖影、细节和运动变化。

实际排查中，一个 744 帧、24 fps、31 秒的原片在旧后处理链中变成约 29.77 秒。CPU 复现定位到临时 MKV 的平均帧率被当成输出节奏。配套插件修复后，两次 CPU 文件处理保持 744 帧/24 fps/31 秒和音轨范围。它验证文件交接与时间轴，不是 GPU 神经处理质量验收；并不证明所有时长变化都有同一个原因。

[后处理接线详情](dlss-timing-0.2.1.txt) · [连接线与缓存](bidirectional-junctions.txt) · [滚动整片导出](rolling-full-export.txt)

## English

These walkthroughs reflect actual revision, memory-investigation and postprocessing needs in this project. The five-clip case is a reproducible operating scenario, not a published end-to-end GPU benchmark or a quantified time-saving claim.

### Five completed clips; rework only clip 3

**Prerequisites:** keep usable first-pass caches and final videos for the five clips, the same Director node/cache identity and source paths. Fix seeds individually, configure Refine and SIGMAS, and save a workflow copy first.

1. Enable rolling and continuity. Select only clip 3, keep edges 2–3 and 3–4 connected, and change only its first-pass seed.
2. Choose **First pass only + Segments export**. Preflight and run. The previous tail and the unselected next clip’s first frame supply boundary constraints. Missing data requires restoring files or explicitly choosing a rebuild; neighbours are not automatically regenerated.
3. Review `first_pass_video` or the workbench preview. Repeat only clip 3 if needed. Approval is your decision to proceed, not an automatically recorded approval state.
4. Once satisfied, keep first-pass seed, prompts, assets, models and links unchanged. Choose **Second pass only + All export + Rolling**, still selecting only clip 3.
5. With the remaining final videos available, refine the matching clip-3 cache and compose the whole timeline. Connect `final_video` to SaveVideo.
6. Verify selected-only sampling in logs, segment order, both junctions, audio and total duration. Composition may re-encode existing footage: avoiding resampling does not eliminate CPU/disk costs.

Seed is only one cache condition. Strict refinement never falls back to a new first pass. Changed links require an explicit first-pass rebuild. The right constraint is a still, not reverse motion/audio conditioning.

### Keep the refined original; retry only postprocessing

1. Save `final_video` separately as the refined original. Do not use a shortened/accelerated postprocessed result as the reference.
2. Start an independent graph from LoadVideo, without Director or model-sampling nodes.
3. Apply SR, NR and interpolation as needed; save each stage. With switches, connect each stage’s save after its switch so disabled branches are not forced to execute.
4. With companion DLSS 0.2.1, put `DLSSNR_VideoTimingGuard` before final SaveVideo. Connect the original to `reference_video` and processed video to `video`.
5. Compare the same scenes at matching times, especially motion/detail. A passed timing check does not establish improved picture quality.

In one investigation, a 744-frame, 24 fps, 31-second source became approximately 29.77 seconds. CPU reproduction traced this to treating a temporary MKV’s average frame rate as the output cadence. The companion fix preserved 744 frames/24 fps/31 seconds and audio coverage through two CPU file passes. This verifies transport/timing, not GPU neural-processing quality, and is not a universal explanation for shortened footage.
