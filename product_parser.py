"""
product_parser.py - Универсальный парсер для извлечения структурированной информации 
из текстовых описаний продуктов.
Версия 2.2 - Исправление ошибок
"""

import re
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime


class ProductInfoParser:
    """
    Универсальный парсер для извлечения структурированной информации 
    из текстовых описаний продуктов.
    """
    
    def __init__(self):
        # Регулярные выражения для различных полей
        self.patterns = {
            'product_name': [
                r'^#\s*(.+)$',  # Заголовок с #
                r'^([А-ЯA-Z][^\n]+?)(?:\n|$)',  # Первая строка как название
                r'(?:товар|продукт|название)[:\s]*([^\n]+)',  # Явное указание
                r'^([А-ЯA-Z][А-Яа-яA-Za-z0-9\s\-]+)(?:\n|$)',  # Любая первая строка
                r'Шампунь[^\n]*|Крем[^\n]*|Маска[^\n]*|Сыворотка[^\n]*|Тональный[^\n]*',
            ],
            'brand': [
                r'(?:бренд|brand)[:\s]*([^\n]+)',
                r'^([А-ЯA-Z][А-ЯA-Z\s]+)(?:\n|$)',  # Капслоком
                r'([А-ЯA-Z][а-яa-z]+)\s+[А-ЯA-Z][а-яa-z]+\s+',  # Два слова подряд
                r'(Kerasys|Dolce\s*&\s*Gabbana|Loreal|L\'Oreal|Maybelline|Nivea|Garnier|Febble)',
            ],
            'description': [
                r'(?:описание|description)[:\s]*([^\n]+)',
                r'(?:^|\n)([^\n]+?\.)(?:\n|$)',
                r'(?:ОБЪЕМ\s+И\s+БЛЕСК|ОБЬЕМ\s+И\s+БЛЕСК)\s*\n([^\n]+)',
                r'(?:Парфюмированная формула[^\n]+|Увлажняющий[^\n]+|Питательный[^\n]+)',
            ],
            'features': [
                r'[-•*]\s*([^\n]+)',  # Маркированные списки
                r'[#*]{1,3}\s*([^\n]+)',  # Заголовки списков
                r'(?:характеристики|features)[:\s]*([^\n]+(?:\n[^\n]+)*)',
                r'(\d+\s+[А-ЯA-Z][А-Яа-яA-Za-z\s]+)',  # "10 ЦВЕТОЧНЫХ ЭКСТРАКТОВ"
            ],
            'specifications': {
                'volume': [
                    r'(\d+(?:[.,]\d+)?)\s*(мл|ml|л|l|L)\b',
                    r'объем[:\s]*(\d+(?:[.,]\d+)?)\s*(мл|ml|л|l|L)',
                    r'(\d+(?:[.,]\d+)?)\s*(миллилитр|литр)',
                    r'(\d+)\s*ML',
                ],
                'weight': [
                    r'(\d+(?:[.,]\d+)?)\s*(г|g|кг|kg)\b',
                    r'вес[:\s]*(\d+(?:[.,]\d+)?)\s*(г|g|кг|kg)',
                    r'(\d+(?:[.,]\d+)?)\s*(грамм|килограмм)',
                ],
                'quantity_per_pack': [
                    r'(\d+)\s*[xх]\s*(\d+)\s*(мл|ml|л|l|г|g)',
                    r'(\d+)\s*шт',
                    r'количество[:\s]*(\d+)\s*шт',
                ],
            },
            'manufacturer': [
                r'(?:производитель|изготовитель|manufacturer)[:\s]*([^\n]+)',
                r'(?:manufacturer|made by)[:\s]*([^\n]+)',
                r'произв[.:]\s*([^\n]+)',
                r'(Aekyung|ZUEGG|I\.C\.O\.N|ZHE\s*JIANG)[^\n]*',
            ],
            'importer': [
                r'(?:импортер|импортёр|importer)[:\s]*([^\n]+)',
                r'(?:importer|imported by)[:\s]*([^\n]+)',
                r'Импортер[^:]*:\s*([^\n]+)',
                r'ООО\s*["“]([^"”]+)["”]',  # ООО "Название"
                r'ООО\s*«([^»]+)»',  # ООО «Название»
                r'(?:организация[,\s]+уполномоченная[^\n]+)[:\s]*([^\n]+)',
            ],
            'country': [
                r'(?:страна|country|сделано|made in)[:\s]*([^\n]+)',
                r'manufactured in[:\s]*([^\n]+)',
                r'(Республика\s+Корея|Россия|Китай|Корея|Франция|Италия|США|Германия|Япония|Бразилия)',
            ],
            'expiry_date': [
                r'(?:годен до|срок годности|expiry|expiration|годен)[:\s]*([^\n]+)',
                r'(?:до|by)[:\s]*(\d{2}[./]\d{2}[./]\d{2,4})',
                r'(\d{2}[./]\d{2}[./]\d{4})',
                r'(\d{2}\.\d{4})',  # 07.2027
                r'(\d{2}[/]\d{4})',  # 08/2028
            ],
            'manufacture_date': [
                r'(?:дата производства|manufacture date|произведено)[:\s]*([^\n]+)',
                r'(?:дата|date)[:\s]*(\d{2}[./]\d{2}[./]\d{2,4})',
            ],
            'batch_number': [
                r'(?:партия|lot|batch)[:\s]*([^\n]+)',
                r'lot[:\s]*([A-Z0-9]+)',
                r'№\s*партии[:\s]*([^\n]+)',
            ],
            'article_number': [
                r'(?:арт|article|артикул)[.\s]*(\d+)',
                r'(?:арт\.?\s*№?)\s*([A-ZА-Я0-9-]+)',
                r'Арт\.\s*(\d+)',
                r'^[А-Я]*(\d+)$',
            ],
            'barcode': [
                r'(\d{13})',
                r'(\d{12})',
                r'ean[:\s]*(\d+)',
                r'(\d{8,13})',
            ],
        }
        
        # ОСОБЫЙ ПРИОРИТЕТ ДЛЯ СОСТАВА - отдельный словарь с высокоприоритетными паттернами
        self.ingredients_patterns = [
            # Русские маркеры
            r'(?:состав|ингредиенты|компоненты)[:\s]*([^\n]+(?:,\s*[^,\n]+)*)',
            r'Состав\s*/\s*Ingredients[:\s]*([^\n]+)',
            r'INGREDIENTS?[:\s]*([^\n]+)',
            
            # Английские маркеры
            r'ingredients?[:\s]*([^\n]+)',
            r'composition[:\s]*([^\n]+)',
            
            # Список ингредиентов через запятую (много INCI названий)
            r'([A-Z][A-Z\s,]+(?:\([^)]+\))?(?:,\s*[A-Z][A-Z\s,]+)*)',
            
            # Конкретные паттерны из ваших примеров
            r'Состав[:\s]*([A-Z,\s]+(?:CI\s+\d+[,\s]*)+)',
            r'(?:HYDROGENATED|POLYISOBUTENE|POLYBUTENE|DIMETHICONE|SILICA)[A-Z\s,]+',
            
            # Для парфюмерных нот (не путать с составом)
            r'(?:Верхние ноты|Средние ноты|Нижние ноты)[:\s]*([^\n]+)',
        ]
        
        # Для парфюмерных нот - отдельно
        self.notes_patterns = {
            'top_notes': r'Верхние ноты[:\s]*([^\n]+)',
            'middle_notes': r'Средние ноты[:\s]*([^\n]+)',
            'base_notes': r'Нижние ноты[:\s]*([^\n]+)',
        }
        
    def parse_text(self, text: str) -> Dict[str, Any]:
        """
        Основной метод парсинга текста
        """
        if not text:
            return {}
        
        # Очистка текста
        text = self._clean_text(text)
        
        # Разбиваем текст на структурированные части
        structured_parts = self._split_text_into_parts(text)
        
        result = {
            'raw_text': text,
            'product_name': structured_parts.get('title') or self._safe_extract(self._extract_product_name, text),
            'original_name': structured_parts.get('original_name'),
            'product_description': structured_parts.get('description'),
            'article_number': structured_parts.get('article') or self._safe_extract(self._extract_article_number, text),
            'brand': self._safe_extract(self._extract_brand, text),
            'description': self._safe_extract(self._extract_description, text),
            'features': self._safe_extract(self._extract_features, text, default=[]),
            'specifications': self._safe_extract(self._extract_specifications, text, default={}),
            'ingredients': self._extract_ingredients(text),  # УЛУЧШЕНО
            'notes': self._extract_notes(text),  # Парфюмерные ноты
            'manufacturer': self._safe_extract(self._extract_manufacturer, text),
            'importer': self._safe_extract(self._extract_importer, text),
            'country': self._safe_extract(self._extract_country, text),
            'expiry_date': self._safe_extract(self._extract_expiry_date, text),
            'manufacture_date': self._safe_extract(self._extract_manufacture_date, text),
            'batch_number': self._safe_extract(self._extract_batch_number, text),
            'barcode': self._safe_extract(self._extract_barcode, text),
            'application': self._safe_extract(self._extract_application, text),
            'precautions': self._safe_extract(self._extract_precautions, text),
            'storage_conditions': self._safe_extract(self._extract_storage_conditions, text),
        }

        # Если название не найдено, берем первую непустую строку
        if not result['product_name'] and text:
            first_line = text.split('\n')[0].strip()
            if first_line and len(first_line) < 100:
                result['product_name'] = first_line

        result['label_description'] = self._build_label_description(result)
        return result
    
    def _split_text_into_parts(self, text: str) -> Dict[str, Optional[str]]:
        """
        Разбивает текст на структурированные части:
        - title: название (первая строка до первого переноса)
        - original_name: оригинальное название на английском (идет ниже)
        - description: описание товара (все остальное)
        - article: артикул (отдельно внизу)
        """
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return {}
        
        result = {}
        
        # 1. Название - первая строка (до первого переноса)
        if lines:
            result['title'] = lines[0]
        
        # 2. Оригинальное название - ищем английскую строку после названия
        # Обычно это строка, которая содержит латинские буквы и идет после названия
        original_name = None
        start_idx = 1 if lines else 0
        
        for i in range(start_idx, min(start_idx + 5, len(lines))):
            line = lines[i]
            # Проверяем, что строка содержит преимущественно латинские буквы
            latin_chars = sum(1 for c in line if c.isalpha() and ord(c) < 128)
            cyrillic_chars = sum(1 for c in line if '\u0400' <= c <= '\u04FF')
            
            # Если больше латинских букв и нет кириллицы (или очень мало)
            if latin_chars > cyrillic_chars * 2 and len(line) > 5:
                # Проверяем, что это не техническая информация
                if not any(keyword in line.lower() for keyword in ['состав', 'ingredients', 'изготовитель', 'manufacturer', 'импортер', 'importer']):
                    original_name = line
                    start_idx = i + 1
                    break
        
        result['original_name'] = original_name
        
        # 3. Описание - все остальное между оригинальным названием и артикулом
        # Ищем артикул в конце текста
        article = None
        article_idx = len(lines)
        
        # Ищем артикул в последних строках
        for i in range(len(lines) - 1, max(len(lines) - 5, start_idx - 1), -1):
            line = lines[i].lower()
            if 'арт' in line or 'art' in line or re.search(r'арт\.?\s*\d+', line, re.IGNORECASE):
                # Извлекаем артикул
                article_match = re.search(r'арт\.?\s*(\d+)', lines[i], re.IGNORECASE)
                if article_match:
                    article = f"Арт. {article_match.group(1)}"
                else:
                    article = lines[i]
                article_idx = i
                break
        
        # Формируем описание из всех строк между оригинальным названием и артикулом
        description_lines = []
        for i in range(start_idx, article_idx):
            line = lines[i]
            # Пропускаем пустые строки и технические маркеры
            if line and not any(keyword in line.lower() for keyword in ['арт', 'art']):
                description_lines.append(line)
        
        result['description'] = '\n'.join(description_lines) if description_lines else None
        result['article'] = article
        
        return result

    def _safe_extract(self, extractor, text: str, default=None):
        """Безопасно вызывает extractor: не падает на пустом тексте или ошибках regex."""
        try:
            return extractor(text)
        except re.error:
            return default
        except Exception:
            return default

    def _build_label_description(self, parsed: Dict[str, Any]) -> str:
        """
        Формирует универсальное описание для макета этикетки:
        название + свойства + ключевые блоки.
        """
        parts: List[str] = []

        product_name = (parsed.get('product_name') or '').strip()
        if product_name:
            parts.append(product_name)

        base_desc = (parsed.get('description') or '').strip()
        if base_desc and base_desc.lower() != product_name.lower():
            parts.append(base_desc)

        features = parsed.get('features') or []
        for feature in features[:8]:
            cleaned = str(feature).strip(' -•*')
            if cleaned:
                parts.append(f"- {cleaned}")

        if parsed.get('application'):
            parts.append(f"Способ применения: {parsed['application']}")
        if parsed.get('precautions'):
            parts.append(f"Меры предосторожности: {parsed['precautions']}")
        if parsed.get('ingredients'):
            parts.append(f"Состав: {parsed['ingredients']}")
        if parsed.get('manufacturer'):
            parts.append(f"Изготовитель: {parsed['manufacturer']}")
        if parsed.get('importer'):
            parts.append(f"Импортер: {parsed['importer']}")

        unique_parts: List[str] = []
        seen = set()
        for p in parts:
            normalized = re.sub(r'\s+', ' ', p).strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_parts.append(re.sub(r'\s+', ' ', p).strip())

        return "\n".join(unique_parts)

    def _clean_text(self, text: str) -> str:
        """
        Очистка текста от лишних пробелов и спецсимволов
        """
        # Замена множественных переносов строк
        text = re.sub(r'\n\s*\n', '\n', text)
        # Удаление лишних пробелов
        text = re.sub(r'[ \t]+', ' ', text)
        # Унификация переводов строк
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        return text.strip()
    
    def _extract_product_name(self, text: str) -> Optional[str]:
        """
        Извлекает название продукта (наиболее вероятный кандидат).
        """
        lines = [ln.strip(' -•*\t') for ln in text.split('\n')]
        lines = [ln for ln in lines if ln and len(ln) >= 3]
        if not lines:
            return None

        bad_prefixes = (
            'состав', 'ingredients', 'изготовитель', 'производитель', 'импортер',
            'импортёр', 'способ применения', 'меры предосторожности', 'срок годности',
            'годен до', 'дата', 'партия', 'batch', 'lot'
        )

        for ln in lines[:12]:
            low = ln.lower()
            if any(low.startswith(bp) for bp in bad_prefixes):
                continue
            if len(ln) > 120:
                continue
            if re.fullmatch(r'[\d\W_]+', ln):
                continue
            return ln
        return lines[0] if lines else None

    
    def _extract_brand(self, text: str) -> Optional[str]:
        """
        Извлечение бренда - ИСПРАВЛЕНО
        """
        # Сначала ищем явные указания
        for pattern in self.patterns['brand']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Проверяем, есть ли группы захвата
                if match.groups():
                    brand = match.group(1).strip()
                else:
                    brand = match.group(0).strip()
                if brand and len(brand) < 50:
                    return brand
        
        # Затем ищем известные бренды
        known_brands = ['Kerasys', 'Dolce & Gabbana', 'L\'Oreal', 'Maybelline', 'Nivea', 
                        'Garnier', 'Febble', 'ZUEGG', 'I.C.O.N.', 'Aekyung']
        for brand in known_brands:
            if brand.lower() in text.lower():
                return brand
        
        return None
    
    def _extract_description(self, text: str) -> Optional[str]:
        """
        Извлечение описания
        """
        # 1) Приоритетный блок для косметики/шампуней
        heading_match = re.search(
            r'(?im)^(?:\u041e\u0411\u042a\u0415\u041c|\u041e\u0411\u042a\u0401\u041c)\s+\u0418\s+\u0411\u041b\u0415\u0421\u041a\s*$',
            text
        )
        if heading_match:
            tail = text[heading_match.end():]
            for line in tail.split('\n'):
                candidate = line.strip()
                if not candidate:
                    continue
                if candidate.startswith('-'):
                    continue
                if len(candidate) > 10:
                    return candidate

        # 2) Явное поле "Описание:"
        explicit = re.search(r'(?is)(?:\u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435|description)\s*:\s*([^\n]+)', text)
        if explicit:
            desc = explicit.group(1).strip()
            if 10 < len(desc) < 500:
                return desc

        # 3) Фолбэк по ключевым словам
        for line in text.split('\n'):
            candidate = line.strip()
            if len(candidate) < 15:
                continue
            if candidate.startswith('-'):
                continue
            if re.search(
                r'(\u043f\u0430\u0440\u0444\u044e\u043c\u0438\u0440\u043e\u0432\u0430\u043d\u043d|\u0443\u0432\u043b\u0430\u0436\u043d\u044f\u044e\u0449|\u043f\u0438\u0442\u0430\u0442\u0435\u043b\u044c\u043d|\u043e\u0431\u044a\u0435\u043c|\u043e\u0431\u044a\u0451\u043c|\u0431\u043b\u0435\u0441\u043a)',
                candidate,
                re.IGNORECASE
            ):
                return candidate
        return None
    
    def _extract_features(self, text: str) -> List[str]:
        """
        Извлекает особенности/характеристики.
        """
        features: List[str] = []

        bullet_lines = re.findall(r'(?m)^\s*[-•*]\s*([^\n]{2,140})\s*$', text)
        features.extend([f.strip() for f in bullet_lines if f.strip()])

        numeric_lines = re.findall(r'(?im)^\s*(\d+\s+[^\n]{2,80})\s*$', text)
        for f in numeric_lines:
            cleaned = re.sub(r'\s+', ' ', f).strip()
            if cleaned and not cleaned.lower().startswith(('годен', 'срок', 'batch', 'lot')):
                features.append(cleaned)

        unique: List[str] = []
        seen = set()
        for f in features:
            normalized = re.sub(r'\s+', ' ', f).strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(re.sub(r'\s+', ' ', f).strip())

        return unique[:10]

    
    def _extract_specifications(self, text: str) -> Dict[str, Any]:
        """
        Извлечение технических характеристик
        """
        specs = {}
        
        for spec_name, patterns in self.patterns['specifications'].items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) > 1:
                        # Если есть группа с единицей измерения
                        value = groups[0].strip()
                        unit = groups[1].strip() if len(groups) > 1 else None
                        specs[spec_name] = {
                            'value': value,
                            'unit': unit,
                            'full': match.group(0).strip()
                        }
                    elif groups:
                        specs[spec_name] = groups[0].strip()
                    else:
                        specs[spec_name] = match.group(0).strip()
                    break  # Используем первое найденное значение
        
        return specs
    
    def _extract_ingredients(self, text: str) -> Optional[str]:
        """
        УЛУЧШЕННОЕ извлечение состава
        """
        # Сначала ищем по специальным паттернам состава
        for pattern in self.ingredients_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                if match.groups():
                    ingredients = match.group(1).strip()
                else:
                    ingredients = match.group(0).strip()
                
                # Проверяем, что это похоже на состав (много INCI названий)
                if ingredients and len(ingredients) > 5:
                    # Если это список через запятую и есть заглавные буквы
                    if ',' in ingredients and re.search(r'[A-Z]{2,}', ingredients):
                        return ingredients
                    # Если это просто длинный текст, но похож на состав
                    elif len(ingredients) > 20 and not re.search(r'[а-я]{10,}', ingredients):
                        return ingredients
                    # Или просто возвращаем, если ничего другого нет
                    elif len(ingredients) > 10:
                        return ingredients
        
        # Ищем блок с INCI названиями (капслоком через запятую)
        inci_match = re.search(r'([A-Z][A-Z\s,]+(?:\([^)]+\))?(?:,\s*[A-Z][A-Z\s,]+){5,})', text)
        if inci_match:
            return inci_match.group(1).strip()
        
        # Ищем строку с "Состав:" и берем все до конца строки или до следующего маркера
        ru_ingredients_match = re.search(r'Состав[:\s]*([^\n]+)', text, re.IGNORECASE)
        if ru_ingredients_match:
            return ru_ingredients_match.group(1).strip()
        
        # Для файла с маской для губ Febble - специальная обработка
        if 'HYDROGENATED POLYISOBUTENE' in text or 'POLYBUTENE' in text:
            # Ищем весь блок с составом
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if 'Состав:' in line or 'INGREDIENTS' in line.upper():
                    # Собираем следующие строки до пустой
                    ingredients = []
                    for j in range(i, min(i+20, len(lines))):
                        if lines[j].strip() and not any(x in lines[j].lower() for x in ['годен', 'срок', 'арт', 'производитель']):
                            ingredients.append(lines[j].strip())
                        else:
                            break
                    return ' '.join(ingredients)
        
        return None
    
    def _extract_notes(self, text: str) -> Dict[str, str]:
        """
        Извлечение парфюмерных нот
        """
        notes = {}
        for note_type, pattern in self.notes_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    notes[note_type] = match.group(1).strip()
                else:
                    notes[note_type] = match.group(0).strip()
        return notes if notes else None
    
    def _extract_manufacturer(self, text: str) -> Optional[str]:
        """
        Извлечение производителя
        """
        for pattern in self.patterns['manufacturer']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        return None
    
    def _extract_importer(self, text: str) -> Optional[str]:
        """
        Извлечение импортера
        """
        for pattern in self.patterns['importer']:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        return None
    
    def _extract_country(self, text: str) -> Optional[str]:
        """
        Извлечение страны
        """
        for pattern in self.patterns['country']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        return None
    
    def _extract_expiry_date(self, text: str) -> Optional[str]:
        """
        Извлечение срока годности
        """
        for pattern in self.patterns['expiry_date']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        return None
    
    def _extract_manufacture_date(self, text: str) -> Optional[str]:
        """
        Извлечение даты производства
        """
        for pattern in self.patterns['manufacture_date']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        return None
    
    def _extract_batch_number(self, text: str) -> Optional[str]:
        """
        Извлечение номера партии
        """
        for pattern in self.patterns['batch_number']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        return None
    
    def _extract_article_number(self, text: str) -> Optional[str]:
        """
        Извлечение артикула
        """
        for pattern in self.patterns['article_number']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        return None
    
    def _extract_barcode(self, text: str) -> Optional[str]:
        """
        Извлечение штрих-кода
        """
        for pattern in self.patterns['barcode']:
            match = re.search(pattern, text)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        return None
    
    def _extract_application(self, text: str) -> Optional[str]:
        """
        Извлечение способа применения
        """
        patterns = [
            r'(?:способ применения|применение|usage|application)[:\s]*([^\n]+)',
            r'(?:^|\n)([^\n]*нанести[^\n]*(?:\.\s*[^\n]+)*)',
            r'Нанести[^\n]+вспенить[^\n]+',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        return None
    
    def _extract_precautions(self, text: str) -> Optional[str]:
        """
        Извлечение мер предосторожности
        """
        patterns = [
            r'(?:меры предосторожности|предупреждение|precautions)[:\s]*([^\n]+)',
            r'(?:беречь|хранить|избегать)[^\n]+',
            r'только\s+для\s+наружного\s+применения[^\n]*',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        return None
    
    def _extract_storage_conditions(self, text: str) -> Optional[str]:
        """
        Извлечение условий хранения
        """
        patterns = [
            r'(?:условия хранения|хранение|storage)[:\s]*([^\n]+)',
            r'хранить[^\n]+температур[^\n]+',
            r'Хранить[^\n]+',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        return None
    
    def parse_multiple_texts(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Парсинг нескольких текстов
        """
        return [self.parse_text(text) for text in texts]
    
    def to_json(self, data: Dict[str, Any], indent: int = 2) -> str:
        """
        Конвертация результата в JSON
        """
        return json.dumps(data, ensure_ascii=False, indent=indent)


# Функция для тестирования парсера
def test_parser():
    """Тестирование парсера на примерах"""
    parser = ProductInfoParser()
    
    test_cases = [
        {
            'name': 'Шампунь Kerasys',
            'text': '''
# Шампунь для волос
ЭГУН КЕРАСИС
ПАРФЮМИРОВАННАЯ ЛИНИЯ ЭЛЕГАНС

Kerasys Classic Perfume Shampoo Elegance & Sensual

ОБЪЕМ И БЛЕСК
Парфюмированная формула с 10 цветочными экстрактами и 3 травяными маслами.

- 10 ЦВЕТОЧНЫХ ЭКСТРАКТОВ
- 3 ТРАВЯНЫХ МАСЛА
- АМИНОКИСЛОТЫ

Состав: вода, лаурет сульфат натрия, кокамидопропил бетаин

Объем: 500 мл
Производитель: Aekyung Ind. Co., Ltd.
Страна: Республика Корея
Арт. 313756
'''
        },
        {
            'name': 'Маска для губ Febble',
            'text': '''
# Плодовая маска для увеличения объема губ Febble

Состав: HYDROGENATED POLYISOBUTENE, POLYBUTENE, DIISOSTEARYL MALEATE, SILICA DIMETHYL SILYLATE, HYDROGENATED STYRENE/ISOPRENE COPOLYMER, TRIDECYL TRIMMELLITATE, TOCOPHERYL ACETATE, SIMMONDSIA CHINENSIS (JOJOBA) SEED OIL, PHENOXYETHANOL, BUTYROSPERMUM PARKII (SHEA) BUTTER, ASCORBYL TETRAISOPALMITATE, LECITHIN, POLYHYDROXYSTEARIC ACID, ETHYLHEXYL PALMITATE, ISOSTEARIC ACID, ISOPROPYL MYRISTATE, POLYGLYCERYL-3 POLYRICINIOLEATE, ETHYLHEXYLGLYCERIN, CALCIUM SODIUM BOROSILICATE, SYNTHETIC FLUORPHLOGOPITE, TIN OXIDE, FRAGRANCE, IRON OXIDES (CI 77492), IRON OXIDES (CI 77491), IRON OXIDES (CI 77499), TITANIUM DIOXIDE (CI 77891), FD&C YELLOW NO.5 AL LAKE (CI 19140), FD&C BLUE NO.1 AL LAKE (CI 42090), FD&C RED NO.40 AL LAKE (CI 16035), D&C RED NO.6 BA LAKE (CI 15850), D&C RED NO.7 CA LAKE (CI 15850), D&C RED NO.27 AL LAKE (CI 45410)

Годен до: 07.2027
Арт. FBC066
'''
        },
        {
            'name': 'Тональный крем',
            'text': '''
DOLCE & GABBANA FLAWLESS LOOK
Стойкий матовый тональный крем EVERLAST FOUNDATION SPF20 PA+++, 01N LIGHT 27 мл

Состав: см. на упаковке после слова Ingredients.
Изготовитель: Dolce & Gabbana Beauty S.r.l., Italy
'''
        }
    ]
    
    for test in test_cases:
        print(f"\n{'='*50}")
        print(f"ТЕСТ: {test['name']}")
        print('='*50)
        
        result = parser.parse_text(test['text'])
        
        print(f"Товар: {result['product_name']}")
        print(f"Бренд: {result['brand']}")
        print(f"Состав: {result['ingredients']}")
        if result.get('notes'):
            print(f"Ноты: {result['notes']}")
        print(f"Производитель: {result['manufacturer']}")
        print(f"Страна: {result['country']}")
        print(f"Срок годности: {result['expiry_date']}")
        print(f"Артикул: {result['article_number']}")
        
        if result['ingredients']:
            print(f"✅ Состав найден! ({len(result['ingredients'])} символов)")
        else:
            print("❌ Состав не найден!")


if __name__ == '__main__':
    test_parser()



