# Source Code

当前 `src/` 目录已经开始承载实际代码，主要包括：

- `src/data_pipeline/`
  - 原始数据清洗、统一字段、构建本地查询库
- `src/backend/`
  - 不依赖 Web 框架的本地查询层

当前还没有正式的 HTTP API 服务层，但数据处理与查询逻辑已经具备原型基础。
