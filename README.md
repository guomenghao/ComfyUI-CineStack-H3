# CineStack H3 / 影栈

[English](README_EN.md) · [分段 seed 与仅二采](docs/per-segment-seed-refine-only.md) · [迁移指南](docs/migration.md) · [发布准备](docs/publishing.md)

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
当前为独立初始版本 `0.1.0`；尚未发布到 Comfy Registry。

```bash
python -m unittest discover -s tests -p 'test_segment_seed_refine_only.py' -v
python -m unittest discover -s tests -p 'test_cinestack_release.py' -v
python tools/check_release.py
```

[GitHub 仓库](https://github.com/guomenghao/ComfyUI-CineStack-H3) ·
[变更记录](CHANGELOG.md) · [平台路线](docs/roadmap.md) · [Apache-2.0](LICENSE)
