# Comfy Registry 发布准备

本仓库已准备独立元数据、静态依赖列表、许可证、迁移工具、CI 和手动发布 Action。
Publisher 已注册为 [`cinestack`](https://registry.comfy.org/zh/publishers/cinestack)，显示名称 `CineStack / 影栈`，元数据已填写真实 Publisher ID。当前尚未上架。

2026-10-13 已确认 GitHub Repository secret `REGISTRY_ACCESS_TOKEN` 存在，发布元数据检查通过。Secret 名称存在不等于已验证 Registry 认证；本阶段只完成注册与配置，正式发布仍保持手动触发。

官方参考（2026-10-13 核对）：
- https://docs.comfy.org/registry/publishing
- https://docs.comfy.org/registry/specifications
- https://github.com/Comfy-Org/publish-node-action

## 当前阶段：注册与发布密钥

按用户 2026-10-13 的安排，本阶段先完成账号和密钥配置，实际 GPU 验证留到后续；本阶段不触发正式发布。

1. Publisher `cinestack` 已注册，项目 `pyproject.toml` 使用同一 ID。
2. 在 Publisher 页面创建专用于此仓库的 API key，建议名称 `cinestack-h3-github-actions`。创建和密钥录入由账号持有人亲自完成。
3. 在 [GitHub Actions secrets](https://github.com/guomenghao/ComfyUI-CineStack-H3/settings/secrets/actions) 新建 Repository secret，名称必须为 `REGISTRY_ACCESS_TOKEN`，值为该 Publisher 的 Registry API key。
4. 密钥无需发送到聊天或提交到代码；配置检查只确认 secret 名称存在，不读取其内容。
5. 运行 `python tools/check_release.py --publish`，检查项目身份和发布元数据。这一步不连接 Registry、不发布，也不验证 GPU 生成效果。

## 后续阶段：正式发布

1. 在实际 ComfyUI/GPU 环境完成目标设备验收。
2. 在 Actions 中手动运行 **Publish to Comfy Registry**，输入与元数据一致的版本号。
3. 检查 Registry 新条目的仓库、作者、版本、安装文件及节点加载结果。

当前包 ID 为 `cinestack-h3`，待发布版本为 `0.6.4`（包含低内存落盘、导演台分段工作台及官方 H3 导入修复）。上架前确认 Registry ID 可用；正式创建后包 ID 不可随意变更。
普通推送只运行 CI，不自动发布。发布 Action 会先运行完整 CPU/浏览器回归，再检查 Publisher ID、token 和版本；检查失败则停止。
后续每个发布版本使用新版本号并同步 CHANGELOG，发布失败须排查后再判断版本是否可重试。

## 包内容与验收

`.comfyignore` 排除 CI、测试、开发产物，保留全部运行模块、前端、迁移工具、许可证和用户文档。
不上传权重、缓存、用户素材、生成视频、访问令牌或本地业务资料。

CPU 与浏览器测试验证种子、缓存拒绝行为和迁移；它们不能替代 GPU 生成验收。
实际目标设备须核对加载节点、旧工作流转换、五段混合 seed 仅二采、失配拒绝、外接组与导演包往返。
