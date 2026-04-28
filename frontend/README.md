# Frontend Prototype

这是网页看板的本地前端原型目录。

当前目标：

- 不依赖额外安装的前端框架
- 基于本地 `/api/v1/*` 接口渲染 5 个看板骨架
- 用于快速验证页面结构、信息层级和交互方式

目录说明：

- `index.html`
  - 单页原型入口
- `styles.css`
  - 页面样式
- `app.js`
  - 页面状态、筛选逻辑、接口请求、模块渲染
- `data/dashboard_dataset.json`
  - 历史轻量数据集留档，当前联调默认不再直接读取

当前限制：

- 这不是最终技术栈实现版
- 当前接口由 `src/backend/server.py` 提供，仍是轻量原型服务
- 当前主要用于本地联调、页面结构确认和接口边界验收

本地联调启动：

```bash
python3 src/backend/server.py
```

然后在浏览器打开：

`http://127.0.0.1:4180`
