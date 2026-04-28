# Web-Kanban

这是当前 `Web-Kanban` 项目的本地原型开发版本。

## 当前内容汇总

基于目前本地工作区的客观情况，仓库当前主要包含：

- `docs/`
  - 看板项目 `1-8` 阶段的执行基线与审计 TODO
  - `1-4 月` 三平台经营数据的数据源审计文档
  - 历史字段口径说明文档
- `assets/`
  - 现有的图片参考文件
- `data/`
  - 本地数据目录占位
  - 导出的标准化经营明细与汇总表
  - 本地查询库 `SQLite`
- `src/`
  - 数据处理脚本
  - 本地查询层
- `frontend/`
  - 5 个看板的静态前端原型
  - 本地前端数据集
  - 本地预览脚本

## 当前项目状态

目前已经完成的工作：

- 明确了 5 个看板的需求范围
- 读取并审计了 `1-4 月` 的美团、饿了么、京东汇总数据
- 确认了时间、收入、到手率、门店转化率等关键业务口径
- 确认了门店对齐表可作为标准门店映射底表
- 完成了 `1-8` 阶段的文档化沉淀
- 已构建本地标准化数据层与查询库
- 已生成前端使用的轻量数据集
- 已搭建 5 个看板的静态前端骨架

目前尚未开始的工作：

- 正式 Web API 封装
- 前端视觉细化和交互打磨
- 浏览器实测与联调
- 正式技术栈迁移与部署

## 当前目录结构

```text
.
├── README.md
├── assets/
├── data/
├── docs/
├── frontend/
└── src/
```

## 当前可用内容

- 数据处理脚本：
  - `src/data_pipeline/build_local_warehouse.py`
  - `src/data_pipeline/build_query_db.py`
  - `src/data_pipeline/export_frontend_dataset.py`
- 本地查询层：
  - `src/backend/query_service.py`
- 前端原型：
  - `frontend/index.html`
  - `frontend/styles.css`
  - `frontend/app.js`
  - `frontend/serve_preview.py`

## 下一步建议

下一阶段建议继续推进：

1. 用浏览器实际验收 5 个看板原型
2. 根据领导反馈调整页面结构和指标展示
3. 把查询层包装成正式 API
4. 再切换到正式前端技术栈并接入后端
