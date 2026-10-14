# 前端资源缓存与验证

0.6.2 起，ComfyUI 在启动时从影栈 `web/js` 构建一套只读资源快照，
通过 `WEB_DIRECTORY` 自动发现全部模块：

```text
/extensions/ComfyUI-CineStack-H3/v0.6.2-<内容指纹>/minimax_timeline.js
/extensions/ComfyUI-CineStack-H3/v0.6.2-<内容指纹>/cinestack_migration.js
```

版本号来自 `pyproject.toml`，指纹涵盖所有资源的实际输出内容。版本或内容变化都会
产生新路径；入口和内部相对依赖使用同一目录，不会因为一个带查询参数、另一个不带
而重复加载模块。ComfyUI 自身的 app/api 模块保持公共 URL，不添加影栈版本。

生成目录位于系统临时目录，保留至进程退出，不使用 ComfyUI 会清理的 temp 目录；
不修改安装目录内的源文件，不需要 Node/npm 或新增 Python 依赖。只读安装目录也可用。
更新源文件后必须重启服务，运行中的后端版本与前端快照不会半途变化。

## 更新与验收

1. 在插件仓库 `git pull --ff-only`，重启 ComfyUI 服务，再刷新浏览器。
2. GET `/cinestack/h3/version` 应返回 `version: "0.6.2"` 与
   `frontend_asset_version: "v0.6.2-..."`。
3. GET `/extensions` 中的影栈脚本应全部包含相同资源版本目录。
4. 请求这些新路径，确认导演台主脚本含 `out-rolling-generation`，迁移脚本含
   `loadInstalledVersion`；实际依赖也应位于同一目录。
5. 重新打开旧工作流，检查滚动生成开关、分段总览及节点版本标记；保存以保留标记。

只给网页首页加参数不会改变内部脚本 URL。旧固定脚本地址即使仍被代理缓存，
也不再作为新启动服务的资源入口。若 `/extensions` 本身仍返回旧列表，需要进一步
检查该接口的代理缓存或是否连接了另一个服务实例，不能仅以版本号认定前端已更新。

本次不改变节点 ID、工作流字段、seed、采样、缓存匹配或滚动导出逻辑，不发布 Registry。
