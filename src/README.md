# Source Code

当前 `src/` 目录已经开始承载实际代码，主要包括：

- `src/data_pipeline/`
  - 原始数据清洗、统一字段、构建本地查询库
- `src/backend/`
  - 轻量本地查询层与原型 HTTP API

当前已经具备本地原型 HTTP API：

- `src/backend/query_service.py`
  - 面向 SQLite 的查询封装
- `src/backend/server.py`
  - 提供 `/api/*` 与 `/api/v1/*` 路由，并同时托管 `frontend/`

这仍然不是最终正式后端框架版本，但已经可以支撑前端联调。
