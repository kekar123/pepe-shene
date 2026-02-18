from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


def _normalize(text: str) -> str:
    if text is None:
        return ""
    value = str(text).strip().lower()
    value = re.sub(r"[^0-9a-zа-я]+", "", value, flags=re.IGNORECASE)
    return value


def _find_column(columns: Iterable, candidates: List[str]) -> Optional[str]:
    normalized = { _normalize(col): col for col in columns }
    for cand in candidates:
        cand_norm = _normalize(cand)
        if cand_norm in normalized:
            return normalized[cand_norm]
    # fallback: partial match
    for cand in candidates:
        cand_norm = _normalize(cand)
        for norm_col, original in normalized.items():
            if cand_norm and cand_norm in norm_col:
                return original
    return None


def _clean_article(value) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text if text else None


def _read_excel(path: Path, sheet_name=0, header=0) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name, header=header)


def _parse_location(location: str) -> Tuple[Optional[str], Optional[str]]:
    if not location:
        return None, None
    parts = str(location).strip().split("-")
    parts = [p for p in parts if p != ""]
    if len(parts) >= 3:
        aisle = parts[1]
        place = parts[2]
        return aisle, place
    # fallback: try to extract groups of digits
    digits = re.findall(r"\d+", str(location))
    if len(digits) >= 2:
        return digits[0], digits[1]
    return None, None


def _load_master_data(path: Path) -> pd.DataFrame:
    df = _read_excel(path, sheet_name=0, header=1)
    code_col = _find_column(df.columns, ["Код артикула", "Article Code"])
    name_col = _find_column(df.columns, ["Имя артикула", "Article Name"])
    pcb_col = _find_column(df.columns, ["Шт в коробе", "Pieces Per Case"])
    stockage_col = _find_column(df.columns, ["Класс стокажа", "Storage Class"])

    cols = {}
    if code_col:
        cols["article"] = df[code_col].apply(_clean_article)
    if name_col:
        cols["name"] = df[name_col]
    if pcb_col:
        cols["pcb"] = df[pcb_col]
    if stockage_col:
        cols["stockage"] = df[stockage_col]

    result = pd.DataFrame(cols)
    result = result.dropna(subset=["article"])
    # Убираем строку-шапку на английском, если попала в данные
    result = result[result["article"].astype(str).str.strip().str.lower().ne("article code")]
    return result


def _load_stock_report(path: Path) -> pd.DataFrame:
    df = _read_excel(path, sheet_name=0, header=0)
    article_col = _find_column(df.columns, ["Article", "Артикул"])
    location_col = _find_column(df.columns, ["Location", "Локация", "Место"])

    if not article_col or not location_col:
        return pd.DataFrame(columns=["article", "location", "aisle", "place"])

    data = df[[article_col, location_col]].copy()
    data.columns = ["article", "location"]
    data["article"] = data["article"].apply(_clean_article)
    data = data.dropna(subset=["article"])

    # choose most frequent location per article
    location_mode = (
        data.groupby("article")["location"]
        .agg(lambda x: x.dropna().astype(str).mode().iloc[0] if not x.dropna().empty else None)
        .reset_index()
    )
    location_mode["aisle"] = location_mode["location"].apply(lambda x: _parse_location(x)[0])
    location_mode["place"] = location_mode["location"].apply(lambda x: _parse_location(x)[1])
    return location_mode


def _load_order_picked(path: Path) -> pd.DataFrame:
    try:
        df = _read_excel(path, sheet_name="За период", header=4)
    except Exception:
        df = _read_excel(path, sheet_name=0, header=4)
    # remove service row with codes
    if "Заказ" in df.columns:
        df = df[df["Заказ"] != "REFLIV"]
    article_col = _find_column(df.columns, ["Артикул", "АРТИКУЛ"])
    picked_boxes_col = _find_column(df.columns, ["Собрано кор.", "Собрано кор", "Собрано"])
    aisle_col = _find_column(df.columns, ["Аллея"])
    place_col = _find_column(df.columns, ["Место"])

    data = pd.DataFrame()
    if article_col:
        data["article"] = df[article_col].apply(_clean_article)
    if picked_boxes_col:
        data["picked_boxes"] = pd.to_numeric(df[picked_boxes_col], errors="coerce").fillna(0)
    if aisle_col:
        data["aisle"] = df[aisle_col]
    if place_col:
        data["place"] = df[place_col]

    data = data.dropna(subset=["article"])

    if "aisle" not in data.columns:
        data["aisle"] = None
    if "place" not in data.columns:
        data["place"] = None

    grouped = data.groupby("article").agg(
        max_pick=("picked_boxes", "sum"),
        lines_count=("article", "count"),
        aisle=("aisle", lambda x: x.dropna().astype(str).mode().iloc[0] if not x.dropna().empty else None),
        place=("place", lambda x: x.dropna().astype(str).mode().iloc[0] if not x.dropna().empty else None),
    ).reset_index()
    return grouped


def _load_stock_movements(path: Path) -> pd.DataFrame:
    df = _read_excel(path, sheet_name=0, header=0)
    reason_col = _find_column(df.columns, ["Причина"])
    article_col = _find_column(df.columns, ["Артикул"])
    pallets_col = _find_column(df.columns, ["Номер паллета", "SSCC"])
    boxes_col = _find_column(df.columns, ["Коробов", "Коробки"])
    units_col = _find_column(df.columns, ["Штук", "ШТУК"])

    if not reason_col or not article_col:
        return pd.DataFrame(columns=["article", "reappro_pallets", "reappro_boxes", "reappro_units"])

    df = df.copy()
    df["article"] = df[article_col].apply(_clean_article)
    df["reason"] = df[reason_col].astype(str).str.lower()
    df = df.dropna(subset=["article"])

    filtered = df[df["reason"].str.contains("спуск") & df["reason"].str.contains("палл", na=False)]
    if filtered.empty:
        return pd.DataFrame(columns=["article", "reappro_pallets", "reappro_boxes", "reappro_units"])

    if pallets_col and pallets_col in filtered.columns:
        pallet_series = filtered[pallets_col]
    else:
        pallet_series = pd.Series([None] * len(filtered))

    filtered["reappro_pallets"] = pallet_series
    filtered["reappro_boxes"] = pd.to_numeric(filtered[boxes_col], errors="coerce").fillna(0) if boxes_col else 0
    filtered["reappro_units"] = pd.to_numeric(filtered[units_col], errors="coerce").fillna(0) if units_col else 0

    def pallet_count(series: pd.Series) -> int:
        series = series.dropna()
        if series.empty:
            return 0
        return series.nunique()

    grouped = filtered.groupby("article").agg(
        reappro_pallets=("reappro_pallets", pallet_count),
        reappro_boxes=("reappro_boxes", "sum"),
        reappro_units=("reappro_units", "sum"),
    ).reset_index()

    return grouped


def _load_picking_lines(path: Path) -> pd.DataFrame:
    df = _read_excel(path, sheet_name=0, header=0)
    article_col = _find_column(df.columns, ["АРТИКУЛ", "Артикул"])
    order_col = _find_column(df.columns, ["ЗАКАЗ", "Заказ"])
    date_col = _find_column(df.columns, ["ПЛАНОВАЯ_ДАТА_ОТГРУЗКИ", "Дата отгрузки"])
    support_type_col = _find_column(df.columns, ["ТИП_СУППОРТА", "Тип суппорта"])
    picked_boxes_col = _find_column(df.columns, ["СОБРАНО_КОР", "Собрано кор"])
    picked_units_col = _find_column(df.columns, ["ШТ_ДЛЯ_СБОРКИ", "Собрано шт", "ШТУК_ЗАКАЗАНО"])

    if not article_col:
        return pd.DataFrame(columns=["article", "orders_count", "last_out_date", "picked_boxes", "picked_units"])

    df = df.copy()
    df["article"] = df[article_col].apply(_clean_article)
    df = df.dropna(subset=["article"])

    if support_type_col and support_type_col in df.columns:
        df["support_type"] = df[support_type_col].astype(str).str.lower()
        df_pick = df[df["support_type"].str.contains("пик", na=False)]
    else:
        df_pick = df

    df_pick["picked_boxes"] = pd.to_numeric(df_pick[picked_boxes_col], errors="coerce").fillna(0) if picked_boxes_col else 0
    df_pick["picked_units"] = pd.to_numeric(df_pick[picked_units_col], errors="coerce").fillna(0) if picked_units_col else 0

    df["orders_count"] = df[order_col] if order_col else None
    df["last_out_date"] = pd.to_datetime(df[date_col], errors="coerce") if date_col else pd.NaT

    orders = (
        df.groupby("article")["orders_count"]
        .agg(lambda x: x.dropna().nunique())
        .reset_index()
        .rename(columns={"orders_count": "orders_count"})
    )

    last_dates = (
        df.groupby("article")["last_out_date"]
        .max()
        .reset_index()
    )

    picks = (
        df_pick.groupby("article")
        .agg(
            picked_boxes=("picked_boxes", "sum"),
            picked_units=("picked_units", "sum"),
        )
        .reset_index()
    )

    combined = orders.merge(last_dates, on="article", how="outer").merge(picks, on="article", how="outer")
    return combined


def _load_abc_analysis(path: Path) -> pd.DataFrame:
    df = _read_excel(path, sheet_name=0, header=0)
    # Убираем строку-шапку, если она продублирована как первая строка данных
    if not df.empty:
        first_row = df.iloc[0].tolist()
        if any('артикул' in str(cell).strip().lower() for cell in first_row):
            df = df.iloc[1:].reset_index(drop=True)
    article_col = _find_column(df.columns, ["Артикул", "АРТИКУЛ"])
    total_boxes_col = _find_column(df.columns, ["Коробов всего", "Коробов всего "])
    palletization_col = _find_column(df.columns, ["Паллетизация"])

    data = pd.DataFrame()
    if article_col:
        data["article"] = df[article_col].apply(_clean_article)
    if total_boxes_col:
        data["total_boxes"] = pd.to_numeric(df[total_boxes_col], errors="coerce").fillna(0)
    if palletization_col:
        data["palletization"] = df[palletization_col]

    data = data.dropna(subset=["article"])
    grouped = data.groupby("article").agg(
        total_boxes=("total_boxes", "sum"),
        palletization=("palletization", lambda x: x.dropna().iloc[0] if not x.dropna().empty else None),
    ).reset_index()
    return grouped


def _compute_abc_classes(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    data = df.copy()
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce").fillna(0)
    data = data.sort_values(value_col, ascending=False)
    total = data[value_col].sum()
    if total <= 0:
        data["abc_class"] = "C"
        return data[["article", "abc_class"]]

    data["share"] = data[value_col] / total * 100
    data["cumulative"] = data["share"].cumsum()

    def classify(cum):
        if cum <= 80:
            return "A"
        if cum <= 95:
            return "B"
        return "C"

    data["abc_class"] = data["cumulative"].apply(classify)
    return data[["article", "abc_class"]]


def _compute_popularity(df: pd.DataFrame, value_col: str, percent_col: str, popularity_col: str) -> pd.DataFrame:
    data = df[["article", value_col]].copy()
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce").fillna(0)
    data = data.sort_values(value_col, ascending=False)
    total = data[value_col].sum()
    if total <= 0:
        data[percent_col] = 0.0
        data[popularity_col] = 0.0
        return data[["article", percent_col, popularity_col]]

    data[percent_col] = data[value_col] / total * 100
    data[popularity_col] = data[percent_col].cumsum()
    return data[["article", percent_col, popularity_col]]


def _dead_stock_status(last_out_date: Optional[pd.Timestamp]) -> str:
    if last_out_date is None or pd.isna(last_out_date):
        return "нет данных"
    days = (datetime.now().date() - last_out_date.date()).days
    if days >= 90:
        return "красный"
    if days >= 60:
        return "желтый"
    return "зеленый"


def _dead_stock_sort_rank(last_out_date: Optional[pd.Timestamp]) -> int:
    if last_out_date is None or pd.isna(last_out_date):
        return 3
    days = (datetime.now().date() - last_out_date.date()).days
    if days >= 90:
        return 2
    if days >= 60:
        return 1
    return 0


@dataclass
class CombinedReportResult:
    rows: List[Dict]
    file_path: Path


def generate_combined_report(
    master_file: Path,
    stock_report_file: Path,
    order_picked_file: Path,
    stock_movements_file: Path,
    picking_lines_file: Path,
    abc_analysis_file: Path,
    output_dir: Path,
) -> CombinedReportResult:
    master = _load_master_data(master_file)
    stock_report = _load_stock_report(stock_report_file)
    order_picked = _load_order_picked(order_picked_file)
    stock_movements = _load_stock_movements(stock_movements_file)
    picking_lines = _load_picking_lines(picking_lines_file)
    abc_data = _load_abc_analysis(abc_analysis_file)

    all_articles = pd.Series(
        pd.concat([
            master["article"] if "article" in master else pd.Series(dtype=str),
            stock_report["article"] if "article" in stock_report else pd.Series(dtype=str),
            order_picked["article"] if "article" in order_picked else pd.Series(dtype=str),
            stock_movements["article"] if "article" in stock_movements else pd.Series(dtype=str),
            picking_lines["article"] if "article" in picking_lines else pd.Series(dtype=str),
            abc_data["article"] if "article" in abc_data else pd.Series(dtype=str),
        ], ignore_index=True)
    ).dropna().drop_duplicates()

    base = pd.DataFrame({"article": all_articles})

    report = base.merge(master, on="article", how="left")
    report = report.merge(stock_report[["article", "aisle", "place"]], on="article", how="left")
    report = report.merge(order_picked[["article", "max_pick", "lines_count", "aisle", "place"]], on="article", how="left", suffixes=("", "_order"))
    report = report.merge(stock_movements, on="article", how="left")
    report = report.merge(picking_lines, on="article", how="left")
    report = report.merge(abc_data, on="article", how="left")

    # fill aisle/place from order-picked if missing
    report["aisle"] = report["aisle"].fillna(report.get("aisle_order"))
    report["place"] = report["place"].fillna(report.get("place_order"))

    abc_classes = _compute_abc_classes(abc_data, "total_boxes") if not abc_data.empty else pd.DataFrame(columns=["article", "abc_class"])
    report = report.merge(abc_classes, on="article", how="left")

    reappro_pop = _compute_popularity(report.fillna(0), "reappro_boxes", "percent_reappro", "popularity_reappro")
    lines_pop = _compute_popularity(report.fillna(0), "lines_count", "percent_lines", "popularity_lines")

    report = report.merge(reappro_pop, on="article", how="left")
    report = report.merge(lines_pop, on="article", how="left")

    report["dead_stock_status"] = report["last_out_date"].apply(_dead_stock_status)
    report["dead_stock_rank"] = report["last_out_date"].apply(_dead_stock_sort_rank)
    report = report.sort_values(by=["dead_stock_rank", "article"], ascending=[True, True]).reset_index(drop=True)

    # output columns
    output = pd.DataFrame({
        "АРТИКУЛ": report["article"],
        "НАЗВАНИЕ": report.get("name"),
        "Аллея пикинг": report.get("aisle"),
        "Место пикинг": report.get("place"),
        "MAX PICK": report.get("max_pick", 0).fillna(0),
        "Кол-во палет реапро": report.get("reappro_pallets", 0).fillna(0),
        "Кол-во коробов реапро": report.get("reappro_boxes", 0).fillna(0),
        "Кол-во штук Реапро": report.get("reappro_units", 0).fillna(0),
        "Кол-во заказов": report.get("orders_count", 0).fillna(0),
        "Дата последнего выхода": report.get("last_out_date"),
        "Выход в коробах из пикинга": report.get("picked_boxes", 0).fillna(0),
        "Выход в штуках": report.get("picked_units", 0).fillna(0),
        "Палетизация": report.get("palletization"),
        "PCB": report.get("pcb"),
        "ABC класс": report.get("abc_class"),
        "Стокаж": report.get("stockage"),
        "Кол-во линий": report.get("lines_count", 0).fillna(0),
        "Процент (реаппро)": report.get("percent_reappro", 0).fillna(0),
        "Популярность (реаппро)": report.get("popularity_reappro", 0).fillna(0),
        "Процент (линии)": report.get("percent_lines", 0).fillna(0),
        "Популярность (линии)": report.get("popularity_lines", 0).fillna(0),
        "Мертвый сток": report.get("dead_stock_status"),
    })

    if "Дата последнего выхода" in output.columns:
        output["Дата последнего выхода"] = output["Дата последнего выхода"].apply(
            lambda value: value.strftime("%Y-%m-%d") if isinstance(value, pd.Timestamp) else ("" if pd.isna(value) else str(value))
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = output_dir / f"combined_report_{timestamp}.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        output.to_excel(writer, index=False, sheet_name="Отчет")
        worksheet = writer.sheets["Отчет"]

        # Ширины колонок
        worksheet.column_dimensions["A"].width = 18   # Артикул
        worksheet.column_dimensions["B"].width = 45   # Название
        worksheet.column_dimensions["C"].width = 16
        worksheet.column_dimensions["D"].width = 16
        worksheet.column_dimensions["E"].width = 12
        worksheet.column_dimensions["F"].width = 16
        worksheet.column_dimensions["G"].width = 16
        worksheet.column_dimensions["H"].width = 16
        worksheet.column_dimensions["I"].width = 18
        worksheet.column_dimensions["J"].width = 18
        worksheet.column_dimensions["K"].width = 18
        worksheet.column_dimensions["L"].width = 18
        worksheet.column_dimensions["M"].width = 14
        worksheet.column_dimensions["N"].width = 14
        worksheet.column_dimensions["O"].width = 14
        worksheet.column_dimensions["P"].width = 14
        worksheet.column_dimensions["Q"].width = 14
        worksheet.column_dimensions["R"].width = 18
        worksheet.column_dimensions["S"].width = 18
        worksheet.column_dimensions["T"].width = 18
        worksheet.column_dimensions["U"].width = 18
        worksheet.column_dimensions["V"].width = 16

        # Перенос текста и высота строк
        from openpyxl.styles import Alignment, Font, PatternFill
        header_fill = PatternFill(fill_type="solid", start_color="00008B", end_color="00008B")
        header_font = Font(color="FFFFFF", bold=True)
        dead_stock_fills = {
            "РєСЂР°СЃРЅС‹Р№": PatternFill(fill_type="solid", start_color="FF0000", end_color="FF0000"),
            "Р¶РµР»С‚С‹Р№": PatternFill(fill_type="solid", start_color="FFFF00", end_color="FFFF00"),
            "Р·РµР»РµРЅС‹Р№": PatternFill(fill_type="solid", start_color="00B050", end_color="00B050"),
        }
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
        dead_stock_fills = {
            "red": PatternFill(fill_type="solid", start_color="FFFF0000", end_color="FFFF0000"),
            "yellow": PatternFill(fill_type="solid", start_color="FFFFFF00", end_color="FFFFFF00"),
            "green": PatternFill(fill_type="solid", start_color="FF00B050", end_color="FF00B050"),
        }

        # Подсветка артикула (колонка A) по статусу "Мертвый сток" (последняя колонка)
        for row_idx, last_out_date in enumerate(report.get("last_out_date", pd.Series(dtype="datetime64[ns]")), start=2):
            if last_out_date is None or pd.isna(last_out_date):
                continue
            days = (datetime.now().date() - last_out_date.date()).days
            color_key = "red" if days >= 90 else ("yellow" if days >= 60 else "green")
            worksheet.cell(row=row_idx, column=1).fill = dead_stock_fills[color_key]

        wrap = Alignment(wrap_text=True, horizontal="center", vertical="center")
        for row in worksheet.iter_rows():
            worksheet.row_dimensions[row[0].row].height = 30
            for cell in row:
                cell.alignment = wrap

    safe_output = output.where(pd.notna(output), None)
    rows = safe_output.to_dict(orient="records")
    return CombinedReportResult(rows=rows, file_path=file_path)
