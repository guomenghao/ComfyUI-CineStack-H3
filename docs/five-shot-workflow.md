# 五段独立 seed、仅二采与滚动导出 / Five-shot workflow

适用 CineStack H3 0.6.11。提供可导入的设置模板，不包含素材、权重、缓存或已生成影片。提示词有意留空：先填写自己的五段内容、选择本机模型，再运行。CPU/浏览器结构验证不代表 GPU 效果验收。

## 文件与接线

- [五段一采模板](../example_workflows/cinestack_five_shots_first_pass.json)：全部段、仅一采、全部导出、滚动生成。
- [五段仅二采设置模板](../example_workflows/cinestack_five_shots_refine_only.json)：相同节点 ID、段 ID、缓存名、五个独立 seed，仅执行方式不同。它用于对照设置；**实际制作请在已经填写提示词的同一个工作流内切换按钮**，不要用此空白模板覆盖已有内容。

五个 seed 为 `561215411` 到 `561215415`，全局 seed 的生成后操作为 `fixed`。每段 124 帧、24 fps、864×480；名义 5 秒对应实际约 5.17 秒，五段时间轴约 25.83 秒。默认“保完整”会保留段间引导网格增加的帧，成片可能更长（四处各多 12 帧时约 27.83 秒）；最终以导出文件元数据为准。

两个文件端口直接接官方 `SaveVideo`：

| 导演台输出 | 用途 | 保存前缀 |
|---|---|---|
| `first_pass_video`（一采视频 · 文件） | 一采完整视频 | `video/CineStack_five_shot_first_pass` |
| `final_video`（最终视频 · 文件） | 二采最终视频 | `video/CineStack_five_shot_final` |

SaveVideo 格式和编码都选 `auto`，音频随 VIDEO 文件保留。没有 CreateVideo、整片 IMAGE、DLSS 或补帧支路。滚动模式仍需当前段解码内存和编码磁盘空间，并非零内存。`images` 等传统输出口在此模式下阻断；已有普通模式接线仍可使用。

Refine 预设为同分辨率精修、一次 pass。SIGMAS 来自 `MiniMaxH3SigmaShift → BasicScheduler`，与导演台共用主模型；25 steps、denoise 0.3 是待按素材验收的示例设置，不保证画质提升。没有要求下载 latent upscaler 或 Turbo LoRA。

## 实际操作

1. 导入一采模板，选 UNET、CLIP、视频/音频 VAE；CLIP 类型为 `minimax`。填写五段提示词，并另存自己的工作流。保持导演台 ID 和 `cache_name`；新项目应另取缓存名，避免混用示例缓存。
2. 确认五段独立 seed、四条连线、滚动勾选和“仅一采”按钮。执行前看摘要：5 段、滚动生成、全部导出。首次运行建立缓存；若提示缺邻段缓存，按提示检查选段范围与连线，不切换仅二采绕过检查。
3. 一采满意后，在**同一工作流**点击“仅二采”，点击“检查缓存”。不改五段 seed、提示词、参考、帧数、模型、一采参数或缓存名。匹配后再运行。缓存失配应列原因并停止，不能自动重跑一采。
4. 全部二采完成后，只重做第 3 段：运行范围改“勾选段”，仅勾第 3 段；修改它的 seed 或内容，点击“仅一采”。第 2、4 段有有效缓存且连线连接时提供前后边界；断开哪边就不使用哪边。不能保证修改后的画面天然无缝，仍需观看验收。
5. 第 3 段一采满意后，不再改 seed/内容，点击“仅二采”。保留“全部导出＋滚动生成”：只重采第 3 段，其他四段读取已有导出结果拼完整片；缺失/失配时停止，不补跑未选段。原一采视频和最终视频在各自入口预览/另存。
6. 如只需交付第 3 段，改“分段导出＋滚动生成”。此时只导出勾选段；不要把它当作完整五段影片。

## 验收记录（后续 GPU 操作）

记录机器、ComfyUI/前端/插件版本、模型和五段有效 seed；保存任务 ID、服务日志与 `memory_diagnostics.jsonl`。检查一采与二采输出帧数/FPS/音轨，观察接缝；重做第 3 段时确认其他段没有采样日志。比较每段清理后的 RSS 与合并峰值，而非只看某个瞬间。此版本准备工作不执行这些生成测试。

## English quick start

Import the first-pass JSON, select local H3 model files and fill all five prompts. Save your working graph. Seeds are independently fixed to 561215411–561215415. Run all five in **First pass + All export + Rolling**. After approval, switch the button to **Second pass only in that same graph**; do not overwrite populated prompts with the empty companion template. Check cache before queuing.

After all five final results exist, select only clip 3, change only its intended settings, rebuild its first pass, then approve and run second pass only. Connected clips 2/4 supply cached boundaries; missing required caches must stop with a reason. All export reuses other saved results to build a complete video; Segment export outputs only the selected clips. Two file VIDEO ports connect directly to SaveVideo (`auto`/`auto`) with audio. No full-film IMAGE conversion is needed. GPU quality, continuity and peak-memory acceptance remain pending.
