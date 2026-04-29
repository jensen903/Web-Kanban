from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
EXPORT_DIR = BASE_DIR / "exports"
WAREHOUSE_DIR = BASE_DIR / "warehouse"
DB_PATH = WAREHOUSE_DIR / "web_kanban.db"
STORE_MASTER_DIR = Path("/Users/apple/窄巷口/可视化看板/Master_门店主表")


def build_standard_store_id(store_name: str) -> str:
    digest = hashlib.md5(store_name.encode("utf-8")).hexdigest()[:10]
    return f"SS_{digest}"


def normalize_store_id(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    return text


def normalize_text(value: object, suffix: str = "") -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if suffix and text.endswith(suffix):
        text = text[: -len(suffix)]
    return text or None


def normalize_province(value: object) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    text = text.removesuffix("特别行政区")
    text = text.removesuffix("自治区")
    if text.endswith("省") or text.endswith("市"):
        text = text[:-1]
    return text or None


def normalize_city(value: object) -> str | None:
    return normalize_text(value, "市")


def resolve_store_master_path() -> Path:
    preferred_names = [
        "门店对齐表_最新版.xlsx",
        "门店对齐表.xlsx",
        "门店对齐表_副本.xlsx",
        "门店对齐表旧版.xlsx",
    ]
    for file_name in preferred_names:
        path = STORE_MASTER_DIR / file_name
        if path.exists():
            return path

    candidates = sorted(STORE_MASTER_DIR.glob("门店对齐表*.xlsx"))
    if candidates:
        return candidates[0]

    raise FileNotFoundError(f"未找到门店对齐表文件: {STORE_MASTER_DIR}")


def build_master_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    master = pd.read_excel(resolve_store_master_path()).copy()
    master["门店名称"] = master["门店名称"].astype(str).str.strip()
    master["standard_store_id"] = master["门店名称"].apply(build_standard_store_id)
    master["省份"] = master["省份"].apply(normalize_province)
    master["城市"] = master["城市"].apply(normalize_city)
    master["行政区"] = master["行政区"].apply(normalize_text)

    dim_standard_store = master.rename(
        columns={
            "门店名称": "standard_store_name",
            "省份": "province",
            "城市": "city",
            "行政区": "district",
            "详细地址": "address",
            "运营": "operator_name",
        }
    )[
        [
            "standard_store_id",
            "standard_store_name",
            "province",
            "city",
            "district",
            "address",
            "operator_name",
        ]
    ].copy()

    mapping_rows: list[dict[str, object]] = []
    platform_columns = {"美团": "美团ID", "饿了么": "饿了么ID", "京东": "京东ID"}
    for row in master.to_dict(orient="records"):
        for platform, col in platform_columns.items():
            store_id = normalize_store_id(row.get(col))
            if not store_id:
                continue
            mapping_rows.append(
                {
                    "platform": platform,
                    "platform_store_id": store_id,
                    "platform_store_name": row["门店名称"],
                    "standard_store_id": row["standard_store_id"],
                    "standard_store_name": row["门店名称"],
                    "province": row["省份"],
                    "city": row["城市"],
                    "district": row["行政区"],
                    "address": row["详细地址"],
                    "operator_name": row["运营"],
                    "match_status": "已对齐",
                    "match_method": "门店对齐表",
                }
            )

    bridge_platform_store_mapping = pd.DataFrame(mapping_rows)
    return dim_standard_store, bridge_platform_store_mapping


def build_raw_index(normalized: pd.DataFrame) -> pd.DataFrame:
    return normalized[
        [
            "platform",
            "source_file",
            "source_month",
            "biz_date",
            "platform_store_id",
            "platform_store_name",
        ]
    ].copy()


def main() -> None:
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)

    normalized = pd.read_csv(EXPORT_DIR / "dwd_platform_daily_normalized.csv")
    platform_summary = pd.read_csv(EXPORT_DIR / "dws_platform_daily_summary.csv")
    store_summary = pd.read_csv(EXPORT_DIR / "dws_store_daily_summary.csv")
    city_summary = pd.read_csv(EXPORT_DIR / "dws_city_daily_summary.csv")

    for frame in (normalized, store_summary, city_summary):
        if "province" in frame.columns:
            frame["province"] = frame["province"].apply(normalize_province)
        if "city" in frame.columns:
            frame["city"] = frame["city"].apply(normalize_city)
        if "district" in frame.columns:
            frame["district"] = frame["district"].apply(normalize_text)

    raw_index = build_raw_index(normalized)
    dim_standard_store, bridge_platform_store_mapping = build_master_tables()

    if DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        for name, frame in [
            ("ods_platform_daily_raw_index", raw_index),
            ("dim_standard_store", dim_standard_store),
            ("bridge_platform_store_mapping", bridge_platform_store_mapping),
            ("dwd_platform_daily_normalized", normalized),
            ("dws_platform_daily_summary", platform_summary),
            ("dws_store_daily_summary", store_summary),
            ("dws_city_daily_summary", city_summary),
        ]:
            frame.to_sql(name, conn, index=False, if_exists="replace", chunksize=2000)

    print("查询库构建完成")
    print(DB_PATH)


if __name__ == "__main__":
    main()
