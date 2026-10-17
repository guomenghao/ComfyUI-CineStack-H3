# CineStack H3 / 影栈

**满意的片段留下，需要修改的片段重做。**

面向 AI 视频创作者、工作流搭建者与小型制作团队的 **ComfyUI H3 多段生成与精修工作台**。逐段固定 seed，确认一采后再精修，利用相邻片段缓存约束接点，并通过滚动生成和文件视频输出完成整片交付。

**分段可控 · 缓存可查 · 局部重做 · 完整导出**

[English](README_EN.md) · [制作案例](docs/production-cases.md) · [示例工作流](example_workflows/README.md) · [安装](#安装与更新) · [变更日志](CHANGELOG.md)

当前 H3 版本 **0.6.11**，通过 Git 安装；尚未发布到 Comfy Registry。影栈当前提供 H3 生成模块，完整本地影视平台是后续方向。

新手入口：[五段独立 seed → 仅二采 → 滚动导出的可导入模板](docs/five-shot-workflow.md)。0.6.11 补上 Nodes 2.0 面板挂载恢复与加载失败重试；[安装与发布准备](docs/publishing.md)列明已验证范围和待完成的 GPU 验收。

## 看真实界面，再看操作步骤

![新版影栈导演台：第3段独立seed、仅一采按钮与五段时间轴](docs/media/director-0.6.10/03-first-pass.png)

**真实 ComfyUI 界面，设置演示，未提交生成。** 使用独立空白五段图，不公开用户素材；缺缓存提示如实保留。拍摄采用标准节点渲染，环境与操作范围见[截图说明](docs/director-ui-demo.md)。

## 把返工留在需要修改的片段里

| 制作时遇到的问题 | 影栈怎么处理 |
| --- | --- |
| 多段里只有一段不满意，想独立尝试 | 每段可固定一采 seed，只运行勾选段；留空仍继承全局 seed |
| 一采已经满意，希望精修时保留它 | **仅二采**只使用匹配的一采缓存；缺失、失配或损坏时说明原因并停止 |
| 重做中间段，希望承接前后画面 | 开启段间引导后，连接线决定是否读取前段尾部、未选后段首帧作为约束 |
| 局部返工后还要交付完整视频 | **全部导出＋滚动生成**复用未选段已有结果，按时间轴合成完整视频 |
| 段数增加，整片画面不断占用内存 | 滚动生成保留当前段和必要的相邻数据，通过文件视频交接与磁盘合并减少画面累积 |

固定 seed 便于管理分段尝试，不保证跨模型、软件版本或设备逐像素复现。缓存是否可复用，还取决于输入、模型和采样设置等匹配条件。

## 制作案例：五段完成，只返工第 3 段

这是基于项目实际返工需求整理的操作场景，不是耗时或画质基准测试。

1. 已有五段结果，保留第 1、2、4、5 段，只勾选第 3 段，调整它的一采 seed。
2. 开启段间引导。2—3 相连时读取第 2 段尾部；3—4 相连且第 4 段未选中时，读取第 4 段首帧约束结尾。断开哪侧，取消哪侧约束。
3. 选择 **仅一采**，检查新结果。满意后保持一采相关设置，选择 **仅二采**精修第 3 段。
4. 使用 **全部导出＋滚动生成**，复用其余段已有的最终视频，输出完整时间轴。只要本轮选中段文件时，使用 **分段导出＋滚动生成**。

![五段只重做第3段：真实界面逐步截图动画](docs/media/director-0.6.10/third-segment-walkthrough.gif)

逐步截图动画：只选第 3 段 → 改独立 seed → 仅一采设置 → 仅二采设置 → 全部导出＋滚动生成。**没有运行一采/二采或导出；演示图未接 Refine，实际阻断提示已保留。** 实际制作需在一采运行并确认后再切换二采。[逐步原图与执行前提 →](docs/director-ui-demo.md)

未选邻段只读取必要边界，完整导出复用其已有视频，不自动重新采样邻段。所需缓存或文件缺失会明确提示；右侧约束是画面首帧，不是反向音频或未来运动生成。接点的实际画面与声音效果需要看片确认。

[查看完整操作步骤、缓存前提及检查项 →](docs/production-cases.md)

## 从一采确认，到精修与交付

- **分段工作台：** 集中查看缩略图、计划帧数、生效 seed 和缓存状态；通过明显的仅一采、仅二采、跟随工作流按钮选择执行阶段。
- **运行前检查：** 检查执行方式、缓存和文件端口接线，提供问题段与处理入口。检查不会代替你启动重新生成。
- **两路结果：** 一采和最终结果分别预览、下载或连接 SaveVideo，方便比较并保留原片。
- **多种 H3 入口：** 支持 t2v / i2v / fl2v / r2v / v2v / rv2v、外部素材组与导演包；继承上游 Refine、SelfLift、Semantic Bridge、FaceRefine 等能力，各自需要相应模型及依赖。

“仅二采”需要已启用并接好 Refine（`refine` 或 `upscale`）及二采 SIGMAS。`latent_upscale` 仅放大 latent；FL2V 二采需关闭 `skip_fl2v`。缓存标记用于初查，执行时仍会完整校验。

## 技术支撑：滚动生成与文件视频交接

长序列优先使用 **滚动生成＋文件 VIDEO 输出**。生成时处理当前段及必要连贯数据，合并时由 FFmpeg 逐区间读取文件，避免在 Python 中重新构造整片 IMAGE 张量。

| 模式 | 输出范围与用途 |
| --- | --- |
| 全部导出＋滚动生成 | 生成勾选段，复用未选段已有视频，交付完整时间轴 |
| 分段导出＋滚动生成 | 仅交付本轮勾选段 |
| 普通模式 | 保留原 IMAGE/AUDIO 接线；完整 IMAGE 输出仍需要整片内存 |

滚动模式接线：

```text
导演台 first_pass_video ──→ SaveVideo（一采）
导演台 final_video      ──→ SaveVideo（最终/二采原片）
                       └─→ 可选后处理链
```

文件端口直接接官方 SaveVideo，格式/编码使用 `auto`；不经过 CreateVideo 或要求 IMAGE 的 Video Combine。普通模式接文件端口会提示开启滚动生成。仅一采时，尚未生成的最终入口不可用。

滚动模式降低画面累积，不等于恒定总内存或永不 OOM：模型驻留、当前段尺寸、VAE 和下游节点仍影响峰值。磁盘合并也有读取、编码及存储开销。阶段诊断可帮助定位问题，不能替代目标设备实测。

[滚动生成](docs/rolling-generation.txt) · [完整导出](docs/rolling-full-export.txt) · [保存与预览](docs/rolling-video-delivery.txt) · [内存诊断](docs/memory-diagnostics.txt)

## 已有满意原片，只调整后处理

二采已经满意时，可以将已保存的原片交给 LoadVideo，再进行 SR、NR 或补帧，无需重跑导演台采样。保留二采原片，并分别保存各阶段结果，才能判断画质变化发生在哪一步。

可选搭配独立的 [DLSS 插件](https://github.com/guomenghao/ComfyUI-DLSS-NeuralRender-Linux)。其 **0.2.1** 提供帧率/音轨修复与时长检查节点；需要单独安装或更新，更新影栈不包含该插件。文件流式路径要求只使用相应 VIDEO 输出；接 IMAGE 输出仍可能保留整片画面。

现有 744 帧、24 fps、31 秒原片的 CPU 文件处理回归验证了两次处理后的帧数、节奏与音轨时长；这不是 GPU SR/NR 画质或补帧拖影验收。超分、降噪和补帧需按素材判断是否采用。

[后处理接线与分阶段保存 →](docs/dlss-timing-0.2.1.txt)

## 安装与更新

需要支持官方 MiniMax H3 的 ComfyUI、对应模型和依赖。在**运行 ComfyUI 的同一 Python 环境**执行，路径按实际安装位置调整：

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/guomenghao/ComfyUI-CineStack-H3.git
python -m pip install -r ComfyUI-CineStack-H3/requirements.txt
```

已通过 Git 安装时：

```bash
cd ComfyUI/custom_nodes/ComfyUI-CineStack-H3
git pull --ff-only
python -m pip install -r requirements.txt
```

更新后重启 ComfyUI、刷新页面。节点位于 `CineStack/H3`。手动复制的同名文件夹需先备份到 `custom_nodes` 外再克隆；不要覆盖删除唯一缓存或运行库。本仓库不含模型权重、用户素材或 ComfyUI 本体。

[官方 H3 教程](https://docs.comfy.org/tutorials/video/minimax/minimax-h3) · [模型与示例说明](example_workflows/README.md)

## 从一个适合你的示例开始

| 目标 | 入口 |
| --- | --- |
| 了解基本生成与接线 | [文生视频示例](example_workflows/minimax_h3_director_t2v.json) |
| 使用人物或素材参考 | [参考生成示例](example_workflows/minimax_h3_director_r2v.json) |
| 学习一采与二采接线 | [二采示例](example_workflows/minimax_h3_director_二采_加速.json) |
| 局部返工并导出整片 | [制作案例与滚动接线说明](docs/production-cases.md) |
| 使用已有二采原片做后处理 | [文件视频后处理说明](docs/dlss-timing-0.2.1.txt) |

仓库 JSON 示例是基础接线模板，不代表已预设滚动生成或严格仅二采；导入后配置自己的模型、素材、执行方式与输出。不要在未核对设置时直接运行陌生工作流。

## 兼容、验证与已知边界

- **旧工作流：** 保留原位置控件及前八个输出位置；文件 VIDEO 输出追加在后。缺少新字段时保留旧行为。只安装影栈时可迁移普通旧工作流；与原版共存或提交 API prompt 时按[迁移指南](docs/migration.md)显式处理。
- **已有缓存：** 继续使用 `output/minimax_seg_cache/`；保持缓存名、节点 ID 和匹配参数，保留被引用的源视频。修改一采条件或连接关系可能使缓存失配，仅二采不会自动重做一采。原版与影栈共存时使用不同缓存名。
- **连贯范围：** 仅二采复用该段一采时保存的接点约束；旧缓存不会自动补上原先不存在的右侧约束。[详细规则](docs/bidirectional-junctions.txt)
- **验证范围：** 提供 CPU 控制流、缓存、实际编解码及前端宿主模拟回归。实机排错记录不构成所有模型、硬件和长片配置的性能保证。[自动检查](https://github.com/guomenghao/ComfyUI-CineStack-H3/actions)与[变更日志](CHANGELOG.md)可查看验证范围。

## 下一步：走向本地影视制作工作台

当前重点是把分段生成、确认、精修与交付做好。未来候选方向包括项目与素材版本管理、任务依赖和失败恢复、跨模型调度、剪辑与声音组织，以及独立桌面工作台。这些属于规划，当前仓库未实现完整平台能力。

[查看平台路线](docs/roadmap.md) · [提交问题或建议](https://github.com/guomenghao/ComfyUI-CineStack-H3/issues)

反馈问题时，请提供版本、执行方式、导出范围、相关日志与脱敏的最小工作流；不要上传密钥或无权公开的素材。

## 来源与维护

由 **guomenghao** 维护，基于 **AIMixer 与贡献者的 MiniMax H3 Director** 扩展。影栈重点增加分段固定 seed、严格缓存精修、局部返工、滚动交付及相应检查与诊断；上游能力和第三方插件分别保留来源说明。

[Apache-2.0](LICENSE) · [NOTICE](NOTICE) · [上游说明](docs/upstream/README.md) · [完整变更日志](CHANGELOG.md)

这是独立衍生项目，不是 MiniMax、AIMixer 或 ComfyUI 官方产品。
