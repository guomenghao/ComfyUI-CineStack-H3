# Comfy Registry 发布准备 / Release preparation

当前候选版本 **0.6.11**。仅推送 GitHub，**尚未发布官方 Registry**。Publisher 为 [`cinestack`](https://registry.comfy.org/zh/publishers/cinestack)，包 ID 为 `cinestack-h3`。

## 已准备与检查

- `pyproject.toml`：独立包 ID、Publisher、版本、Python/ComfyUI 最低声明、仓库 URL 与依赖。
- LICENSE、NOTICE 和上游来源保留；自有新增功能与原项目区分。改名不改变已有来源文件的许可证。
- 中英文 README、真实界面演示、[五段示例](five-shot-workflow.md)、[迁移说明](migration.md)、CHANGELOG。
- 原节点序列化字段、端口顺序与缓存指纹不因本次 UI 修复而变更。旧工作流不用删除节点或清缓存。
- 离线包检查调用官方 comfy-cli 1.22.0 的 `zip_files`；解压后检查元数据、全部 Python/前端文件和版本化脚本构建，不只检查源码目录。
- 离线检查与发布流程均关闭 Git `core.quotepath` 转义，修复官方打包器遗漏中文名旧示例的问题；检查包含全部示例。
- 发布 Action 仅允许手动 `workflow_dispatch`；普通 Git push 不上架。发布前复用全部 CI，并核对输入版本和 Secret 是否存在。

2026-10-13 已确认 `REGISTRY_ACCESS_TOKEN` 名称存在。名称存在不代表凭据已验证可发布；不读取或输出密钥，不为试验认证而发布。

## 可重复检查（不发布）

```bash
python tools/check_release.py --publish
python -m unittest discover -s tests -p 'test_*.py' -v
# 在独立开发环境安装，不要求插件用户安装 comfy-cli。
python -m pip install comfy-cli==1.22.0
python tools/check_package.py --output /tmp/cinestack-h3-candidate.zip
```

Windows 把最后路径换成临时目录的绝对路径，并使用 `python -X utf8 tools/check_package.py --output ...`，确保官方 CLI 正确读取 Git 的中文文件名（CI 设置 `PYTHONUTF8=1`）。`--publish` 是元数据严格检查开关，不会上传。打包仅包含 Git 已跟踪文件；新文件须先加入 Git。检查脚本拒绝把压缩包写回源目录。`.comfyignore` 排除测试、CI、开发产物；包中保留示例、文档、运行模块、前端、迁移工具和许可证，不包含权重、缓存或用户视频。

## 安装兼容性边界

- 声明基线：Python ≥3.10、ComfyUI ≥0.30.0；H3 采样依赖官方 MiniMax H3 实现。最低声明不等于每个历史版本都经过验收。
- 本轮隔离安装检查使用官方 ComfyUI **0.40.0**、前端 **1.55.17**、Python **3.11**、CPU；不加载模型。具体结果见 [0.6.11 验证记录](validation-0.6.11.md)。
- 实际服务器此前是前端 1.53.6；官方 Core 0.40.0 要求的推荐前端为 1.55.17。更新 ComfyUI 时应使用该环境 Python 安装其 requirements，避免 Core/前端长期错配。
- Nodes 2.0 与传统渲染器都保留；本次修复 DOM 重新挂载恢复、已删除节点的迟到回调，以及初始化失败的可见重试。不能把一次成功展示称为所有第三方扩展组合都兼容。
- Windows 整合包、Linux GPU、同时安装上游插件的完整生成验收仍待完成。macOS CPU 启动只验证导入和界面，不代表支持本地 H3 GPU 生成。
- 可选人脸能力依赖 ultralytics/OpenCV；不要为了安装本插件无条件替换已有 CUDA/PyTorch。独立环境安装失败时记录依赖解析日志。

## 正式上架前仍须完成

- [ ] GPU 运行五段示例：独立 seed、严格仅二采、缺缓存拒绝、只重做第 3 段、两侧连贯与断开连线。
- [ ] 滚动模式的一采/最终文件、音轨、帧数和整片/选段导出；系统内存趋势与峰值。
- [ ] 实际旧项目加载与缓存复用；不要用空白示例覆盖用户工作流或替换缓存名。
- [ ] Windows/Linux 目标环境与可选扩展联用验收，记录明确支持范围。
- [ ] 审核候选压缩包文件列表、运行 CI 的同一提交和版本；确认 Registry ID 仍可用。
- [ ] 确认 Publisher 密钥可用、图标/横幅等展示资料（可选）与描述真实。
- [ ] 用户明确允许发布后，手动运行 Publish to Comfy Registry；再从 Registry 全新安装检查。此次不执行。

官方资料（2026-10-17 核对）：[发布流程](https://docs.comfy.org/registry/publishing)、[元数据规范](https://docs.comfy.org/registry/specifications)、[节点标准](https://docs.comfy.org/registry/standards)。CPU/浏览器检查不能代替 GPU 验收，也不能代替 Registry 自身审核。

## English

0.6.11 is a GitHub-only release candidate. The offline packaging check uses the official CLI packer and validates extracted runtime assets. Publishing remains a manual action, gated by CI, matching version and a configured Registry token. GPU acceptance, target Windows/Linux validation, existing-cache reuse and Registry install verification remain release gates; none are implied by the CPU or browser tests. Follow the five-shot guide and record evidence before explicitly authorizing publication.
