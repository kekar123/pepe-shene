from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import json
import os
import re
import sqlite3
import urllib.error
import urllib.request


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
    def __init__(
        self,
        db_path: Path,
        extra_db_paths: List[Path] | None = None,
        combined_reports_dir: Path | None = None,
    ) -> None:
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

        self.combined_reports_dir = Path(combined_reports_dir).resolve() if combined_reports_dir else None
        self.combined_jobs_dir = (
            (self.combined_reports_dir / "combined_jobs").resolve()
            if self.combined_reports_dir
            else None
        )
        self.use_combined_json_only = os.getenv("CHAT_USE_COMBINED_JSON", "1").lower() in {"1", "true", "yes"}

        # Model backend settings.
        self.model = None
        self.model_loaded = False
        self.model_backend = "deterministic"
        self.model_error = None

        self.ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "warehouse-assistant")
        self.use_ollama = os.getenv("CHAT_USE_OLLAMA", "1").lower() in {"1", "true", "yes"}
        self.force_ollama = os.getenv("CHAT_FORCE_OLLAMA", "0").lower() in {"1", "true", "yes"}
        self.llm_mode = os.getenv("CHAT_LLM_MODE", "auto").strip().lower()
        try:
            self.ollama_temperature = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))
        except Exception:
            self.ollama_temperature = 0.1
        try:
            self.ollama_top_p = float(os.getenv("OLLAMA_TOP_P", "0.9"))
        except Exception:
            self.ollama_top_p = 0.9
        try:
            self.ollama_max_tokens = int(os.getenv("OLLAMA_MAX_TOKENS", "260"))
        except Exception:
            self.ollama_max_tokens = 260

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

        q_norm = self._normalize(question)
        intent = self._parse_intent(q_norm)

        if self.use_combined_json_only:
            summary = self._load_latest_combined_summary()
            rows = self._load_latest_combined_rows()
            if not summary:
                return self._response(NO_DATA_RESPONSE, source="db")

            deterministic_answer = self._answer_from_combined_summary(question, q_norm, intent, summary, rows)
            if deterministic_answer:
                if deterministic_answer in {NO_DATA_RESPONSE, CLARIFY_RESPONSE}:
                    if self._should_use_ollama(intent):
                        ollama_answer = self._answer_with_ollama(
                            question,
                            [],
                            {},
                            summary,
                            deterministic_answer=deterministic_answer,
                        )
                        if ollama_answer:
                            self.model_loaded = True
                            self.model_backend = "ollama"
                            return self._response(ollama_answer, source="ollama")
                    return self._response(deterministic_answer, source="deterministic")

                if self._should_use_ollama(intent):
                    ollama_answer = self._answer_with_ollama(
                        question,
                        [],
                        {},
                        summary,
                        deterministic_answer=deterministic_answer,
                    )
                    if ollama_answer:
                        self.model_loaded = True
                        self.model_backend = "ollama"
                        return self._response(ollama_answer, source="ollama")
                return self._response(deterministic_answer, source="deterministic")

            if self._should_use_ollama(intent):
                ollama_answer = self._answer_with_ollama(
                    question,
                    [],
                    {},
                    summary,
                    deterministic_answer=CLARIFY_RESPONSE,
                )
                if ollama_answer:
                    self.model_loaded = True
                    self.model_backend = "ollama"
                    return self._response(ollama_answer, source="ollama")

            # When no deterministic answer is available, always prefer LLM response if enabled.
            if self.use_ollama:
                ollama_answer = self._answer_with_ollama(
                    question,
                    [],
                    {},
                    summary,
                    deterministic_answer=CLARIFY_RESPONSE,
                )
                if ollama_answer:
                    self.model_loaded = True
                    self.model_backend = "ollama"
                    return self._response(ollama_answer, source="ollama")
            return self._response(CLARIFY_RESPONSE, source="deterministic")

        rows, rows_by_db = self._load_all_rows()
        if not rows:
            return self._response(NO_DATA_RESPONSE, source="db")

        summary = self._build_summary(rows)
        deterministic_answer = self._handle_intent(question, q_norm, intent, rows, rows_by_db, summary)

        if deterministic_answer in {NO_DATA_RESPONSE, CLARIFY_RESPONSE}:
            if self._should_use_ollama(intent):
                ollama_answer = self._answer_with_ollama(
                    question,
                    rows,
                    rows_by_db,
                    summary,
                    deterministic_answer=deterministic_answer,
                )
                if ollama_answer:
                    self.model_loaded = True
                    self.model_backend = "ollama"
                    return self._response(ollama_answer, source="ollama", rows=len(rows))
            return self._response(deterministic_answer, source="deterministic", rows=len(rows))

        if self._should_use_ollama(intent):
            ollama_answer = self._answer_with_ollama(
                question,
                rows,
                rows_by_db,
                summary,
                deterministic_answer=deterministic_answer,
            )
            if ollama_answer:
                self.model_loaded = True
                self.model_backend = "ollama"
                return self._response(ollama_answer, source="ollama", rows=len(rows))

        return self._response(deterministic_answer, source="deterministic", rows=len(rows))

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

    def _greeting_response(self, question: str) -> Optional[str]:
        q = self._normalize(question)
        greetings = [
            "привет",
            "здравств",
            "добрый день",
            "добрый вечер",
            "доброе утро",
            "хай",
            "hello",
        ]
        if any(g in q for g in greetings):
            return "Здравствуйте. Задайте вопрос по логистике или складу."
        return None

    def _explain_term(self, question: str) -> Optional[str]:
        q = self._normalize(question)
        glossary = {
            "пикинг": (
                "Пикинг — это зона и процесс отбора товаров по заказам. "
                "Обычно это места хранения, из которых комплектуют отгрузки. "
                "Если нужно, могу показать конкретные аллеи и места пикинга по артикулу."
            ),
            "реапро": (
                "Реапро — это пополнение зоны пикинга (re-appro). "
                "Задача — вовремя подвозить товары в пикинг, чтобы не было дефицита при отборе."
            ),
            "abc": (
                "ABC‑анализ — это группировка товаров по важности. "
                "A — самые важные/часто отбираемые, B — средние, C — редкие. "
                "Могу показать распределение по ABC в общем отчете."
            ),
            "xyz": (
                "XYZ‑анализ — это группировка по стабильности спроса. "
                "X — стабильный спрос, Y — сезонные колебания, Z — нерегулярный спрос."
            ),
        }
        for key, text in glossary.items():
            if key in q:
                return text
        return None

    def _load_latest_combined_summary(self) -> Optional[Dict[str, Any]]:
        if not self.combined_reports_dir:
            return None
        try:
            files = sorted(
                self.combined_reports_dir.glob("combined_report_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            return None
        if not files:
            return None
        latest = files[0]
        try:
            with latest.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                return None
            return payload
        except Exception:
            return None

    def _load_latest_combined_rows(self) -> List[Dict[str, Any]]:
        if not self.combined_jobs_dir:
            return []
        try:
            files = sorted(
                self.combined_jobs_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            return []
        for path in files[:5]:
            try:
                with path.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
                if not isinstance(payload, dict):
                    continue
                if payload.get("status") != "ready":
                    continue
                rows = payload.get("rows")
                if isinstance(rows, list):
                    return rows
            except Exception:
                continue
        return []

    def _answer_from_combined_summary(
        self,
        question: str,
        q_norm: str,
        intent: Dict[str, Any],
        summary: Dict[str, Any],
        rows: List[Dict[str, Any]] | None = None,
    ) -> Optional[str]:
        rows = rows or []
        rows_answer = self._answer_from_combined_rows(question, q_norm, rows)
        if rows_answer:
            return rows_answer

        if "заказыва" in q_norm or ("чаще всего" in q_norm and "товар" in q_norm):
            top_orders = summary.get("топ10_по_заказам") or []
            if top_orders:
                item = top_orders[0]
                name = item.get("название") or item.get("РќРђР—Р’РђРќРР•") or ""
                article = item.get("артикул") or item.get("РђР РўРРљРЈР›") or ""
                value = item.get("значение") or item.get("Р·РЅР°С‡РµРЅРёРµ") or ""
                if name:
                    return f"Чаще всего заказывают: {name} (арт. {article}), заказов: {value}."
                if article:
                    return f"Чаще всего заказывают артикул {article}, заказов: {value}."
            return NO_DATA_RESPONSE

        # Category counts (ABC by frequency or weight).
        categories: List[str] = intent["categories"]
        abc_freq = summary.get("abc_по_частоте") or {}
        abc_weight = summary.get("abc_по_весу") or {}

        asks_weight = "вес" in q_norm or "весу" in q_norm
        abc_source = abc_weight if asks_weight and abc_weight else abc_freq

        if categories and intent["asks_count"]:
            parts = []
            for cat in categories:
                count = abc_source.get(cat)
                if count is None:
                    continue
                parts.append(f"{cat}: {count}")
            if parts:
                label = "по весу" if abc_source is abc_weight else "по частоте"
                return f"Количество товаров по ABC ({label}): " + ", ".join(parts) + "."
            return NO_DATA_RESPONSE

        if intent["asks_count"] and not categories:
            total_master = summary.get("количество_артикулов_мастер")
            total_picking = summary.get("количество_товаров_в_пикинге")
            if total_master is not None or total_picking is not None:
                return (
                    f"Артикулов в мастер-данных: {total_master or 0}. "
                    f"Товаров в пикинге: {total_picking or 0}."
                )

        # Top lists.
        if intent["asks_top"] or intent["asks_list"]:
            key = None
            metric_label = ""
            if "заказ" in q_norm:
                key = "топ10_по_заказам"
                metric_label = "заказов"
            elif "линий" in q_norm or "линии" in q_norm:
                key = "топ10_по_количеству_линий"
                metric_label = "линий"
            elif "реапро" in q_norm or "короб" in q_norm:
                key = "топ10_по_коробам_реапро"
                metric_label = "коробов реапро"
            elif "штук" in q_norm or "выход" in q_norm:
                key = "топ10_по_выходу_в_штуках"
                metric_label = "штук"

            if key and summary.get(key):
                return self._format_summary_list(summary[key], intent["limit"], metric_label)

        if intent["asks_bottom"]:
            if "залеж" in q_norm or "долго" in q_norm or "стар" in q_norm:
                key = "топ10_залежавшихся"
                metric_label = "дней без движения"
            else:
                key = "топ10_худших"
                metric_label = "заказов/выхода"
            if summary.get(key):
                return self._format_summary_list(summary[key], intent["limit"], metric_label)

        # Product lookup inside summary lists.
        product_tokens = self._extract_query_tokens(question)
        hit = self._find_in_summary_lists(summary, product_tokens)
        if hit:
            return hit

        # General fallback for ABC distribution.
        if intent["asks_category_info"] and (abc_freq or abc_weight):
            parts = []
            if abc_freq:
                parts.append("ABC по частоте: " + ", ".join(f"{k}: {v}" for k, v in abc_freq.items()))
            if abc_weight:
                parts.append("ABC по весу: " + ", ".join(f"{k}: {v}" for k, v in abc_weight.items()))
            return ". ".join(parts) + "."

        return None

    def _answer_from_combined_rows(self, question: str, q_norm: str, rows: List[Dict[str, Any]]) -> Optional[str]:
        if not rows:
            return None

        article = self._extract_article_code(question)
        if article:
            found = self._find_row_by_article(rows, article)
            if found:
                name = self._row_get(found, ["НАЗВАНИЕ", "РќРђР—Р’РђРќРР•"])
                aisle = self._row_get(found, ["Аллея пикинг", "РђР»Р»РµСЏ РїРёРєРёРЅРі"])
                place = self._row_get(found, ["Место пикинг", "РњРµСЃС‚Рѕ РїРёРєРёРЅРі"])
                if aisle is None and place is None:
                    return NO_DATA_RESPONSE
                label = name or article
                return f"{label}: аллея {aisle}, место {place}."

        if "алле" in q_norm:
            aisles = set()
            for row in rows:
                val = self._row_get(row, ["Аллея пикинг", "РђР»Р»РµСЏ РїРёРєРёРЅРі"])
                if val is None:
                    continue
                try:
                    aisles.add(int(float(val)))
                except Exception:
                    continue
            if aisles:
                return f"Учитывается аллей: {len(aisles)}."
            return NO_DATA_RESPONSE

        if any(word in q_norm for word in ["самый тяжел", "самый тяжёл", "тяжел", "тяжёл"]):
            best = None
            best_weight = None
            for row in rows:
                weight = self._row_get(row, ["Вес", "Р’РµСЃ"])
                if weight is None:
                    continue
                try:
                    w = float(weight)
                except Exception:
                    continue
                if best_weight is None or w > best_weight:
                    best_weight = w
                    best = row
            if best and best_weight is not None:
                name = self._row_get(best, ["НАЗВАНИЕ", "РќРђР—Р’РђРќРР•"])
                article = self._row_get(best, ["АРТИКУЛ", "РђР РўРРљРЈР›"])
                return f"Самый тяжелый товар: {name or article}, вес {best_weight}."
            return NO_DATA_RESPONSE

        return None

    def _extract_article_code(self, text: str) -> Optional[str]:
        pattern = re.compile(r"\b[A-Z]{2,}\d+[A-Z0-9-]*\b", re.IGNORECASE)
        match = pattern.search(text.upper())
        return match.group(0) if match else None

    def _find_row_by_article(self, rows: List[Dict[str, Any]], article: str) -> Optional[Dict[str, Any]]:
        key_variants = ["АРТИКУЛ", "РђР РўРРљРЈР›", "article", "арт", "артикул"]
        target = article.strip().upper()
        for row in rows:
            value = self._row_get(row, key_variants)
            if value is None:
                continue
            if str(value).strip().upper() == target:
                return row
        return None

    def _row_get(self, row: Dict[str, Any], keys: List[str]) -> Optional[Any]:
        for key in keys:
            if key in row:
                return row.get(key)
        normalized = {self._norm_key(k): k for k in row.keys()}
        for key in keys:
            nk = self._norm_key(key)
            real = normalized.get(nk)
            if real is not None:
                return row.get(real)
        return None

    def _norm_key(self, value: str) -> str:
        v = str(value).strip().lower()
        for ch in [" ", "\t", "\n", "\r", ".", ",", "-", "_", "/", "\\", "(", ")", "[", "]", "{", "}", '"', "'"]:
            v = v.replace(ch, "")
        return v

    def _format_summary_list(self, rows: List[Dict[str, Any]], limit: int, metric_label: str) -> str:
        if not rows:
            return NO_DATA_RESPONSE
        parts = []
        for idx, row in enumerate(rows[:limit], start=1):
            name = row.get("название") or row.get("РќРђР—Р’РђРќРР•") or row.get("name") or ""
            val = row.get("значение") or row.get("Р·РЅР°С‡РµРЅРёРµ") or row.get("value") or ""
            if not name:
                name = row.get("артикул") or row.get("РђР РўРРљРЈР›") or row.get("article") or ""
            if metric_label:
                parts.append(f"{idx}) {name} — {val} {metric_label}")
            else:
                parts.append(f"{idx}) {name} — {val}")
        return "; ".join(parts) + "."

    def _find_in_summary_lists(self, summary: Dict[str, Any], tokens: List[str]) -> Optional[str]:
        if not tokens:
            return None
        list_keys = [
            "топ10_по_заказам",
            "топ10_по_выходу_в_штуках",
            "топ10_по_количеству_линий",
            "топ10_по_коробам_реапро",
            "топ10_худших",
            "топ10_залежавшихся",
        ]
        for key in list_keys:
            rows = summary.get(key) or []
            for row in rows:
                name = str(row.get("название") or row.get("name") or "").lower()
                if name and all(t in name for t in tokens):
                    val = row.get("значение") or row.get("value") or ""
                    return f"{row.get('название') or row.get('name')}: {val}."
        return None

    def _is_capabilities_question(self, question: str) -> bool:
        q = self._normalize(question)
        triggers = [
            "что умеешь",
            "что ты умеешь",
            "что ты можешь",
            "что умеет",
            "чем помогаешь",
            "помощь",
            "справка",
            "кто ты",
            "ты кто",
            "о себе",
            "как пользоваться",
            "как работать",
            "инструкция",
        ]
        return any(t in q for t in triggers)

    def _capabilities_response(self) -> str:
        return (
            "Я помощник по данным склада и отчетам. Могу отвечать на вопросы по товарам, "
            "категориям ABC/XYZ, выручке, количествам, топ/анти‑топ, а также показывать "
            "сводные показатели по базе. Если запрос не содержит данных или слишком общий, "
            "я попрошу уточнить формулировку."
        )

    def _should_use_ollama(self, intent: Dict[str, Any]) -> bool:
        if not self.use_ollama:
            return False
        if self.force_ollama:
            return True

        if self.llm_mode == "auto":
            return True
        return self.llm_mode == "paraphrase"

    def _answer_with_ollama(
        self,
        question: str,
        rows: List[ProductRow],
        rows_by_db: Dict[str, int],
        summary: Dict[str, Any],
        deterministic_answer: str,
    ) -> Optional[str]:
        if self.llm_mode == "paraphrase":
            prompt = self._build_paraphrase_prompt(question, rows, rows_by_db, summary, deterministic_answer)
        elif self.llm_mode == "auto":
            if deterministic_answer in {NO_DATA_RESPONSE, CLARIFY_RESPONSE}:
                prompt = self._build_general_prompt(question, summary)
            else:
                prompt = self._build_paraphrase_prompt(question, rows, rows_by_db, summary, deterministic_answer)
        else:
            prompt = self._build_ollama_prompt(question, rows, rows_by_db, summary)
        if not prompt:
            return None
        candidate = self._ollama_generate(prompt)
        if not candidate:
            return None
        allow_questions = self.llm_mode == "auto" and deterministic_answer in {NO_DATA_RESPONSE, CLARIFY_RESPONSE}
        if not self._validate_llm_response(candidate, allow_questions=allow_questions):
            retry = self._build_paraphrase_retry_prompt(
                question,
                rows,
                rows_by_db,
                summary,
                deterministic_answer,
            )
            if not retry:
                return None
            candidate = self._ollama_generate(retry)
            if not candidate or not self._validate_llm_response(candidate, allow_questions=allow_questions):
                return None
        return candidate

    def _build_ollama_prompt(
        self,
        question: str,
        rows: List[ProductRow],
        rows_by_db: Dict[str, int],
        summary: Dict[str, Any],
    ) -> str:
        selected = self._select_rows_for_llm(question, rows)
        payload = {
            "summary": summary,
            "sources": rows_by_db,
            "rows": [
                {
                    "product_name": r.product_name,
                    "quantity": r.quantity,
                    "revenue": r.revenue,
                    "abc_category": r.abc_category,
                    "xyz_category": r.xyz_category,
                    "abc_xyz_category": r.abc_xyz_category,
                }
                for r in selected
            ],
        }

        instructions = (
            "Ты помощник склада. Отвечай только на основе DATA ниже. "
            "Всегда отвечай на русском языке. "
            "Если данных недостаточно, ответь строго: "
            f"\"{NO_DATA_RESPONSE}\". "
            "Если вопрос не ясен, ответь строго: "
            f"\"{CLARIFY_RESPONSE}\". "
            "Не придумывай факты. Отвечай кратко и по делу."
        )

        return (
            f"{instructions}\n\n"
            f"QUESTION: {question}\n\n"
            f"DATA (JSON):\n{json.dumps(payload, ensure_ascii=False)}\n"
        )

    def _build_paraphrase_prompt(
        self,
        question: str,
        rows: List[ProductRow],
        rows_by_db: Dict[str, int],
        summary: Dict[str, Any],
        deterministic_answer: str,
    ) -> str:
        selected = self._select_rows_for_llm(question, rows)
        payload = {
            "summary": summary,
            "sources": rows_by_db,
            "rows": [
                {
                    "product_name": r.product_name,
                    "quantity": r.quantity,
                    "revenue": r.revenue,
                    "abc_category": r.abc_category,
                    "xyz_category": r.xyz_category,
                    "abc_xyz_category": r.abc_xyz_category,
                }
                for r in selected
            ],
        }

        instructions = (
            "ВЫПОЛНЯЙ ТОЛЬКО ИНСТРУКЦИИ НИЖЕ.\n"
            "1) Всегда отвечай на русском языке.\n"
            "2) НЕЛЬЗЯ добавлять новые факты или числа.\n"
            "3) Можно ТОЛЬКО перефразировать и немного расширить ANSWER_TO_EXPAND.\n"
            "4) Никаких вопросов пользователю.\n"
            "5) Длина: 3–6 предложений, не более 600 символов.\n"
            "6) Если данных недостаточно, ответь строго: "
            f"\"{NO_DATA_RESPONSE}\".\n"
            "7) Если вопрос не ясен, ответь строго: "
            f"\"{CLARIFY_RESPONSE}\".\n"
            "8) Выведи ТОЛЬКО итоговый ответ, без пояснений."
        )

        return (
            f"{instructions}\n\n"
            f"QUESTION: {question}\n\n"
            f"ANSWER_TO_EXPAND: {deterministic_answer}\n\n"
            f"DATA (JSON):\n{json.dumps(payload, ensure_ascii=False)}\n"
        )

    def _build_general_prompt(self, question: str, summary: Optional[Dict[str, Any]] = None) -> str:
        instructions = (
            "Ты помощник по логистике и складу. Всегда отвечай на русском.\n"
            "Отвечай на общие вопросы о логистике, терминологии и возможностях ассистента.\n"
            "НЕЛЬЗЯ выдумывать факты, цифры или данные по складу.\n"
            "Если вопрос требует данных из БД/JSON, ответь строго:\n"
            f"\"{NO_DATA_RESPONSE}\"\n"
            "Не проси уточнений.\n"
            "Длина ответа: 2–5 предложений, до 450 символов.\n"
            "Выведи только итоговый ответ."
        )

        if summary:
            data_blob = json.dumps(summary, ensure_ascii=False)
            return f"{instructions}\n\nQUESTION: {question}\n\nDATA (JSON):\n{data_blob}\n"
        return f"{instructions}\n\nQUESTION: {question}\n"

    def _build_paraphrase_retry_prompt(
        self,
        question: str,
        rows: List[ProductRow],
        rows_by_db: Dict[str, int],
        summary: Dict[str, Any],
        deterministic_answer: str,
    ) -> str:
        payload = {
            "summary": summary,
            "sources": rows_by_db,
        }

        instructions = (
            "СТРОГО ВЫПОЛНИ:\n"
            "1) Ответ ТОЛЬКО на русском языке.\n"
            "2) Никаких вопросов пользователю.\n"
            "3) Никаких новых фактов и чисел.\n"
            "4) Перепиши ANSWER_TO_EXPAND почти дословно, "
            "допустимо только 1-2 коротких уточняющих фразы.\n"
            "5) Длина до 500 символов.\n"
            "6) Выведи ТОЛЬКО итоговый ответ."
        )

        return (
            f"{instructions}\n\n"
            f"QUESTION: {question}\n\n"
            f"ANSWER_TO_EXPAND: {deterministic_answer}\n\n"
            f"DATA (JSON):\n{json.dumps(payload, ensure_ascii=False)}\n"
        )

    def _select_rows_for_llm(self, question: str, rows: List[ProductRow]) -> List[ProductRow]:
        tokens = self._extract_query_tokens(question)
        hits = self._find_products(tokens, rows)
        if hits:
            return hits[:50]
        return rows[:50]

    def _ollama_generate(self, prompt: str) -> Optional[str]:
        url = self.ollama_url.rstrip("/") + "/api/generate"
        body = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.ollama_temperature,
                "top_p": self.ollama_top_p,
                "num_predict": self.ollama_max_tokens,
            },
        }

        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=6) as response:
                payload = json.loads(response.read().decode("utf-8"))
                text = (payload.get("response") or "").strip()
                return text or None
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError):
            return None

    def _validate_llm_response(self, text: str, allow_questions: bool = False) -> bool:
        if not text:
            return False
        if len(text) > 600:
            return False
        # Reject if it contains too much Latin or looks like it asks questions.
        latin = sum(1 for ch in text if "a" <= ch.lower() <= "z")
        cyr = sum(1 for ch in text if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
        total_letters = latin + cyr
        min_ratio = 0.6 if allow_questions else 0.8
        if total_letters > 0 and cyr / total_letters < min_ratio:
            return False
        if not allow_questions and "?" in text:
            return False
        return True

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
