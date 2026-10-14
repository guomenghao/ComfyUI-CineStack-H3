# CineStack H3 / 影栈

[English](README_EN.md) · [分段 seed 与仅二采](docs/per-segment-seed-refine-only.md) · [迁移指南](docs/migration.md) · [发布准备](docs/publishing.md)

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
当前版本 `0.3.0` 包含低内存落盘、分段工作台、官方 H3 导入修复及全面复查修复；尚未发布到 Comfy Registry。详见 [复查记录](docs/review-2026-10-14.txt)。

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
