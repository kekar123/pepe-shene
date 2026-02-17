from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import re
import sqlite3


NO_DATA_RESPONSE = "В базе данных нет информации для ответа на этот вопрос."
CLARIFY_RESPONSE = (
    "Не удалось однозначно понять вопрос. Уточните, что нужно: "
    "количество, выручка, средняя выручка, топ/анти-топ, категории или конкретный товар."
)


@dataclass
class ProductRow:
    id: int
    product_name: str
    quantity: float
    revenue: float
    abc_category: str
    xyz_category: str
    abc_xyz_category: str
    source_db: str


class WarehouseChatAssistant:
    def __init__(self, db_path: Path, extra_db_paths: List[Path] | None = None) -> None:
        primary = Path(db_path)
        extras = [Path(p) for p in (extra_db_paths or [])]
        ordered = [primary, *extras]

        self.db_paths: List[Path] = []
        seen = set()
        for path in ordered:
            resolved = path.resolve()
            key = str(resolved).lower()
            if key in seen:
                continue
            seen.add(key)
            self.db_paths.append(resolved)

        # Fields are kept for API compatibility.
        self.model = None
        self.model_loaded = False
        self.model_backend = "deterministic"
        self.model_error = None

        self.stop_words = {
            "и",
            "в",
            "во",
            "на",
            "по",
            "с",
            "со",
            "к",
            "ко",
            "у",
            "о",
            "об",
            "от",
            "до",
            "из",
            "за",
            "для",
            "что",
            "как",
            "какой",
            "какая",
            "какие",
            "покажи",
            "покажи",
            "дай",
            "мне",
            "нужно",
            "хочу",
            "данные",
            "информация",
            "это",
            "эта",
            "этот",
            "где",
            "когда",
            "ли",
            "или",
            "а",
            "но",
            "же",
            "все",
            "всё",
            "товар",
            "товара",
            "товару",
            "товары",
        }

    def answer(self, user_message: str, history: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        question = (user_message or "").strip()
        if not question:
            return self._response(NO_DATA_RESPONSE, source="guard")

        rows, rows_by_db = self._load_all_rows()
        if not rows:
            return self._response(NO_DATA_RESPONSE, source="db")

        q_norm = self._normalize(question)
        intent = self._parse_intent(q_norm)
        summary = self._build_summary(rows)
        answer = self._handle_intent(question, q_norm, intent, rows, rows_by_db, summary)
        return self._response(answer, source="deterministic", rows=len(rows))

    def _response(self, answer: str, source: str, rows: int | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "answer": answer,
            "source": source,
            "model_loaded": self.model_loaded,
            "model_backend": self.model_backend,
        }
        if rows is not None:
            payload["rows"] = rows
        return payload

    def _parse_intent(self, q_norm: str) -> Dict[str, Any]:
        asks_count = self._has_any(q_norm, ["сколько", "колич", "числ"])
        asks_sum = self._has_any(q_norm, ["выручк", "оборот", "сумм", "итог"])
        asks_avg = self._has_any(q_norm, ["средн", "avg"])
        asks_units = self._has_any(q_norm, ["единиц", "ед", "штук", "шт", "qty", "колво"])
        asks_top = self._has_any(q_norm, ["топ", "лидер", "наибол", "макс", "луч"])
        asks_bottom = self._has_any(q_norm, ["анти", "миним", "наимен", "худш", "последн"])
        asks_list = self._has_any(q_norm, ["какие", "переч", "спис", "покажи"])
        asks_compare = self._has_any(q_norm, ["сравн", "больше", "меньше", "разниц"])
        asks_sources = self._has_any(q_norm, ["источник", "бд", "база", "откуда"])
        asks_matrix = self._has_any(q_norm, ["матриц", "abc xyz", "abc-xyz", "abcxyz"])
        asks_category_info = self._has_any(q_norm, ["категор", "группа", "класс"])

        # User can ask "топ 7", default 5.
        m_top = re.search(r"\b(?:топ|top)\s*(\d{1,2})\b", q_norm)
        limit = int(m_top.group(1)) if m_top else 5
        limit = max(1, min(limit, 20))

        categories = self._extract_categories(q_norm)
        return {
            "asks_count": asks_count,
            "asks_sum": asks_sum,
            "asks_avg": asks_avg,
            "asks_units": asks_units,
            "asks_top": asks_top,
            "asks_bottom": asks_bottom,
            "asks_list": asks_list,
            "asks_compare": asks_compare,
            "asks_sources": asks_sources,
            "asks_matrix": asks_matrix,
            "asks_category_info": asks_category_info,
            "categories": categories,
            "limit": limit,
        }

    def _handle_intent(
        self,
        question: str,
        q_norm: str,
        intent: Dict[str, Any],
        rows: List[ProductRow],
        rows_by_db: Dict[str, int],
        summary: Dict[str, Any],
    ) -> str:
        asks_stock_total = (
            intent["asks_count"]
            and self._has_any(q_norm, ["склад", "на складе", "всего товаров", "всего позиций", "номенклатур"])
        )

        if intent["asks_sources"]:
            return self._answer_sources(rows_by_db)

        if intent["asks_matrix"]:
            return self._answer_matrix(summary)

        categories: List[str] = intent["categories"]
        if intent["asks_compare"] and len(categories) >= 2:
            return self._answer_compare_categories(summary, categories[0], categories[1], intent)

        if categories:
            filtered = self._rows_by_category(rows, categories)
            if not filtered:
                return NO_DATA_RESPONSE
            return self._answer_for_rows(filtered, intent, category_label=", ".join(categories))

        product_tokens = self._extract_query_tokens(question)
        product_hits = self._find_products(product_tokens, rows)

        if asks_stock_total and not intent["categories"] and not product_hits:
            total_items = summary["unique_products"]
            total_units = summary.get("total_quantity", 0.0) if intent.get("asks_units") else 0.0
            if total_units > 0 and intent.get("asks_units"):
                return (
                    f"Всего товаров на складе: {total_items} наименований. "
                    f"Суммарное количество: {total_units:.3f} ед."
                )
            return f"Всего товаров на складе: {total_items} наименований."

        if product_hits:
            # If user asks about category/group -> focus on category answer.
            if intent["asks_category_info"] and not (intent["asks_sum"] or intent["asks_count"] or intent["asks_top"]):
                row = product_hits[0]
                return (
                    f"{row.product_name}: ABC {row.abc_category or '-'}, "
                    f"XYZ {row.xyz_category or '-'}, группа {row.abc_xyz_category or '-'}."
                )
            return self._answer_for_rows(product_hits, intent, category_label=None)

        # General aggregated questions without explicit category/product.
        if intent["asks_top"] or intent["asks_bottom"] or intent["asks_count"] or intent["asks_sum"] or intent["asks_avg"] or intent["asks_list"]:
            return self._answer_for_rows(rows, intent, category_label="всей выборки")

        if self._has_any(q_norm, ["общ", "сводк", "в целом", "всего"]):
            return (
                f"Записей: {summary['total_rows']}, уникальных товаров: {summary['unique_products']}, "
                f"суммарная выручка: {summary['total_revenue']:.2f}."
            )

        return CLARIFY_RESPONSE

    def _answer_for_rows(self, rows: List[ProductRow], intent: Dict[str, Any], category_label: Optional[str]) -> str:
        if not rows:
            return NO_DATA_RESPONSE

        label = category_label or "найденной выборки"
        count = len(rows)
        total = sum(r.revenue for r in rows)
        avg = total / count if count else 0.0
        use_quantity_metric = (not any((r.revenue or 0.0) > 0 for r in rows)) and any(
            (r.quantity or 0.0) > 0 for r in rows
        )

        if intent["asks_top"]:
            key_fn = (lambda r: r.quantity) if use_quantity_metric else (lambda r: r.revenue)
            top = sorted(rows, key=key_fn, reverse=True)[: intent["limit"]]
            metric = "quantity" if use_quantity_metric else "revenue"
            suffix = " по количеству" if use_quantity_metric else ""
            return self._format_product_list(top, f"Топ {len(top)} товаров{suffix} для {label}", metric=metric)

        if intent["asks_bottom"]:
            key_fn = (lambda r: r.quantity) if use_quantity_metric else (lambda r: r.revenue)
            bottom = sorted(rows, key=key_fn)[: intent["limit"]]
            metric = "quantity" if use_quantity_metric else "revenue"
            suffix = " по количеству" if use_quantity_metric else ""
            return self._format_product_list(bottom, f"Анти-топ {len(bottom)} товаров{suffix} для {label}", metric=metric)

        if intent["asks_list"]:
            key_fn = (lambda r: r.quantity) if use_quantity_metric else (lambda r: r.revenue)
            listed = sorted(rows, key=key_fn, reverse=True)[: intent["limit"]]
            metric = "quantity" if use_quantity_metric else "revenue"
            suffix = " (по количеству)" if use_quantity_metric else ""
            return self._format_product_list(listed, f"Список товаров{suffix} для {label}", metric=metric)

        # One primary metric by priority of mention in question.
        if intent["asks_count"] and not (intent["asks_sum"] or intent["asks_avg"]):
            if category_label:
                return f"Количество товаров для категории {label}: {count}."
            return f"Количество товаров: {count}."
        if intent["asks_avg"] and not intent["asks_sum"]:
            return f"Средняя выручка для {label}: {avg:.2f}."
        if intent["asks_sum"] and not intent["asks_avg"]:
            return f"Суммарная выручка для {label}: {total:.2f}."

        if intent["asks_sum"] and intent["asks_avg"]:
            return f"Для {label}: суммарная выручка {total:.2f}, средняя {avg:.2f}."

        # Default short answer for matched rows.
        best = sorted(rows, key=lambda r: (r.quantity if use_quantity_metric else r.revenue), reverse=True)[0]
        best_value = best.quantity if use_quantity_metric else best.revenue
        metric_label = "кол-во" if use_quantity_metric else "выручка"
        return (
            f"Найдено записей для {label}: {count}. "
            f"Лидер: {best.product_name} ({metric_label}: {best_value:.3f})."
        )

    def _answer_sources(self, rows_by_db: Dict[str, int]) -> str:
        if not rows_by_db:
            return NO_DATA_RESPONSE
        parts = [f"{db}: {count}" for db, count in sorted(rows_by_db.items())]
        return "Подключенные БД (число записей): " + "; ".join(parts) + "."

    def _answer_matrix(self, summary: Dict[str, Any]) -> str:
        order = ["AX", "AY", "AZ", "BX", "BY", "BZ", "CX", "CY", "CZ"]
        parts = []
        for cell in order:
            val = summary["matrix"].get(cell, {"count": 0})
            parts.append(f"{cell}: {val['count']}")
        return "Матрица ABC-XYZ (количество): " + ", ".join(parts) + "."

    def _answer_compare_categories(
        self,
        summary: Dict[str, Any],
        cat1: str,
        cat2: str,
        intent: Dict[str, Any],
    ) -> str:
        s1 = self._category_stats(summary, cat1)
        s2 = self._category_stats(summary, cat2)
        if not s1 and not s2:
            return NO_DATA_RESPONSE

        # Decide comparison metric.
        metric = "revenue" if intent["asks_sum"] or intent["asks_avg"] else "count"
        if metric == "revenue":
            v1 = s1["revenue"] if s1 else 0.0
            v2 = s2["revenue"] if s2 else 0.0
            if v1 == v2:
                return f"Категории {cat1} и {cat2} равны по выручке: {v1:.2f}."
            winner = cat1 if v1 > v2 else cat2
            diff = abs(v1 - v2)
            return f"По выручке больше у {winner}. Разница: {diff:.2f}."

        c1 = int(s1["count"]) if s1 else 0
        c2 = int(s2["count"]) if s2 else 0
        if c1 == c2:
            return f"Категории {cat1} и {cat2} равны по количеству: {c1}."
        winner = cat1 if c1 > c2 else cat2
        diff = abs(c1 - c2)
        return f"По количеству больше у {winner}. Разница: {diff}."

    def _category_stats(self, summary: Dict[str, Any], category: str) -> Optional[Dict[str, float]]:
        c = category.upper()
        if len(c) == 1 and c in {"A", "B", "C"}:
            return summary["abc"].get(c, {"count": 0, "revenue": 0.0})
        if len(c) == 1 and c in {"X", "Y", "Z"}:
            return summary["xyz"].get(c, {"count": 0, "revenue": 0.0})
        if len(c) == 2 and c[0] in {"A", "B", "C"} and c[1] in {"X", "Y", "Z"}:
            return summary["matrix"].get(c, {"count": 0, "revenue": 0.0})
        return None

    def _rows_by_category(self, rows: List[ProductRow], categories: List[str]) -> List[ProductRow]:
        cats = {c.upper() for c in categories}

        def match(row: ProductRow) -> bool:
            if row.abc_category in cats:
                return True
            if row.xyz_category in cats:
                return True
            if row.abc_xyz_category in cats:
                return True
            return False

        return [r for r in rows if match(r)]

    def _format_product_list(self, rows: List[ProductRow], title: str, metric: str = "revenue") -> str:
        if not rows:
            return NO_DATA_RESPONSE
        parts = []
        for idx, r in enumerate(rows, start=1):
            if metric == "quantity":
                parts.append(f"{idx}) {r.product_name} - {r.quantity:.3f} ед.")
            else:
                parts.append(f"{idx}) {r.product_name} - {r.revenue:.2f}")
        return f"{title}: " + "; ".join(parts) + "."

    def _extract_categories(self, q_norm: str) -> List[str]:
        found: List[str] = []
        category_map = {
            "A": "A",
            "А": "A",
            "B": "B",
            "Б": "B",
            "В": "B",
            "C": "C",
            "С": "C",
            "X": "X",
            "Х": "X",
            "Y": "Y",
            "У": "Y",
            "Z": "Z",
            "З": "Z",
        }

        tokens = re.findall(r"[a-zа-яё0-9]+", q_norm, flags=re.IGNORECASE)
        prepositions = {"в", "во", "на", "по", "у", "из", "для", "и", "или"}

        def normalize_category_token(token: str, allow_cyrillic: bool) -> str:
            # Category must be an explicit short token, not letters extracted from full words.
            if len(token) not in {1, 2}:
                return ""
            if re.fullmatch(r"[abcxyz]{1,2}", token, flags=re.IGNORECASE):
                mapped = token.upper()
            elif allow_cyrillic and re.fullmatch(r"[абвсхуз]{1,2}", token, flags=re.IGNORECASE):
                mapped = "".join(category_map.get(ch.upper(), "") for ch in token)
            else:
                return ""
            if len(mapped) == 1 and mapped in {"A", "B", "C", "X", "Y", "Z"}:
                return mapped
            if len(mapped) == 2 and mapped[0] in {"A", "B", "C"} and mapped[1] in {"X", "Y", "Z"}:
                return mapped
            return ""

        # Explicit forms like "категория а", "группа ах".
        for i, tok in enumerate(tokens[:-1]):
            if tok in {"категория", "категории", "группа", "группы"}:
                for nxt in tokens[i + 1 : i + 4]:
                    if nxt in prepositions:
                        continue
                    normalized = normalize_category_token(nxt, allow_cyrillic=True)
                    if normalized and normalized not in found:
                        found.append(normalized)
                    break

        # Standalone categories: only Latin notation (A/B/C/X/Y/Z, AX/BY...).
        for tok in tokens:
            normalized = normalize_category_token(tok, allow_cyrillic=False)
            if normalized and normalized not in found:
                found.append(normalized)

        return found

    def _extract_query_tokens(self, question: str) -> List[str]:
        q = self._normalize(question)
        tokens = []
        for tok in q.split():
            if len(tok) < 3:
                continue
            if tok in self.stop_words:
                continue
            if tok in {
                "abc",
                "xyz",
                "категория",
                "категории",
                "группа",
                "выручка",
                "сумма",
                "средняя",
                "топ",
                "анти",
                "матрица",
                "сколько",
            }:
                continue
            tokens.append(tok)
        return tokens

    def _find_products(self, tokens: List[str], rows: List[ProductRow]) -> List[ProductRow]:
        if not tokens:
            return []

        scored: List[Tuple[int, ProductRow]] = []
        for row in rows:
            name = self._normalize(row.product_name)
            if not name:
                continue
            score = sum(1 for token in tokens if token in name)
            if score > 0:
                scored.append((score, row))

        if not scored:
            return []

        scored.sort(key=lambda item: (item[0], item[1].revenue), reverse=True)
        return [row for _, row in scored]

    def _normalize(self, text: str) -> str:
        text = text.lower()
        # Keep both Latin and Cyrillic letters to correctly parse Russian user queries.
        text = re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9\s\-]", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _has_any(self, text: str, needles: List[str]) -> bool:
        return any(n in text for n in needles)

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND lower(name)=lower(?) LIMIT 1",
            (table_name,),
        )
        return cur.fetchone() is not None

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> List[str]:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table_name})")
        rows = cur.fetchall()
        return [str(row[1]).lower() for row in rows]

    def _load_rows_from_db(self, db_path: Path) -> List[ProductRow]:
        if not db_path.exists():
            return []

        conn = None
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()

            if self._table_exists(conn, "analysis"):
                analysis_columns = self._table_columns(conn, "analysis")
                has_quantity = "quantity" in analysis_columns
                cur.execute(
                    "SELECT id, product_name, "
                    + ("quantity, " if has_quantity else "NULL AS quantity, ")
                    + "revenue, abc_category, xyz_category, abc_xyz_category "
                    + "FROM analysis"
                )
            elif self._table_exists(conn, "products"):
                product_columns = self._table_columns(conn, "products")
                has_quantity = "quantity" in product_columns
                cur.execute(
                    "SELECT id, product_name, "
                    + ("quantity, " if has_quantity else "NULL AS quantity, ")
                    + "revenue, abc_category, xyz_category, abc_xyz_category "
                    + "FROM products"
                )
            else:
                return []

            out: List[ProductRow] = []
            for row in cur.fetchall():
                out.append(
                    ProductRow(
                        id=int(row[0]) if row[0] is not None else 0,
                        product_name=str(row[1] or "").strip(),
                        quantity=float(row[2]) if row[2] is not None else 0.0,
                        revenue=float(row[3]) if row[3] is not None else 0.0,
                        abc_category=str(row[4] or "").strip().upper(),
                        xyz_category=str(row[5] or "").strip().upper(),
                        abc_xyz_category=str(row[6] or "").strip().upper(),
                        source_db=db_path.name,
                    )
                )
            return out
        except Exception:
            return []
        finally:
            if conn is not None:
                conn.close()

    def _load_all_rows(self) -> Tuple[List[ProductRow], Dict[str, int]]:
        all_rows: List[ProductRow] = []
        rows_by_db: Dict[str, int] = {}

        for db_path in self.db_paths:
            rows = self._load_rows_from_db(db_path)
            if not rows:
                continue
            all_rows.extend(rows)
            rows_by_db[db_path.name] = rows_by_db.get(db_path.name, 0) + len(rows)

        # De-duplicate repeated products across DB snapshots/sessions.
        by_key: Dict[Tuple[str, str, str, str], ProductRow] = {}
        for row in all_rows:
            key = (
                row.product_name.lower(),
                row.abc_category,
                row.xyz_category,
                row.abc_xyz_category,
            )
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = row
                continue

            # Keep the most informative values when duplicates differ.
            existing.revenue = max(existing.revenue, row.revenue)
            existing.quantity = max(existing.quantity, row.quantity)

        uniq = list(by_key.values())
        uniq.sort(key=lambda r: r.revenue, reverse=True)
        return uniq, rows_by_db

    def _build_summary(self, rows: List[ProductRow]) -> Dict[str, Any]:
        total_revenue = sum(r.revenue for r in rows)
        total_quantity = sum(r.quantity for r in rows if r.quantity is not None)
        unique_products = len({r.product_name.lower() for r in rows if r.product_name})

        abc: Dict[str, Dict[str, float]] = {}
        xyz: Dict[str, Dict[str, float]] = {}
        matrix: Dict[str, Dict[str, float]] = {}

        for row in rows:
            a = (row.abc_category or "?").upper()
            x = (row.xyz_category or "?").upper()
            m = (row.abc_xyz_category or (a + x)).upper()

            abc.setdefault(a, {"count": 0, "revenue": 0.0})
            abc[a]["count"] += 1
            abc[a]["revenue"] += row.revenue

            xyz.setdefault(x, {"count": 0, "revenue": 0.0})
            xyz[x]["count"] += 1
            xyz[x]["revenue"] += row.revenue

            matrix.setdefault(m, {"count": 0, "revenue": 0.0})
            matrix[m]["count"] += 1
            matrix[m]["revenue"] += row.revenue

        return {
            "total_rows": len(rows),
            "unique_products": unique_products,
            "total_quantity": total_quantity,
            "total_revenue": total_revenue,
            "abc": abc,
            "xyz": xyz,
            "matrix": matrix,
        }
