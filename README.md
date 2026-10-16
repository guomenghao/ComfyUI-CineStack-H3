# CineStack H3 / 影栈

[English](README_EN.md) · [分段 seed 与仅二采](docs/per-segment-seed-refine-only.md) · [迁移指南](docs/migration.md) · [发布准备](docs/publishing.md)

当前版本 **0.6.8** 支持按连接线对局部重做施加双向接点约束；保留独立 seed、仅二采和滚动整片导出。见 [双向接点与缓存](docs/bidirectional-junctions.txt)。

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

## 导演台分段工作台

导演台内可统一浏览每段缩略图、计划帧数/时长、生效一采 seed 和缓存状态，直接点击片段进入原编辑区。
seed 留空继承全局，填写数字固定本段；“固定当前值”将继承值保存为分段 seed。总览和原卡片输入即时同步。

- **按原接线**：旧工作流默认模式，保留 Refine、确认一采、脸修等原有行为。
- **仅一采**：重新生成选中段的一采并保存 AV 缓存，跳过 Refine 与脸修。
- **仅二采**：需启用并连接 Refine（refine/upscale）及二采 SIGMAS；只使用匹配的一采缓存，失配停止。

“加入 ComfyUI 队列”提交当前工作流。运行范围与原“选择运行”同步；执行方式不修改 Refine 控件或图接线。
缓存标记是元数据检查结果，完整 latent 校验在执行前进行；成片缓存存在不代表已经通过二采。
界面新增设置写在 `timeline_data.executionMode`，不增加位置控件；工作流与导演包保存后保留。

**影栈（CineStack）面向未来的自动化、本地影视制作工作流平台。**
当前仓库是平台的首个 H3 生成模块，以 ComfyUI 自定义节点形式提供多段音视频导演台。
完整独立平台、剧本管理、跨模型调度和自动剪辑属于后续规划，当前版本没有实现这些能力。

项目维护：**guomenghao**。来源、修改范围及授权信息集中见 [NOTICE](NOTICE) 和 [来源说明](docs/upstream/README.md)。

## 当前能力

- 多段 t2v / i2v / fl2v / r2v / v2v / rv2v 时间轴、外部素材组和导演包导入导出。
- 每段独立固定一采 `first_pass_seed`；空白继承导演台全局 seed，`0` 也是有效固定值。
- 严格“仅二采”：只读取匹配的一采缓存，缺失、失配或损坏时列出具体段和原因，停止运行。
- 保留 Refine、SelfLift、Semantic Bridge、FaceRefine 等上游能力；特定功能需要各自模型和依赖。
- 独立 `CineStackH3Director*` 节点 ID、`/cinestack/h3/*` 路由和事件，提供旧工作流迁移。

## 安装

使用支持官方 MiniMax H3 的 ComfyUI（上游最低要求为 0.30.0），在其 Python 环境安装：

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/guomenghao/ComfyUI-CineStack-H3.git
python -m pip install -r ComfyUI-CineStack-H3/requirements.txt
```

Linux 云端环境（ComfyUI 位于 `/root/ComfyUI`）：在运行 ComfyUI 的同一 Python 环境执行：

```bash
cd /root/ComfyUI/custom_nodes
git clone https://github.com/guomenghao/ComfyUI-CineStack-H3.git
python -m pip install -r ComfyUI-CineStack-H3/requirements.txt
```

Git 安装后更新：

```bash
cd /root/ComfyUI/custom_nodes/ComfyUI-CineStack-H3
git pull --ff-only
python -m pip install -r requirements.txt
```

手动复制的同名文件夹请先备份到 `custom_nodes` 外，再首次克隆。安装/更新后重启 ComfyUI，并强制刷新浏览器。

重启 ComfyUI，在 `CineStack/H3` 分类添加节点，或加载 [example_workflows](example_workflows)。
本仓库不包含模型权重、用户素材或 ComfyUI 本体。模型类型及额外注意事项参考
[上游使用说明存档](docs/upstream/README.md)与[官方 H3 教程](https://docs.comfy.org/tutorials/video/minimax/minimax-h3)。

## 五段独立一采，再统一二采

1. 制作一采时关闭 `refine_only`，逐段设置 seed。需要先确认一采时启用 `confirm_first_pass`。
2. 不满意哪一段，只改变该段 seed，并选择运行该段。
3. 全部满意后全选五段，接 Refine 与二采 SIGMAS，启用 `refine_only`。
4. 一采缓存全部匹配后直接二采；全局 seed 的变化不影响已固定分段 seed。

`refine_only` 适用于 Refine 的 `refine` / `upscale`，不适用于只放大的 `latent_upscale`。
FL2V 需要明确关闭 `skip_fl2v` 才能二采。普通模式保持上游自动生成行为。
详细缓存前提和错误示例见[使用说明](docs/per-segment-seed-refine-only.md)。

## 旧工作流与缓存

旧版缺少分段 seed、仅二采字段时继续继承全局 seed、默认关闭仅二采。
只安装影栈时，打开普通旧工作流会在内存中迁移节点 ID，保留节点编号、接线、控件和时间轴。
同时安装原版时，原版工作流仍使用原版；可使用[迁移工具](docs/migration.md)明确转换为影栈。
API prompt 必须先显式转换，再提交。

为兼容旧数据，缓存目录仍使用 `output/minimax_seg_cache/`，素材包目录也保留旧路径。
复用缓存需要保持 `cache_name`、节点 ID 和实际参数；原版与影栈执行时应使用不同缓存名以免互相覆盖。
更名不会恢复不存在的缓存，也不会绕过失配检查。

## 验证与发布状态

CPU 回归覆盖真实计划、缓存和执行控制流；浏览器回归使用真实前端模块与 ComfyUI 宿主模拟。
GPU 模型生成、实际 ComfyUI 环境与长视频效果尚待目标设备验收。
当前版本 `0.6.8` 包含滚动生成、低内存落盘、分段工作台、官方 H3 导入修复及全面复查修复；尚未发布到 Comfy Registry。详见 [复查记录](docs/review-2026-10-14.txt)。

```bash
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -p 'test_segment_seed_refine_only.py' -v
python -m unittest discover -s tests -p 'test_cinestack_release.py' -v
python tools/check_release.py
python -m unittest discover -s tests -p 'test_official_minimax_imports.py' -v
python -m unittest discover -s tests -p 'test_director_execution_mode.py' -v
```

[GitHub 仓库](https://github.com/guomenghao/ComfyUI-CineStack-H3) ·
[变更记录](CHANGELOG.md) · [平台路线](docs/roadmap.md) · [Apache-2.0](LICENSE)
