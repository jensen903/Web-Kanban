from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = Path("/Users/apple/窄巷口/可视化看板/Inputs/经营数据")
STORE_MASTER_PATH = Path(
    "/Users/apple/窄巷口/可视化看板/Master_门店主表/门店对齐表_最新版.xlsx"
)

WAREHOUSE_DIR = REPO_ROOT / "data" / "warehouse"
EXPORT_DIR = REPO_ROOT / "data" / "exports"
DB_PATH = WAREHOUSE_DIR / "web_kanban.db"


PLATFORM_FILES = {
    "美团": [
        "1月美团汇总.csv",
        "2月美团汇总.csv",
        "3月美团汇总.csv",
        "4月美团汇总.csv",
    ],
    "饿了么": [
        "1月饿了么汇总.xlsx",
        "2月饿了么汇总.xlsx",
        "饿了么3月汇总.xlsx",
        "4月饿了么汇总.xlsx",
    ],
    "京东": [
        "1月京东汇总.xlsx",
        "2月京东汇总.xlsx",
        "3月京东汇总.xlsx",
        "4月京东汇总.xlsx",
    ],
}


def ensure_output_dirs() -> None:
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def parse_source_month(file_name: str) -> int:
    match = re.search(r"(\d+)月", file_name)
    if not match:
        raise ValueError(f"无法从文件名识别月份: {file_name}")
    return int(match.group(1))


def normalize_store_id(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    return text


def normalize_city(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    return re.sub(r"市$", "", text)


def normalize_province(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"特别行政区$", "", text)
    text = re.sub(r"自治区$", "", text)
    text = re.sub(r"[省市]$", "", text)
    return text or None


def normalize_district(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def normalize_date(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{8}", text):
        dt = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    else:
        dt = pd.to_datetime(text, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.strftime("%Y/%m/%d")


def to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def to_rate(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    has_percent = text.str.endswith("%")
    numeric = pd.to_numeric(text.str.rstrip("%"), errors="coerce")
    numeric.loc[has_percent] = numeric.loc[has_percent] / 100
    return numeric


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = numerator / denominator
    result = result.where(denominator.notna() & (denominator != 0))
    return result


def build_standard_store_id(store_name: str) -> str:
    digest = hashlib.md5(store_name.encode("utf-8")).hexdigest()[:10]
    return f"SS_{digest}"


def read_source_file(platform: str, file_name: str) -> pd.DataFrame:
    path = RAW_DIR / file_name
    if platform == "美团":
        df = pd.read_csv(path, encoding="gb18030")
    else:
        xls = pd.ExcelFile(path)
        df = pd.read_excel(path, sheet_name=xls.sheet_names[0])

    df = df.copy()
    df["source_platform"] = platform
    df["source_file"] = file_name
    df["source_month"] = parse_source_month(file_name)
    return df


def build_raw_union() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for platform, files in PLATFORM_FILES.items():
        for file_name in files:
            frames.append(read_source_file(platform, file_name))
    return pd.concat(frames, ignore_index=True, sort=False)


def build_store_master() -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[str, str], dict[str, object]]]:
    master = pd.read_excel(STORE_MASTER_PATH)
    master = master.copy()
    master["门店名称"] = master["门店名称"].astype(str).str.strip()
    master["standard_store_id"] = master["门店名称"].apply(build_standard_store_id)
    master["省份"] = master["省份"].apply(normalize_province)
    master["城市"] = master["城市"].apply(normalize_city)
    master["行政区"] = master["行政区"].apply(normalize_district)

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
    lookup: dict[tuple[str, str], dict[str, object]] = {}
    id_columns = {
        "美团": "美团ID",
        "饿了么": "饿了么ID",
        "京东": "京东ID",
    }

    for row in master.to_dict(orient="records"):
        for platform, id_col in id_columns.items():
            platform_store_id = normalize_store_id(row.get(id_col))
            if not platform_store_id:
                continue
            mapping_record = {
                "platform": platform,
                "platform_store_id": platform_store_id,
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
            mapping_rows.append(mapping_record)
            lookup[(platform, platform_store_id)] = mapping_record

    bridge_platform_store_mapping = pd.DataFrame(mapping_rows)
    return dim_standard_store, bridge_platform_store_mapping, lookup


def standardize_platform_rows(
    source_df: pd.DataFrame,
    mapping_lookup: dict[tuple[str, str], dict[str, object]],
) -> pd.DataFrame:
    platform = source_df["source_platform"].iloc[0]
    df = source_df.copy()

    if platform == "美团":
        platform_store_id = df["门店id"].apply(normalize_store_id)
        city = df["门店所在城市"].apply(normalize_city)
        province = df["省份"].apply(normalize_province)
        district = df["区县市"].apply(normalize_district)
        revenue = to_number(df["营业收入"])
        gross_amount = to_number(df["优惠前总额"])
        customer_paid = to_number(df["顾客实付"])
        valid_orders = to_number(df["有效订单"])
        avg_ticket = to_number(df["实付单均价"])
        exposure_users = to_number(df["曝光人数"])
        visit_users = to_number(df["入店人数"])
        visit_conversion_rate = to_rate(df["入店转化率"])
        order_conversion_rate = to_rate(df["下单转化率"])
        activity_subsidy = to_number(df["活动补贴"]).fillna(0).add(
            to_number(df["平台活动补贴"]).fillna(0), fill_value=0
        )
        expense_amount = to_number(df["补贴及支出"])
    elif platform == "饿了么":
        platform_store_id = df["门店编号"].apply(normalize_store_id)
        city = df["城市名称"].apply(normalize_city)
        province = df["省份"].apply(normalize_province)
        district = df["区县名称"].apply(normalize_district)
        revenue = to_number(df["收入"])
        gross_amount = to_number(df["营业额"])
        customer_paid = to_number(df["顾客实付总额"])
        valid_orders = to_number(df["有效订单"])
        avg_ticket = to_number(df["单均实付"])
        exposure_users = to_number(df["曝光人数"])
        visit_users = to_number(df["进店人数"])
        visit_conversion_rate = to_rate(df["进店转化率"])
        order_conversion_rate = to_rate(df["下单转化率"])
        activity_subsidy = to_number(df["活动补贴"])
        expense_amount = to_number(df["支出"])
    elif platform == "京东":
        platform_store_id = df["门店id"].apply(normalize_store_id)
        city = df["城市"].apply(normalize_city)
        province = pd.Series([None] * len(df), index=df.index, dtype="object")
        district = pd.Series([None] * len(df), index=df.index, dtype="object")
        revenue = to_number(df["收入"])
        gross_amount = to_number(df["营业额"])
        customer_paid = to_number(df["顾客实付"])
        valid_orders = to_number(df["有效订单"])
        avg_ticket = to_number(df["实付单均价"])
        exposure_users = to_number(df["曝光人数"])
        visit_users = to_number(df["入店人数"])
        visit_conversion_rate = to_rate(df["入店转化率"])
        order_conversion_rate = to_rate(df["下单转化率"])
        activity_subsidy = to_number(df["活动补贴"])
        expense_amount = to_number(df["支出"])
    else:
        raise ValueError(f"不支持的平台: {platform}")

    records: list[dict[str, object]] = []
    for idx in df.index:
        key = (platform, platform_store_id.loc[idx])
        matched = mapping_lookup.get(key)
        records.append(
            {
                "platform": platform,
                "source_file": df.at[idx, "source_file"],
                "source_month": df.at[idx, "source_month"],
                "biz_date": normalize_date(df.at[idx, "日期"]),
                "platform_store_id": platform_store_id.loc[idx],
                "platform_store_name": str(df.at[idx, "门店名称"]).strip(),
                "standard_store_id": matched["standard_store_id"] if matched else None,
                "standard_store_name": matched["standard_store_name"] if matched else None,
                "match_status": matched["match_status"] if matched else "未对齐",
                "match_method": matched["match_method"] if matched else None,
                "province": matched["province"] if matched and matched["province"] else province.loc[idx],
                "city": matched["city"] if matched and matched["city"] else city.loc[idx],
                "district": matched["district"] if matched and matched["district"] else district.loc[idx],
                "address": matched["address"] if matched else None,
                "operator_name": matched["operator_name"] if matched else None,
                "revenue": revenue.loc[idx],
                "gross_amount": gross_amount.loc[idx],
                "customer_paid": customer_paid.loc[idx],
                "valid_orders": valid_orders.loc[idx],
                "avg_ticket": avg_ticket.loc[idx],
                "activity_subsidy": activity_subsidy.loc[idx],
                "expense_amount": expense_amount.loc[idx],
                "exposure_users": exposure_users.loc[idx],
                "visit_users": visit_users.loc[idx],
                "visit_conversion_rate": visit_conversion_rate.loc[idx],
                "order_conversion_rate": order_conversion_rate.loc[idx],
            }
        )

    normalized = pd.DataFrame(records)
    normalized["revenue"] = to_number(normalized["revenue"])
    normalized["gross_amount"] = to_number(normalized["gross_amount"])
    normalized["customer_paid"] = to_number(normalized["customer_paid"])
    normalized["valid_orders"] = to_number(normalized["valid_orders"])
    normalized["avg_ticket"] = to_number(normalized["avg_ticket"])
    normalized["activity_subsidy"] = to_number(normalized["activity_subsidy"])
    normalized["expense_amount"] = to_number(normalized["expense_amount"])
    normalized["exposure_users"] = to_number(normalized["exposure_users"])
    normalized["visit_users"] = to_number(normalized["visit_users"])
    normalized["visit_conversion_rate"] = to_number(normalized["visit_conversion_rate"])
    normalized["order_conversion_rate"] = to_number(normalized["order_conversion_rate"])
    normalized["hand_rate"] = safe_divide(normalized["revenue"], normalized["gross_amount"])
    normalized["active_store_flag"] = normalized["valid_orders"].fillna(0) > 0
    return normalized


def build_normalized_layer(
    raw_union: pd.DataFrame,
    mapping_lookup: dict[tuple[str, str], dict[str, object]],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for platform in PLATFORM_FILES:
        platform_df = raw_union[raw_union["source_platform"] == platform].copy()
        frames.append(standardize_platform_rows(platform_df, mapping_lookup))
    return pd.concat(frames, ignore_index=True)


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


def distinct_count(frame: pd.Series) -> int:
    return frame.dropna().nunique()


def build_platform_summary(normalized: pd.DataFrame) -> pd.DataFrame:
    grouped = normalized.groupby(["biz_date", "platform"], dropna=False)
    summary = grouped.agg(
        revenue=("revenue", "sum"),
        gross_amount=("gross_amount", "sum"),
        customer_paid=("customer_paid", "sum"),
        valid_orders=("valid_orders", "sum"),
        exposure_users=("exposure_users", "sum"),
        active_store_count=("active_store_flag", "sum"),
        store_count=("standard_store_id", distinct_count),
        city_count=("city", distinct_count),
        province_count=("province", distinct_count),
    ).reset_index()
    summary["avg_ticket"] = safe_divide(summary["customer_paid"], summary["valid_orders"])
    summary["hand_rate"] = safe_divide(summary["revenue"], summary["gross_amount"])
    return summary.sort_values(["biz_date", "platform"]).reset_index(drop=True)


def build_store_summary(normalized: pd.DataFrame) -> pd.DataFrame:
    grouped = normalized.groupby(
        ["biz_date", "platform", "standard_store_id", "standard_store_name"],
        dropna=False,
    )
    summary = grouped.agg(
        revenue=("revenue", "sum"),
        gross_amount=("gross_amount", "sum"),
        customer_paid=("customer_paid", "sum"),
        valid_orders=("valid_orders", "sum"),
        exposure_users=("exposure_users", "sum"),
        order_conversion_rate=("order_conversion_rate", "mean"),
        province=("province", "first"),
        city=("city", "first"),
        district=("district", "first"),
    ).reset_index()
    summary["avg_ticket"] = safe_divide(summary["customer_paid"], summary["valid_orders"])
    summary["hand_rate"] = safe_divide(summary["revenue"], summary["gross_amount"])
    return summary.sort_values(["biz_date", "platform", "revenue"], ascending=[True, True, False])


def build_city_summary(normalized: pd.DataFrame) -> pd.DataFrame:
    grouped = normalized.groupby(["biz_date", "platform", "province", "city"], dropna=False)
    summary = grouped.agg(
        revenue=("revenue", "sum"),
        gross_amount=("gross_amount", "sum"),
        customer_paid=("customer_paid", "sum"),
        valid_orders=("valid_orders", "sum"),
        exposure_users=("exposure_users", "sum"),
        active_store_count=("active_store_flag", "sum"),
        store_count=("standard_store_id", distinct_count),
    ).reset_index()
    summary["avg_ticket"] = safe_divide(summary["customer_paid"], summary["valid_orders"])
    summary["hand_rate"] = safe_divide(summary["revenue"], summary["gross_amount"])
    return summary.sort_values(["biz_date", "platform", "revenue"], ascending=[True, True, False])


def export_csvs(named_frames: Iterable[tuple[str, pd.DataFrame]]) -> None:
    for name, frame in named_frames:
        frame.to_csv(EXPORT_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")


def write_sqlite(named_frames: Iterable[tuple[str, pd.DataFrame]]) -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    journal_path = DB_PATH.with_name(f"{DB_PATH.name}-journal")
    if journal_path.exists():
        journal_path.unlink()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode = DELETE")
        conn.execute("PRAGMA synchronous = NORMAL")
        for name, frame in named_frames:
            frame.to_sql(
                name,
                conn,
                index=False,
                if_exists="replace",
                chunksize=2000,
                method="multi",
            )


def main() -> None:
    ensure_output_dirs()

    raw_union = build_raw_union()
    dim_standard_store, bridge_platform_store_mapping, mapping_lookup = build_store_master()
    normalized = build_normalized_layer(raw_union, mapping_lookup)
    raw_index = build_raw_index(normalized)
    platform_summary = build_platform_summary(normalized)
    store_summary = build_store_summary(normalized)
    city_summary = build_city_summary(normalized)

    sqlite_frames = [
        ("ods_platform_daily_raw_index", raw_index),
        ("dim_standard_store", dim_standard_store),
        ("bridge_platform_store_mapping", bridge_platform_store_mapping),
        ("dwd_platform_daily_normalized", normalized),
        ("dws_platform_daily_summary", platform_summary),
        ("dws_store_daily_summary", store_summary),
        ("dws_city_daily_summary", city_summary),
    ]

    export_frames = [
        ("dwd_platform_daily_normalized", normalized),
        ("dws_platform_daily_summary", platform_summary),
        ("dws_store_daily_summary", store_summary),
        ("dws_city_daily_summary", city_summary),
    ]

    write_sqlite(sqlite_frames)
    export_csvs(export_frames)

    print("本地数据仓库构建完成")
    print(f"SQLite: {DB_PATH}")
    for name, _ in export_frames:
        print(f"CSV: {EXPORT_DIR / f'{name}.csv'}")


if __name__ == "__main__":
    main()
