# Comfy Registry 发布准备

本仓库已准备独立元数据、静态依赖列表、许可证、迁移工具、CI 和手动发布 Action。
`PublisherId` 为空，当前状态是“准备完成，尚未上架”。GitHub 用户名不能代替已注册 Publisher ID。

官方参考（2026-10-13 核对）：
- https://docs.comfy.org/registry/publishing
- https://docs.comfy.org/registry/specifications
- https://github.com/Comfy-Org/publish-node-action

## 首次上架

1. 在 Comfy Registry 创建你自己的 Publisher，记下真实 Publisher ID。不要使用上游的 `aimixer`。
2. 更新 `pyproject.toml` 的 `[tool.comfy].PublisherId`。
3. 运行 `python tools/check_release.py --publish`，完成实际 ComfyUI/GPU 环境验收。
4. 创建该 Publisher 的 Registry API key，将其存入 GitHub 仓库 Actions secret `REGISTRY_ACCESS_TOKEN`；密钥不写入代码或 issue。
5. 提交配置，在 Actions 中手动运行 **Publish to Comfy Registry**，输入与元数据一致的版本号。
6. 检查 Registry 新条目的仓库、作者、版本、安装文件及节点加载结果。

当前包 ID 为 `cinestack-h3`，首版 `0.1.0`。上架前确认 Registry ID 可用；正式创建后包 ID 不可随意变更。
普通推送只运行 CI，不自动发布。发布 Action 会检查 Publisher ID、token 和版本，缺少任一项则停止。
后续每个发布版本使用新版本号并同步 CHANGELOG，发布失败须排查后再判断版本是否可重试。

## 包内容与验收

`.comfyignore` 排除 CI、测试、开发产物，保留全部运行模块、前端、迁移工具、许可证和用户文档。
不上传权重、缓存、用户素材、生成视频、访问令牌或本地业务资料。

CPU 与浏览器测试验证种子、缓存拒绝行为和迁移；它们不能替代 GPU 生成验收。
实际目标设备须核对加载节点、旧工作流转换、五段混合 seed 仅二采、失配拒绝、外接组与导演包往返。
