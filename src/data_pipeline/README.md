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
- `export_frontend_dataset.py`

目录配置：

- 默认数据根目录：`/Users/apple/窄巷口/可视化看板`
- 如需迁移到其他电脑或 Linux 环境，可通过环境变量覆盖：
  - `WEB_KANBAN_DATA_ROOT`
  - `WEB_KANBAN_RAW_DIR`
  - `WEB_KANBAN_RAW_ARCHIVE_DIR`
  - `WEB_KANBAN_STORE_MASTER_DIR`

一键更新并以局域网方式启动看板：

```bash
bash scripts/update_and_serve_lan.sh
```

常用可选项：

```bash
PORT=4181 bash scripts/update_and_serve_lan.sh
WEB_KANBAN_DATA_ROOT="/data/web-kanban" bash scripts/update_and_serve_lan.sh
PYTHON_BIN=python3 bash scripts/update_and_serve_lan.sh
```

当前 `build_local_warehouse.py` 会自动扫描：

- `Inputs/经营数据` 中待处理的当月汇总文件
- `Inputs/经营数据_历史备份` 中已归档的历史月汇总文件

如果同一平台同一月份同时存在“当前文件”和“历史归档文件”，脚本会优先使用当前文件；构建成功后，会把本次从 `Inputs/经营数据` 消费掉的月汇总文件移动到新的时间戳归档目录。

输出结果：

- `src/warehouse/web_kanban.db`
- `src/exports/dwd_platform_daily_normalized.csv`
- `src/exports/dws_platform_daily_summary.csv`
- `src/exports/dws_store_daily_summary.csv`
- `src/exports/dws_city_daily_summary.csv`

注意：

- 当前实现基于你已经确认的业务口径
- 美团 `营业额` 暂按 `优惠前总额` 映射
- 后续如果你要调整口径，优先修改字段映射，不需要重写整个脚本
- 为了保证本地环境稳定落库，`SQLite` 中当前保留的是轻量可查询层，不强行写入原始宽表全量镜像
- 如果本地完整重建过程较慢，可先运行 `build_query_db.py`，它会直接把现有标准化导出表回灌到查询库
