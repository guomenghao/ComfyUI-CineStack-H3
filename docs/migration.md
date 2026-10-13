# 从原版迁移到影栈

CineStack 使用独立节点 ID，映射表见 `node_ids.json`。官方 H3 模型节点不会改名。

## 普通 UI 工作流

只安装影栈时，加载旧 JSON 会通过 `beforeConfigureGraph` 在内存中转换 Director 系列节点。
自动转换不修改原文件；另存为新文件后可保留两个版本。
同时装有原版时，不接管原版已注册节点。需要影栈功能时使用下列工具显式转换。

```bash
python tools/migrate_workflow.py old_workflow.json cinestack_workflow.json
```

输出文件必须是新文件。转换保留节点 ID、链接、模型、提示词、控件位置、分段 seed 和时间轴。
支持普通工作流、现代 subgraph、旧 groupNodes，以及 API prompt / queue request。
通过 API 或外部自动化提交的旧 prompt 必须转换后再发送，后端不注册冲突的旧别名。

## 一采缓存

缓存目录和指纹格式保留；外接素材组的节点类型在见证摘要中规范为旧名称，
避免仅品牌改名导致缓存失配。其他实际参数仍严格检查。

复用旧缓存时保持节点 ID、`cache_name`、素材和一采参数。旧工作流没有分段 seed 时继承全局，
没有 `refine_only` 时默认为 false。仅二采不会自动生成缺失缓存。

同时安装或比较两个插件时，应分别使用不同缓存名，避免相同节点编号共用目录。
现有导演包媒体目录与包格式继续兼容，不需要复制或改写用户素材。

## 安装范围

仓库名、节点 ID、HTTP 路由和进度事件已独立。
完整 ComfyUI 共存测试尚未在目标 GPU 设备执行；迁移与前端行为由 CPU/浏览器回归覆盖。
