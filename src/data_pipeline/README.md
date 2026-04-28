# Data Pipeline

这一目录用于存放本地数据层构建脚本。

当前第一阶段目标：

- 读取 `1-4 月` 的美团、饿了么、京东经营汇总文件
- 读取门店对齐表
- 清洗并统一字段
- 构建本地 `SQLite` 数据仓库
- 生成后续看板开发可直接使用的明细层与汇总层

当前脚本：

- `build_local_warehouse.py`
- `build_query_db.py`

输出结果：

- `data/warehouse/web_kanban.db`
- `data/exports/dwd_platform_daily_normalized.csv`
- `data/exports/dws_platform_daily_summary.csv`
- `data/exports/dws_store_daily_summary.csv`
- `data/exports/dws_city_daily_summary.csv`

注意：

- 当前实现基于你已经确认的业务口径
- 美团 `营业额` 暂按 `优惠前总额` 映射
- 后续如果你要调整口径，优先修改字段映射，不需要重写整个脚本
- 为了保证本地环境稳定落库，`SQLite` 中当前保留的是轻量可查询层，不强行写入原始宽表全量镜像
- 如果本地完整重建过程较慢，可先运行 `build_query_db.py`，它会直接把现有标准化导出表回灌到查询库
