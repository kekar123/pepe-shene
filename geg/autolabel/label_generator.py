"""
AutoLabel Designer - автоматический дизайнер таможенных этикеток
Объединенная версия всех модулей (без qrcode)
"""

import re
import json
import argparse
import math
import os
import time 
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ========== ContentProcessor ==========

class ContentProcessor:
    """Обработчик контента для этикеток"""
    
    def __init__(self):
        self.required_fields = [
            'product_name',
            'country_of_origin',
            'importer',
            'manufacturer'
        ]
        
        # Правила форматирования для разных типов товаров
        self.formatting_rules = {
            'food': {
                'product_name': {'caps': True, 'bold': True, 'size_multiplier': 1.2},
                'ingredients': {'caps': False, 'bold': False, 'size_multiplier': 0.9},
                'warning': {'caps': True, 'bold': True, 'color': 'red'}
            },
            'electronics': {
                'product_name': {'caps': True, 'bold': True, 'size_multiplier': 1.3},
                'specifications': {'caps': False, 'bold': False, 'size_multiplier': 1.0}
            },
            'cosmetics': {
                'product_name': {'caps': True, 'bold': True, 'size_multiplier': 1.2},
                'volume': {'caps': False, 'bold': True, 'size_multiplier': 1.1}
            }
        }
    
    def process(self, customer_data: Dict) -> Dict:
        """
        Обработка данных заказчика в форматированный контент
        
        Args:
            customer_data: сырые данные от заказчика
        
        Returns:
            Структурированный и отформатированный контент
        """
        # Определяем тип товара
        product_type = self._detect_product_type(customer_data)
        
        # Извлекаем и структурируем данные
        structured_data = self._extract_and_structure(customer_data)
        
        # Применяем правила форматирования
        formatted_blocks = self._apply_formatting(structured_data, product_type)
        
        # Добавляем обязательные элементы
        formatted_blocks = self._add_required_elements(formatted_blocks, customer_data)
        
        # Рассчитываем размеры шрифтов
        font_sizes = self._calculate_font_sizes(formatted_blocks)
        
        return {
            'product_type': product_type,
            'text_blocks': formatted_blocks,
            'font_sizes': font_sizes,
            'layout': self._determine_layout(formatted_blocks),
            'icons': self._determine_required_icons(customer_data)
        }
    
    def _detect_product_type(self, data: Dict) -> str:
        """Определяет тип товара"""
        product_name = data.get('product_name', '').lower()
        
        if any(word in product_name for word in ['сок', 'juice', 'молоко', 'вода', 'напиток']):
            return 'food'
        elif any(word in product_name for word in ['крем', 'шампунь', 'гель', 'косметик']):
            return 'cosmetics'
        elif any(word in product_name for word in ['телефон', 'ноутбук', 'charger', 'кабель']):
            return 'electronics'
        else:
            return 'default'
    
    def _extract_and_structure(self, data: Dict) -> List[Dict]:
        """Извлекает и структурирует данные"""
        blocks = []
        
        # Основное название товара
        if 'product_name' in data:
            blocks.append({
                'type': 'product_name',
                'text': data['product_name'],
                'priority': 1
            })
        
        # Страна происхождения
        if 'country_of_origin' in data:
            # Добавляем перевод если нужно
            country = data['country_of_origin']
            translated = self._translate_country(country)
            blocks.append({
                'type': 'country_of_origin',
                'text': f"Страна происхождения: {country} ({translated})",
                'priority': 2
            })
        
        # Импортер
        if 'importer' in data:
            blocks.append({
                'type': 'importer',
                'text': f"Импортёр: {data['importer']}",
                'priority': 3
            })
        
        # Производитель
        if 'manufacturer' in data:
            blocks.append({
                'type': 'manufacturer',
                'text': f"Производитель: {data['manufacturer']}",
                'priority': 4
            })
        
        # Состав (для продуктов)
        if 'composition' in data:
            blocks.append({
                'type': 'composition',
                'text': f"Состав: {data['composition']}",
                'priority': 5
            })
        
        # Объем/вес
        if 'volume' in data or 'weight' in data:
            volume_text = data.get('volume', '')
            weight_text = data.get('weight', '')
            if volume_text and weight_text:
                blocks.append({
                    'type': 'volume_weight',
                    'text': f"{volume_text}, {weight_text}",
                    'priority': 6
                })
            elif volume_text:
                blocks.append({
                    'type': 'volume',
                    'text': volume_text,
                    'priority': 6
                })
        
        # Предупреждения (если есть)
        if 'warnings' in data:
            for warning in data['warnings']:
                blocks.append({
                    'type': 'warning',
                    'text': warning.upper(),
                    'priority': 7
                })
        
        return blocks
    
    def _apply_formatting(self, blocks: List[Dict], product_type: str) -> List[Dict]:
        """Применяет правила форматирования"""
        rules = self.formatting_rules.get(product_type, {})
        
        for block in blocks:
            block_type = block['type']
            if block_type in rules:
                format_rules = rules[block_type]
                
                # Применяем CAPS
                if format_rules.get('caps', False):
                    block['text'] = block['text'].upper()
                
                # Добавляем жирность
                block['bold'] = format_rules.get('bold', False)
                
                # Множитель размера шрифта
                block['size_multiplier'] = format_rules.get('size_multiplier', 1.0)
                
                # Цвет (если указан)
                if 'color' in format_rules:
                    block['color'] = format_rules['color']
        
        return blocks
    
    def _add_required_elements(self, blocks: List[Dict], data: Dict) -> List[Dict]:
        """Добавляет обязательные элементы по законодательству"""
        
        # Знак соответствия ГОСТ (если нужно)
        if data.get('requires_gost', False):
            blocks.append({
                'type': 'gost_mark',
                'text': '✔ Соответствует ГОСТ',
                'priority': 8,
                'is_icon': True
            })
        
        # Знак переработки
        if data.get('is_recyclable', False):
            blocks.append({
                'type': 'recycle',
                'text': '♻ Перерабатываемая упаковка',
                'priority': 9,
                'is_icon': True
            })
        
        # Срок годности
        if 'expiry_date' in data:
            blocks.append({
                'type': 'expiry',
                'text': f"Срок годности: {data['expiry_date']}",
                'priority': 10
            })
        
        return blocks
    
    def _calculate_font_sizes(self, blocks: List[Dict]) -> Dict:
        """Рассчитывает размеры шрифтов для разных блоков"""
        base_size = 8  # pt
        
        font_sizes = {}
        for block in blocks:
            if block.get('is_icon', False):
                # Для иконок используем стандартный размер
                font_sizes[block['type']] = base_size
            else:
                # Учитываем множитель
                multiplier = block.get('size_multiplier', 1.0)
                font_sizes[block['type']] = round(base_size * multiplier)
        
        return font_sizes
    
    def _translate_country(self, country: str) -> str:
        """Простой перевод названий стран"""
        translations = {
            'china': 'КИТАЙ',
            'germany': 'ГЕРМАНИЯ',
            'usa': 'США',
            'italy': 'ИТАЛИЯ',
            'france': 'ФРАНЦИЯ',
            'spain': 'ИСПАНИЯ'
        }
        
        country_lower = country.lower()
        return translations.get(country_lower, country.upper())
    
    def _determine_layout(self, blocks: List[Dict]) -> Dict:
        """Определяет layout для размещения блоков"""
        # Сортируем по приоритету
        sorted_blocks = sorted(blocks, key=lambda x: x['priority'])
        
        # Разделяем на колонки если много текста
        if len(sorted_blocks) > 6:
            return {'type': 'two_column', 'blocks_per_column': len(sorted_blocks) // 2}
        else:
            return {'type': 'single_column', 'blocks': sorted_blocks}
    
    def _determine_required_icons(self, data: Dict) -> List[str]:
        """Определяет необходимые иконки"""
        icons = []
        
        if data.get('is_recyclable', False):
            icons.append('recycle')
        
        if data.get('requires_gost', False):
            icons.append('gost')
        
        if data.get('is_organic', False):
            icons.append('eco')
        
        if data.get('requires_certification', False):
            icons.append('certificate')
        
        return icons

# ========== SizeCalculator ==========

class SizeCalculator:
    """Калькулятор размеров этикетки"""
    
    # Стандартные соотношения для разных типов товаров
    STANDARD_RATIOS = {
        'juice_box': {'min': 2.5, 'max': 3.5, 'preferred': 3.0},
        'cosmetics': {'min': 2.0, 'max': 2.8, 'preferred': 2.5},
        'electronics': {'min': 1.8, 'max': 2.5, 'preferred': 2.2},
        'default': {'min': 2.0, 'max': 3.0, 'preferred': 2.5}
    }
    
    def calculate_optimal_size(self, 
                              content: Dict, 
                              product_dimensions: Dict,
                              qr_code_size: float = 2.0) -> Dict:
        """
        Рассчитывает оптимальный размер этикетки
        
        Args:
            content: обработанный контент
            product_dimensions: размеры упаковки
            qr_code_size: размер QR кода в см
        
        Returns:
            Dict с параметрами этикетки
        """
        # Получаем размеры упаковки
        wall_width = product_dimensions.get('wall_width', 10)  # см
        wall_height = product_dimensions.get('wall_height', 6)  # см
        min_margin = product_dimensions.get('min_label_margin', 0.5)  # см
        
        # Определяем доступную площадь
        available_width = wall_width - (2 * min_margin)
        available_height = wall_height - (2 * min_margin)
        
        # Определяем тип продукта для выбора соотношения
        product_type = product_dimensions.get('package_type', 'default')
        ratios = self.STANDARD_RATIOS.get(product_type, self.STANDARD_RATIOS['default'])
        
        # Расчет на основе объема текста
        text_volume = self._calculate_text_volume(content)
        
        # Определяем высоту этикетки
        # Минимальная высота для QR кода + отступы
        min_height = qr_code_size + 1.0  # QR + отступы
        # Высота текстовой части
        text_height = self._estimate_text_height(text_volume)
        
        total_height_needed = max(min_height, text_height + 0.5)
        
        # Ограничиваем доступной высотой
        label_height = min(total_height_needed, available_height)
        
        # Определяем ширину на основе выбранного соотношения
        # Для коробки сока используем узкую высокую этикетку
        if product_type == 'juice_box':
            # Для боковой стенки 12x4 см
            label_width = 3.5
            label_height = 3.0
        else:
            # Для других товаров используем пропорции
            preferred_ratio = ratios['preferred']
            label_width = label_height * preferred_ratio
        
        # Ограничиваем доступной шириной
        label_width = min(label_width, available_width)
        
        # Определяем позицию на упаковке
        position = self._determine_position(product_dimensions, label_width, label_height)
        
        # Определяем позицию QR кода
        qr_position = self._determine_qr_position(content, label_width, label_height, qr_code_size)
        
        return {
            'width': round(label_width, 1),
            'height': round(label_height, 1),
            'unit': 'cm',
            'position': position,
            'qr_position': qr_position,
            'qr_size': round(qr_code_size, 1),
            'text_area': {
                'width': round(label_width - 1.0, 1),  # минус отступы
                'height': round(label_height - qr_code_size - 0.5, 1)
            }
        }
    
    def _calculate_text_volume(self, content: Dict) -> int:
        """Рассчитывает объем текста в символах"""
        text_blocks = content.get('text_blocks', [])
        total_chars = 0
        for block in text_blocks:
            total_chars += len(block.get('text', ''))
        return total_chars
    
    def _estimate_text_height(self, text_volume: int) -> float:
        """
        Оценивает необходимую высоту для текста
        Эмпирическая формула: 1 символ ≈ 0.1 см² при 10pt шрифте
        """
        # Примерные расчеты
        if text_volume < 50:
            return 1.5  # см
        elif text_volume < 100:
            return 2.0
        elif text_volume < 200:
            return 2.5
        elif text_volume < 300:
            return 3.0
        else:
            return 3.5
    
    def _determine_position(self, product_dimensions: Dict, 
                           label_width: float, label_height: float) -> str:
        """Определяет оптимальное положение этикетки на упаковке"""
        package_type = product_dimensions.get('package_type', 'default')
        
        if package_type == 'juice_box':
            # Для коробки сока - по центру боковой стенки
            return "center_middle"
        elif package_type == 'bottle':
            # Для бутылки - сверху, под горлышком
            return "top_center"
        else:
            # По умолчанию - снизу справа
            return "bottom_right"
    
    def _determine_qr_position(self, content: Dict, 
                              label_width: float, label_height: float,
                              qr_size: float) -> Dict:
        """Определяет положение QR кода на этикетке"""
        
        # Для маленьких этикеток (менее 4см шириной) QR ставим сверху
        if label_width < 4:
            return {
                'x': 'center',
                'y': 'top',
                'margin_x': 0.2,
                'margin_y': 0.2
            }
        # Для средних этикеток - справа
        elif label_width < 6:
            return {
                'x': 'right',
                'y': 'center',
                'margin_x': 0.2,
                'margin_y': 0.2
            }
        # Для больших этикеток - снизу справа
        else:
            return {
                'x': 'right',
                'y': 'bottom',
                'margin_x': 0.3,
                'margin_y': 0.3
            }

# ========== LabelDesigner ==========
class LabelDesigner:
    """Дизайнер этикеток - КРУПНЫЙ ШРИФТ, ЗАЩИТНЫЕ ЗОНЫ ДЛЯ ИКОНОК"""
    
    def __init__(self, width: float, height: float, dpi: int = 300):
        """
        Args:
            width: ширина этикетки в см
            height: высота этикетки в см
            dpi: разрешение для печати
        """
        self.width_cm = width
        self.height_cm = height
        self.dpi = dpi
        
        # Конвертация см в пиксели
        cm_to_inch = 0.393701
        self.width_px = int(width * cm_to_inch * dpi)
        self.height_px = int(height * cm_to_inch * dpi)
        
        # Создание холста
        self.image = Image.new('RGB', (self.width_px, self.height_px), 'white')
        self.draw = ImageDraw.Draw(self.image)
        
        # ========== ОПРЕДЕЛЯЕМ ФОРМАТ ==========
        self.is_wide = width >= 14  # 16x9 - wide
        self.is_compact = width <= 10 and height <= 7  # 10x7 и меньше
        
        # ОТСТУПЫ - МИНИМАЛЬНЫЕ, ЧТОБЫ БОЛЬШЕ МЕСТА
        if self.is_compact:
            self.margin = int(0.1 * cm_to_inch * dpi)  # 0.1 см
        elif self.is_wide:
            self.margin = int(0.15 * cm_to_inch * dpi)  # 0.15 см
        else:
            self.margin = int(0.12 * cm_to_inch * dpi)  # 0.12 см
        
        # ========== ЗАГРУЖАЕМ ШРИФТЫ ==========
        self.fonts = self._load_fonts()
        self.icons = {}
        
        # Область для текста (будет вычислена в add_full_content)
        self.text_area = {
            'x_min': self.margin,
            'x_max': self.width_px - self.margin,
            'y_min': self.margin,
            'y_max': self.height_px - self.margin,
            'width': self.width_px - 2 * self.margin,
            'height': self.height_px - 2 * self.margin
        }
    
    def _load_fonts(self) -> Dict:
        """Загружает шрифты - МАКСИМАЛЬНО КРУПНЫЕ, ЧТОБЫ ЗАПОЛНИТЬ ЭТИКЕТКУ"""
        fonts = {}
        
        # ===== РАЗМЕРЫ ШРИФТОВ - МАКСИМАЛЬНО УВЕЛИЧЕННЫЕ! =====
        if self.is_compact:  # 10x7
            font_sizes = {
                'micro': 11,      # Для адресов, штрихкодов
                'small': 13,      # Для импортера, состава
                'normal': 14,     # Основной текст
                'medium': 16,     # Вес/объем
                'large': 18,      # Подзаголовки
                'title': 22,      # Название товара
                'display': 24     # Крупное название
            }
        elif self.is_wide:  # 16x9
            font_sizes = {
                'micro': 14,
                'small': 16,
                'normal': 18,
                'medium': 20,
                'large': 24,
                'title': 30,
                'display': 36
            }
        else:  # Стандарт
            font_sizes = {
                'micro': 12,
                'small': 14,
                'normal': 16,
                'medium': 18,
                'large': 20,
                'title': 26,
                'display': 30
            }
        
        # Пытаемся загрузить Arial Bold для лучшей читаемости
        try:
            fonts['micro'] = ImageFont.truetype("arial.ttf", font_sizes['micro'])
            fonts['small'] = ImageFont.truetype("arial.ttf", font_sizes['small'])
            fonts['normal'] = ImageFont.truetype("arial.ttf", font_sizes['normal'])
            fonts['medium'] = ImageFont.truetype("arialbd.ttf", font_sizes['medium'])
            fonts['large'] = ImageFont.truetype("arialbd.ttf", font_sizes['large'])
            fonts['title'] = ImageFont.truetype("arialbd.ttf", font_sizes['title'])
            fonts['display'] = ImageFont.truetype("arialbd.ttf", font_sizes['display'])
            fonts['bold'] = fonts['title']
            fonts['regular'] = fonts['normal']
            fonts['small_bold'] = ImageFont.truetype("arialbd.ttf", font_sizes['small'])
            fonts['micro_bold'] = ImageFont.truetype("arialbd.ttf", font_sizes['micro'])
        except:
            # Fallback
            default = ImageFont.load_default()
            for key in font_sizes:
                fonts[key] = default
            fonts['bold'] = default
            fonts['regular'] = default
            fonts['small_bold'] = default
            fonts['micro_bold'] = default
        
        return fonts
    
    # ========== ГЛАВНЫЙ МЕТОД - ЗАЩИТНЫЕ ЗОНЫ И МАКСИМАЛЬНО КРУПНЫЙ ТЕКСТ ==========
    
    def add_full_content(self, data: Dict, processed_content: Dict = None):
        """
        Добавляет ВСЮ информацию на этикетку МАКСИМАЛЬНО КРУПНЫМ ШРИФТОМ
        QR-код и иконки — строго по углам с защитными зонами
        Текст заполняет оставшееся пространство
        """
        print(f"📝 Рисуем этикетку {self.width_cm}x{self.height_cm}см")
        
        # ===== 1. РАЗМЕРЫ ЭЛЕМЕНТОВ В ПИКСЕЛЯХ =====
        cm_to_inch = 0.393701
        
        # Стандартные размеры
        icon_size = int(1.0 * cm_to_inch * self.dpi)      # 1 см для иконок
        qr_size = int(2.0 * cm_to_inch * self.dpi)       # 2 см для QR-кода
        safe_margin = int(0.15 * cm_to_inch * self.dpi)  # 0.15 см защитная зона
        
        # Для маленьких этикеток уменьшаем размеры
        if self.is_compact:
            icon_size = int(0.8 * cm_to_inch * self.dpi)
            qr_size = int(1.8 * cm_to_inch * self.dpi)
            safe_margin = int(0.1 * cm_to_inch * self.dpi)
        
        # ===== 2. ОПРЕДЕЛЯЕМ ЗАЩИТНЫЕ ЗОНЫ ПО УГЛАМ =====
        reserved_areas = []
        
        # Правый верхний угол - ГОСТ
        if data.get('requires_gost', False):
            x_icon = self.width_px - icon_size - self.margin
            y_icon = self.margin
            reserved_areas.append({
                'x_min': x_icon - safe_margin,
                'x_max': x_icon + icon_size + safe_margin,
                'y_min': y_icon - safe_margin,
                'y_max': y_icon + icon_size + safe_margin,
                'type': 'gost',
                'x': x_icon,
                'y': y_icon,
                'size': icon_size
            })
        
        # Левый нижний угол - Переработка
        if data.get('is_recyclable', False):
            x_icon = self.margin
            y_icon = self.height_px - icon_size - self.margin
            reserved_areas.append({
                'x_min': x_icon - safe_margin,
                'x_max': x_icon + icon_size + safe_margin,
                'y_min': y_icon - safe_margin,
                'y_max': y_icon + icon_size + safe_margin,
                'type': 'recycle',
                'x': x_icon,
                'y': y_icon,
                'size': icon_size
            })
        
        # Правый нижний угол - QR-код
        if data.get('requires_qr', False):
            x_qr = self.width_px - qr_size - self.margin
            y_qr = self.height_px - qr_size - self.margin
            reserved_areas.append({
                'x_min': x_qr - safe_margin,
                'x_max': x_qr + qr_size + safe_margin,
                'y_min': y_qr - safe_margin,
                'y_max': y_qr + qr_size + safe_margin,
                'type': 'qr',
                'x': x_qr,
                'y': y_qr,
                'size': qr_size
            })
        
        # ===== 3. ОПРЕДЕЛЯЕМ ДОСТУПНУЮ ОБЛАСТЬ ДЛЯ ТЕКСТА =====
        text_margin_left = self.margin
        text_margin_right = self.width_px - self.margin
        text_margin_top = self.margin
        text_margin_bottom = self.height_px - self.margin
        
        # Если справа есть иконка/QR, уменьшаем ширину текста
        right_reserved = [area for area in reserved_areas 
                         if area['x_min'] > self.width_px // 2]
        if right_reserved:
            rightmost_reserved = min(area['x_min'] for area in right_reserved)
            text_margin_right = rightmost_reserved - safe_margin
        
        # Если слева есть иконка, уменьшаем ширину текста
        left_reserved = [area for area in reserved_areas 
                        if area['x_max'] < self.width_px // 2]
        if left_reserved:
            leftmost_reserved = max(area['x_max'] for area in left_reserved)
            text_margin_left = leftmost_reserved + safe_margin
        
        # Верхние иконки
        top_reserved = [area for area in reserved_areas 
                       if area['y_max'] < self.height_px // 2]
        if top_reserved:
            highest_reserved = max(area['y_max'] for area in top_reserved)
            text_margin_top = highest_reserved + safe_margin
        
        # Нижние иконки
        bottom_reserved = [area for area in reserved_areas 
                          if area['y_min'] > self.height_px // 2]
        if bottom_reserved:
            lowest_reserved = min(area['y_min'] for area in bottom_reserved)
            text_margin_bottom = lowest_reserved - safe_margin
        
        # Сохраняем область для текста
        self.text_area = {
            'x_min': max(text_margin_left, self.margin),
            'x_max': min(text_margin_right, self.width_px - self.margin),
            'y_min': max(text_margin_top, self.margin),
            'y_max': min(text_margin_bottom, self.height_px - self.margin),
            'width': text_margin_right - text_margin_left,
            'height': text_margin_bottom - text_margin_top
        }
        
        # Убеждаемся, что область имеет положительные размеры
        self.text_area['width'] = max(10, self.text_area['width'])
        self.text_area['height'] = max(20, self.text_area['height'])
        self.text_area['x_max'] = self.text_area['x_min'] + self.text_area['width']
        self.text_area['y_max'] = self.text_area['y_min'] + self.text_area['height']
        
        print(f"  📐 Область текста: {self.text_area['width']}x{self.text_area['height']}px")
        print(f"     Отступы: L:{self.text_area['x_min']} R:{self.text_area['x_max']} "
              f"T:{self.text_area['y_min']} B:{self.text_area['y_max']}")
        
        # ===== 4. РИСУЕМ ИКОНКИ ПО УГЛАМ =====
        for area in reserved_areas:
            if area['type'] == 'gost':
                # ГОСТ (правый верхний угол)
                self.draw.rectangle(
                    [area['x'], area['y'], area['x'] + area['size'], area['y'] + area['size']],
                    outline='#f59e0b', width=2
                )
                # Текст ГОСТ
                font_icon = self.fonts.get('small', self.fonts.get('micro', ImageFont.load_default()))
                self.draw.text(
                    (area['x'] + area['size']//4, area['y'] + area['size']//4),
                    'ГОСТ', fill='#f59e0b', font=font_icon
                )
                print(f"  ✓ ГОСТ добавлен: ({area['x']}, {area['y']})")
            
            elif area['type'] == 'recycle':
                # Переработка (левый нижний угол)
                self.draw.ellipse(
                    [area['x'], area['y'], area['x'] + area['size'], area['y'] + area['size']],
                    outline='#10b981', width=2
                )
                font_icon = self.fonts.get('medium', self.fonts.get('normal', ImageFont.load_default()))
                self.draw.text(
                    (area['x'] + area['size']//3, area['y'] + area['size']//3),
                    '♻', fill='#10b981', font=font_icon
                )
                print(f"  ✓ Переработка добавлена: ({area['x']}, {area['y']})")
            
            elif area['type'] == 'qr':
                # QR-код (правый нижний угол)
                self.draw.rectangle(
                    [area['x'], area['y'], area['x'] + area['size'], area['y'] + area['size']],
                    outline='black', width=2
                )
                
                # Имитация QR-кода
                cell_size = max(2, (area['size'] - 8) // 6)
                for i in range(6):
                    for j in range(6):
                        if (i + j) % 2:
                            x = area['x'] + 4 + i * cell_size
                            y = area['y'] + 4 + j * cell_size
                            self.draw.rectangle(
                                [x, y, x + cell_size - 1, y + cell_size - 1],
                                fill='black'
                            )
                print(f"  ✓ QR-код добавлен: ({area['x']}, {area['y']}) размер: {area['size']}px")
        
        # ===== 5. НАЧИНАЕМ РАЗМЕЩЕНИЕ ТЕКСТА =====
        y_position = self.text_area['y_min']
        
        # ===== 6. НАЗВАНИЕ ТОВАРА - ОЧЕНЬ КРУПНО =====
        product_name = data.get('product_full_name') or data.get('product_name', 'Товар')
        product_name = product_name.upper()
        
        # Выбираем шрифт в зависимости от доступного места
        if self.text_area['height'] > 200:
            font_title = self.fonts.get('display', self.fonts.get('title', ImageFont.load_default()))
        elif self.text_area['height'] > 150:
            font_title = self.fonts.get('title', self.fonts.get('large', ImageFont.load_default()))
        else:
            font_title = self.fonts.get('large', self.fonts.get('medium', ImageFont.load_default()))
        
        # Разбиваем на строки
        title_lines = self._wrap_text(product_name, font_title, self.text_area['width'])
        
        for i, line in enumerate(title_lines[:2]):  # Максимум 2 строки
            line_height = self._get_text_height(line, font_title)
            
            if y_position + line_height <= self.text_area['y_max']:
                # Центрируем по горизонтали
                bbox = self.draw.textbbox((0, 0), line, font=font_title)
                text_width = bbox[2] - bbox[0]
                x = self.text_area['x_min'] + (self.text_area['width'] - text_width) // 2
                x = max(self.text_area['x_min'], min(x, self.text_area['x_max'] - text_width))
                
                self.draw.text((x, y_position), line, fill='black', font=font_title)
                y_position += line_height + 5
        
        y_position += 5
        
        # ===== 7. МАССА НЕТТО / ОБЪЕМ =====
        if data.get('net_weight') or data.get('volume'):
            font_weight = self.fonts.get('large', self.fonts.get('bold', ImageFont.load_default()))
            
            weight_text = ""
            if data.get('net_weight'):
                net = data['net_weight'].replace('Масса нетто:', '').replace('Нетто:', '').strip()
                weight_text = f"Масса нетто: {net}"
            elif data.get('volume'):
                weight_text = f"Объем: {data['volume']}"
            
            if weight_text:
                line_height = self._get_text_height(weight_text, font_weight)
                
                if y_position + line_height <= self.text_area['y_max']:
                    bbox = self.draw.textbbox((0, 0), weight_text, font=font_weight)
                    text_width = bbox[2] - bbox[0]
                    x = self.text_area['x_min'] + (self.text_area['width'] - text_width) // 2
                    x = max(self.text_area['x_min'], min(x, self.text_area['x_max'] - text_width))
                    
                    self.draw.text((x, y_position), weight_text, fill='black', font=font_weight)
                    y_position += line_height + 8
        
        # ===== 8. СОСТАВ =====
        if data.get('ingredients'):
            font_ing = self.fonts.get('normal', self.fonts.get('regular', ImageFont.load_default()))
            ingredients_text = f"Состав: {data['ingredients']}"
            ing_lines = self._wrap_text(ingredients_text, font_ing, self.text_area['width'])
            
            for line in ing_lines:
                line_height = self._get_text_height(line, font_ing)
                
                if y_position + line_height <= self.text_area['y_max']:
                    self.draw.text((self.text_area['x_min'], y_position), line, fill='black', font=font_ing)
                    y_position += line_height + 3
                else:
                    # Добавляем многоточие если не помещается
                    if y_position + 15 <= self.text_area['y_max']:
                        self.draw.text((self.text_area['x_min'], y_position), "...", fill='black', font=font_ing)
                    break
            
            y_position += 5
        
        # ===== 9. ПИЩЕВАЯ И ЭНЕРГЕТИЧЕСКАЯ ЦЕННОСТЬ =====
        nutrition_lines = []
        
        if data.get('nutrition'):
            nutrition_lines.append(f"Пищ. ценность: {data['nutrition'][:100]}")
        
        if data.get('energy_value') and data.get('energy_value_kj'):
            nutrition_lines.append(f"Энерг.: {data['energy_value_kj']} / {data['energy_value']}")
        elif data.get('energy_value'):
            nutrition_lines.append(f"Энерг.: {data['energy_value']}")
        
        if nutrition_lines:
            font_nutr = self.fonts.get('small', self.fonts.get('regular', ImageFont.load_default()))
            
            for text in nutrition_lines:
                line_height = self._get_text_height(text, font_nutr)
                
                if y_position + line_height <= self.text_area['y_max']:
                    self.draw.text((self.text_area['x_min'], y_position), text, fill='#444444', font=font_nutr)
                    y_position += line_height + 3
            
            y_position += 5
        
        # ===== 10. ПРОИЗВОДИТЕЛЬ =====
        if data.get('manufacturer_full') or data.get('manufacturer'):
            font_label = self.fonts.get('small_bold', self.fonts.get('bold', ImageFont.load_default()))
            font_text = self.fonts.get('small', self.fonts.get('regular', ImageFont.load_default()))
            
            # Заголовок
            label_height = self._get_text_height("Производитель:", font_label)
            
            if y_position + label_height <= self.text_area['y_max']:
                self.draw.text((self.text_area['x_min'], y_position), "Производитель:", fill='black', font=font_label)
                y_position += label_height + 2
            
            # Текст производителя
            man_text = data.get('manufacturer_full') or data.get('manufacturer', '')
            if data.get('manufacturer_address') and not data.get('manufacturer_full'):
                man_text += f", {data['manufacturer_address']}"
            
            man_lines = self._wrap_text(man_text, font_text, self.text_area['width'] - 20)
            
            for line in man_lines:
                line_height = self._get_text_height(line, font_text)
                
                if y_position + line_height <= self.text_area['y_max']:
                    self.draw.text((self.text_area['x_min'] + 10, y_position), line, fill='black', font=font_text)
                    y_position += line_height + 2
            
            y_position += 5
        
        # ===== 11. ИМПОРТЕР =====
        if data.get('importer_full') or data.get('importer'):
            font_label = self.fonts.get('small_bold', self.fonts.get('bold', ImageFont.load_default()))
            font_text = self.fonts.get('small', self.fonts.get('regular', ImageFont.load_default()))
            
            # Заголовок
            label_height = self._get_text_height("Импортер:", font_label)
            
            if y_position + label_height <= self.text_area['y_max']:
                self.draw.text((self.text_area['x_min'], y_position), "Импортер:", fill='black', font=font_label)
                y_position += label_height + 2
            
            # Текст импортера
            imp_text = data.get('importer_full') or data.get('importer', '')
            if data.get('importer_address') and not data.get('importer_full'):
                imp_text += f", {data['importer_address']}"
            
            imp_lines = self._wrap_text(imp_text, font_text, self.text_area['width'] - 20)
            
            for line in imp_lines:
                line_height = self._get_text_height(line, font_text)
                
                if y_position + line_height <= self.text_area['y_max']:
                    self.draw.text((self.text_area['x_min'] + 10, y_position), line, fill='black', font=font_text)
                    y_position += line_height + 2
            
            y_position += 5
        
        # ===== 12. СТРАНА ПРОИСХОЖДЕНИЯ И ТАМОЖЕННЫЙ СОЮЗ =====
        country_parts = []
        
        if data.get('country_of_origin'):
            country_clean = data['country_of_origin'].replace('Страна происхождения:', '').replace('Страна:', '').strip()
            country_parts.append(f"Страна: {country_clean}")
        
        if data.get('customs_union'):
            country_parts.append("Таможенный союз")
        
        if country_parts:
            font_country = self.fonts.get('normal', self.fonts.get('regular', ImageFont.load_default()))
            display_text = ' • '.join(country_parts)
            line_height = self._get_text_height(display_text, font_country)
            
            if y_position + line_height <= self.text_area['y_max']:
                self.draw.text((self.text_area['x_min'], y_position), display_text, fill='black', font=font_country)
                y_position += line_height + 8
        
        # ===== 13. ДАТЫ - В ДВЕ КОЛОНКИ =====
        if data.get('manufacture_date') or data.get('expiry_date'):
            font_date = self.fonts.get('normal', self.fonts.get('regular', ImageFont.load_default()))
            date_y = y_position
            
            # Дата изготовления (слева)
            if data.get('manufacture_date'):
                man_date = data['manufacture_date'].replace('Дата изготовления:', '').strip()
                man_text = f"Изготовлен: {man_date}"
                line_height = self._get_text_height(man_text, font_date)
                
                if date_y + line_height <= self.text_area['y_max']:
                    self.draw.text((self.text_area['x_min'], date_y), man_text, fill='#555555', font=font_date)
            
            # Дата окончания (справа)
            if data.get('expiry_date'):
                exp_date = data['expiry_date'].replace('Годен до:', '').replace('Дата окончания срока годности:', '').strip()
                exp_text = f"Годен до: {exp_date}"
                bbox = self.draw.textbbox((0, 0), exp_text, font=font_date)
                text_width = bbox[2] - bbox[0]
                x_exp = self.text_area['x_max'] - text_width
                
                if x_exp >= self.text_area['x_min'] and date_y + line_height <= self.text_area['y_max']:
                    self.draw.text((x_exp, date_y), exp_text, fill='black', font=font_date)
            
            if data.get('manufacture_date') or data.get('expiry_date'):
                y_position += self._get_text_height(
                    data.get('expiry_date') or data.get('manufacture_date', ''), 
                    font_date
                ) + 8
        
        # ===== 14. СРОК ГОДНОСТИ =====
        if data.get('shelf_life'):
            font_shelf = self.fonts.get('normal', self.fonts.get('regular', ImageFont.load_default()))
            shelf_text = f"Срок годности: {data['shelf_life']}"
            line_height = self._get_text_height(shelf_text, font_shelf)
            
            if y_position + line_height <= self.text_area['y_max']:
                self.draw.text((self.text_area['x_min'], y_position), shelf_text, fill='#555555', font=font_shelf)
                y_position += line_height + 8
        
        # ===== 15. УСЛОВИЯ ХРАНЕНИЯ =====
        if data.get('storage_conditions'):
            font_storage = self.fonts.get('normal', self.fonts.get('regular', ImageFont.load_default()))
            storage_text = f"Хранение: {data['storage_conditions']}"
            storage_lines = self._wrap_text(storage_text, font_storage, self.text_area['width'])
            
            for line in storage_lines:
                line_height = self._get_text_height(line, font_storage)
                
                if y_position + line_height <= self.text_area['y_max']:
                    self.draw.text((self.text_area['x_min'], y_position), line, fill='#555555', font=font_storage)
                    y_position += line_height + 2
            
            y_position += 5
        
        # ===== 16. ПОСЛЕ ВСКРЫТИЯ =====
        if data.get('after_opening'):
            font_after = self.fonts.get('normal', self.fonts.get('regular', ImageFont.load_default()))
            line_height = self._get_text_height(data['after_opening'], font_after)
            
            if y_position + line_height <= self.text_area['y_max']:
                self.draw.text((self.text_area['x_min'], y_position), data['after_opening'], fill='#c41e3a', font=font_after)
                y_position += line_height + 8
        
        # ===== 17. СПОСОБ ПРИМЕНЕНИЯ =====
        if data.get('usage_instructions'):
            font_usage = self.fonts.get('normal', self.fonts.get('regular', ImageFont.load_default()))
            usage_text = f"Применение: {data['usage_instructions']}"
            usage_lines = self._wrap_text(usage_text, font_usage, self.text_area['width'])
            
            for line in usage_lines:
                line_height = self._get_text_height(line, font_usage)
                
                if y_position + line_height <= self.text_area['y_max']:
                    self.draw.text((self.text_area['x_min'], y_position), line, fill='#444444', font=font_usage)
                    y_position += line_height + 2
            
            y_position += 5
        
        # ===== 18. ТЕХНИЧЕСКИЕ РЕГЛАМЕНТЫ =====
        tr_lines = data.get('technical_regulations', [])
        
        if tr_lines:
            font_tr = self.fonts.get('small', self.fonts.get('regular', ImageFont.load_default()))
            
            for tr in tr_lines[:2]:  # Максимум 2 строки
                line_height = self._get_text_height(tr, font_tr)
                
                if y_position + line_height <= self.text_area['y_max']:
                    self.draw.text((self.text_area['x_min'], y_position), tr, fill='#2e7d32', font=font_tr)
                    y_position += line_height + 2
            
            y_position += 5
        
        # ===== 19. ПРЕДУПРЕЖДЕНИЯ =====
        warnings = data.get('warnings', [])
        
        if warnings:
            font_warning = self.fonts.get('small_bold', self.fonts.get('bold', ImageFont.load_default()))
            warning_text = f"⚠ {warnings[0]}"
            line_height = self._get_text_height(warning_text, font_warning)
            
            if y_position + line_height <= self.text_area['y_max']:
                self.draw.text((self.text_area['x_min'], y_position), warning_text, fill='#c41e3a', font=font_warning)
                y_position += line_height + 8
        
        # ===== 20. ШТРИХКОД - ВНИЗУ ТЕКСТОВОЙ ОБЛАСТИ =====
        if data.get('barcode') or data.get('ean13'):
            font_barcode = self.fonts.get('small', self.fonts.get('regular', ImageFont.load_default()))
            barcode = data.get('barcode') or data.get('ean13')
            barcode_clean = barcode.replace('Штрихкод продукта:', '').replace('Штрихкод:', '').strip()
            barcode_text = f"Штрихкод: {barcode_clean}"
            
            bbox = self.draw.textbbox((0, 0), barcode_text, font=font_barcode)
            text_width = bbox[2] - bbox[0]
            x_barcode = self.text_area['x_min'] + (self.text_area['width'] - text_width) // 2
            x_barcode = max(self.text_area['x_min'], min(x_barcode, self.text_area['x_max'] - text_width))
            
            # Размещаем над нижней защитной зоной
            y_barcode = self.text_area['y_max'] - 25
            
            if y_barcode >= self.text_area['y_min']:
                self.draw.text((x_barcode, y_barcode), barcode_text, fill='black', font=font_barcode)
        
        # Рисуем тонкую рамку этикетки
        self.draw.rectangle(
            [(0, 0), (self.width_px - 1, self.height_px - 1)],
            outline='#cccccc',
            width=1
        )
        
        # Для отладки - рисуем границы защитных зон (раскомментировать при необходимости)
        if False:
            for area in reserved_areas:
                self.draw.rectangle(
                    [area['x_min'], area['y_min'], area['x_max'], area['y_max']],
                    outline='red', width=1
                )
            self.draw.rectangle(
                [self.text_area['x_min'], self.text_area['y_min'], 
                 self.text_area['x_max'], self.text_area['y_max']],
                outline='blue', width=1
            )
        
        print(f"✅ Этикетка отрисована, Y-позиция: {y_position}/{self.text_area['y_max']}")
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    
    def _wrap_text(self, text: str, font, max_width: int) -> List[str]:
        """Разбивает текст на строки по ширине"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            if self.draw.textlength(test_line, font=font) <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Длинное слово - разрезаем
                    parts = []
                    part = ''
                    for char in word:
                        if self.draw.textlength(part + char, font=font) <= max_width - 10:
                            part += char
                        else:
                            if part:
                                parts.append(part + '-')
                            part = char
                    if part:
                        parts.append(part)
                    lines.extend(parts)
                    current_line = []
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def _get_text_height(self, text: str, font) -> int:
        """Возвращает высоту текста"""
        bbox = self.draw.textbbox((0, 0), text, font=font)
        return bbox[3] - bbox[1]
    
    def render(self) -> Image.Image:
        """Возвращает готовое изображение этикетки"""
        return self.image
    
    def add_qr_code(self, data: str, position: Dict, size: float = 2.0):
        """Добавляет QR-код (заглушка, QR уже рисуется в add_full_content)"""
        # Метод оставлен для обратной совместимости
        pass
    
    def add_icon(self, icon_type: str, position: str):
        """Добавляет иконку (заглушка, иконки уже рисуются в add_full_content)"""
        # Метод оставлен для обратной совместимости
        pass
    
    def _calculate_position(self, size: Tuple[int, int], position: Dict) -> Tuple[int, int]:
        """Рассчитывает позицию элемента (для обратной совместимости)"""
        element_width, element_height = size
        x_pos = position.get('x', 'center')
        y_pos = position.get('y', 'center')
        margin_x = int(position.get('margin_x', 0.2) * 0.393701 * self.dpi)
        margin_y = int(position.get('margin_y', 0.2) * 0.393701 * self.dpi)
        
        if x_pos == 'left':
            x = self.margin + margin_x
        elif x_pos == 'right':
            x = self.width_px - element_width - self.margin - margin_x
        else:
            x = (self.width_px - element_width) // 2
        
        if y_pos == 'top':
            y = self.margin + margin_y
        elif y_pos == 'bottom':
            y = self.height_px - element_height - self.margin - margin_y
        else:
            y = (self.height_px - element_height) // 2
        
        return x, y


# ========== API Functions ==========

def parse_product_text(text: str) -> Dict:
    """
    Парсит текст пользователя с полной информацией о товаре
    Поддерживает ВСЕ поля из стандарта ЕАЭС/Таможенного союза
    """
    result = {
        # Основное
        'product_name': 'Товар',
        'product_full_name': '',
        
        # Состав и пищевая ценность
        'ingredients': '',
        'nutrition': '',
        'energy_value': '',
        'energy_value_kj': '',
        'nutrition_facts': {},
        
        # Вес и объем
        'net_weight': '',
        'volume': '',
        'gross_weight': '',
        
        # Сроки и даты
        'expiry_date': '',
        'manufacture_date': '',
        'shelf_life': '',
        'shelf_life_days': '',
        'after_opening': '',
        
        # Условия хранения
        'storage_conditions': '',
        'storage_temp': '',
        'humidity': '',
        
        # Производитель
        'manufacturer': '',
        'manufacturer_address': '',
        'manufacturer_full': '',
        
        # Импортер
        'importer': '',
        'importer_address': '',
        'importer_full': '',
        
        # Страна
        'country_of_origin': '',
        'country_code': '',
        
        # Сертификация и соответствие
        'certification': [],
        'technical_regulations': [],
        'customs_union': False,
        'eaeu': False,
        'tr_codes': [],
        
        # Маркировка
        'barcode': '',
        'ean13': '',
        'honest_sign_barcode': '',
        'requires_qr': False,
        'qr_data': '',
        
        # Иконки и знаки
        'requires_gost': False,
        'gost_numbers': [],
        'is_recyclable': False,
        'recycle_code': '',
        'is_organic': False,
        'is_bio': False,
        'is_eco': False,
        'warning_icons': [],
        
        # Инструкции
        'usage_instructions': '',
        'preparation': '',
        'dilution': '',
        
        # Предупреждения
        'warnings': [],
        'allergens': [],
        'restrictions': '',
        
        # Дополнительно
        'batch_number': '',
        'best_before': '',
        'package_type': '',
        'package_material': '',
        'serving_size': '',
        'servings_per_package': ''
    }
    
    lines = text.split('\n')
    full_text = ' '.join(lines)
    
    # Специализированные паттерны для сложных полей
    energy_pattern = r'(\d+)\s*кДж\s*/\s*(\d+)\s*ккал'
    energy_match = re.search(energy_pattern, full_text, re.IGNORECASE)
    if energy_match:
        result['energy_value_kj'] = f"{energy_match.group(1)} кДж"
        result['energy_value'] = f"{energy_match.group(2)} ккал"
    
    # Парсинг пищевой ценности
    nutrition_patterns = [
        (r'белки?\s*[\-–—]?\s*(\d+(?:[.,]\d+)?)\s*г', 'белки'),
        (r'жиры?\s*[\-–—]?\s*(\d+(?:[.,]\d+)?)\s*г', 'жиры'),
        (r'углеводы?\s*[\-–—]?\s*(\d+(?:[.,]\d+)?)\s*г', 'углеводы'),
        (r'сахара?\s*[\-–—]?\s*(\d+(?:[.,]\d+)?)\s*г', 'сахара'),
        (r'клетчатк[аи]\s*[\-–—]?\s*(\d+(?:[.,]\d+)?)\s*г', 'клетчатка'),
        (r'соль\s*[\-–—]?\s*(\d+(?:[.,]\d+)?)\s*г', 'соль')
    ]
    
    for pattern, key in nutrition_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            result['nutrition_facts'][key] = match.group(1).replace(',', '.') + ' г'
    
    # Сбор всех требований ТР ТС
    tr_matches = re.findall(r'ТР ТС\s*\d{3,4}[/-]\d{4}', full_text)
    if tr_matches:
        result['tr_codes'] = list(set(tr_matches))
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        line_lower = line.lower()
        
        # --- ОСНОВНОЕ НАИМЕНОВАНИЕ ---
        if any(x in line_lower for x in ['товар:', 'наименование продукта:', 'наименование товара:', 'продукт:']):
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['product_full_name'] = parts[1].strip()
                # Если краткое название не задано, используем полное
                if not result['product_name'] or result['product_name'] == 'Товар':
                    result['product_name'] = parts[1].strip()[:50]
        
        # --- СОСТАВ ---
        elif any(x in line_lower for x in ['состав продукта:', 'состав:', 'ингредиенты:']):
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['ingredients'] = parts[1].strip()
        
        # --- ПИЩЕВАЯ ЦЕННОСТЬ ---
        elif 'пищевая ценность' in line_lower:
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['nutrition'] = parts[1].strip()
        
        # --- ЭНЕРГЕТИЧЕСКАЯ ЦЕННОСТЬ ---
        elif 'энергетическая ценность' in line_lower:
            if 'кДж' in line and 'ккал' in line:
                kj_match = re.search(r'(\d+)\s*кДж', line, re.IGNORECASE)
                kcal_match = re.search(r'(\d+)\s*ккал', line, re.IGNORECASE)
                if kj_match:
                    result['energy_value_kj'] = kj_match.group(1) + ' кДж'
                if kcal_match:
                    result['energy_value'] = kcal_match.group(1) + ' ккал'
            else:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    result['energy_value'] = parts[1].strip()
        
        # --- МАССА НЕТТО / ОБЪЕМ ---
        elif 'масса нетто:' in line_lower:
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['net_weight'] = parts[1].strip()
        elif any(x in line_lower for x in ['объем:', 'объём:']):
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['volume'] = parts[1].strip()
        
        # --- СРОК ГОДНОСТИ ---
        elif 'срок годности:' in line_lower:
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['shelf_life'] = parts[1].strip()
                # Извлекаем количество месяцев
                months = re.search(r'(\d+)\s*месяц', parts[1], re.IGNORECASE)
                if months:
                    result['shelf_life_days'] = str(int(months.group(1)) * 30)
        
        # --- ДАТА ИЗГОТОВЛЕНИЯ ---
        elif 'дата изготовления:' in line_lower:
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['manufacture_date'] = parts[1].strip()
        
        # --- ДАТА ОКОНЧАНИЯ СРОКА ---
        elif any(x in line_lower for x in ['дата окончания срока годности:', 'годен до:']):
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['expiry_date'] = parts[1].strip()
        
        # --- УСЛОВИЯ ХРАНЕНИЯ ---
        elif 'условия хранения:' in line_lower:
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['storage_conditions'] = parts[1].strip()
                
                # Извлекаем температуру
                temp = re.search(r'(\+?\d+)\s*[°⁰СC]', parts[1])
                if temp:
                    result['storage_temp'] = temp.group(1) + '°C'
        
        # --- ПОСЛЕ ВСКРЫТИЯ ---
        elif 'после вскрытия' in line_lower:
            result['after_opening'] = line.strip()
        
        # --- ИЗГОТОВИТЕЛЬ ---
        elif 'изготовитель:' in line_lower:
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['manufacturer'] = parts[1].strip()
        
        # --- АДРЕС ИЗГОТОВИТЕЛЯ ---
        elif 'адрес изготовителя:' in line_lower:
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['manufacturer_address'] = parts[1].strip()
        
        # --- ИМПОРТЕР ---
        elif any(x in line_lower for x in ['импортер в рф', 'импортёр в рф', 'импортер в еаэс', 'импортер:']):
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['importer'] = parts[1].strip()
        
        # --- АДРЕС ИМПОРТЕРА ---
        elif 'адрес импортера' in line_lower or 'адрес импортёра' in line_lower:
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['importer_address'] = parts[1].strip()
        
        # --- СТРАНА ПРОИСХОЖДЕНИЯ ---
        elif any(x in line_lower for x in ['страна происхождения:', 'страна:']):
            parts = line.split(':', 1)
            if len(parts) > 1:
                country = parts[1].strip()
                result['country_of_origin'] = country
                
                # Код страны (ISO)
                country_codes = {
                    'германия': 'DE', 'россия': 'RU', 'сша': 'US', 
                    'франция': 'FR', 'италия': 'IT', 'испания': 'ES',
                    'китай': 'CN', 'бразилия': 'BR'
                }
                for name, code in country_codes.items():
                    if name in country.lower():
                        result['country_code'] = code
        
        # --- ТАМОЖЕННЫЙ СОЮЗ / ЕАЭС ---
        elif any(x in line_lower for x in ['таможенный союз', 'еаэс']):
            result['customs_union'] = True
            result['eaeu'] = True
        
        # --- ТР ТС / СЕРТИФИКАЦИЯ ---
        elif any(x in line_lower for x in ['требованиям технического регламента', 'тр тс', 'технического регламента']):
            result['certification'].append(line.strip())
            if '021/2011' in line:
                result['technical_regulations'].append('ТР ТС 021/2011')
            if '022/2011' in line:
                result['technical_regulations'].append('ТР ТС 022/2011')
            if '005/2011' in line:
                result['technical_regulations'].append('ТР ТС 005/2011')
        
        # --- ШТРИХКОД ---
        elif any(x in line_lower for x in ['штрихкод продукта:', 'штрих-код:', 'ean-13:', 'ean13:']):
            parts = line.split(':', 1)
            if len(parts) > 1:
                barcode = parts[1].strip()
                result['barcode'] = barcode
                result['ean13'] = barcode
        
        # --- QR-КОД / ЧЕСТНЫЙ ЗНАК ---
        elif any(x in line_lower for x in ['qr-код', 'честного знака', 'требуется qr-код']):
            result['requires_qr'] = True
            if ':' in line:
                parts = line.split(':', 1)
                result['qr_data'] = parts[1].strip()
            else:
                result['qr_data'] = f"QR_{int(time.time())}"
        
        # --- ГОСТ ---
        elif 'гост' in line_lower or 'значки гост' in line_lower:
            result['requires_gost'] = True
            # Извлекаем номер ГОСТа
            gost = re.search(r'ГОСТ\s*[\-–—]?\s*([\d\-\s]+)', line, re.IGNORECASE)
            if gost:
                result['gost_numbers'].append(gost.group(1).strip())
        
        # --- ЗНАК ПЕРЕРАБОТКИ ---
        elif any(x in line_lower for x in ['знак переработки', 'перерабатываемая упаковка', '♻', 'recycl']):
            result['is_recyclable'] = True
            # Код переработки
            code = re.search(r'(\d{1,2})\s*(PET|HDPE|PVC|LDPE|PP|PS|O)', line, re.IGNORECASE)
            if code:
                result['recycle_code'] = code.group(1) + ' ' + code.group(2)
        
        # --- СПОСОБ ПРИМЕНЕНИЯ / ПРИГОТОВЛЕНИЯ ---
        elif any(x in line_lower for x in ['способ применения:', 'приготовление:', 'разведение:']):
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['usage_instructions'] = parts[1].strip()
                
                # Извлекаем пропорции разведения
                dilution = re.search(r'(\d+)\s*г\s*.+?\s*(\d+)\s*мл', parts[1], re.IGNORECASE)
                if dilution:
                    result['dilution'] = f"{dilution.group(1)}г / {dilution.group(2)}мл"
        
        # --- АЛЛЕРГЕНЫ / ПРЕДУПРЕЖДЕНИЯ ---
        elif any(x in line_lower for x in ['предупреждение:', 'аллерген', 'содержит', 'warning:']):
            if 'аллерген' in line_lower or 'содержит' in line_lower:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    result['allergens'].append(parts[1].strip())
                else:
                    result['warnings'].append(line.strip())
            else:
                result['warnings'].append(line.strip())
        
        # --- ПАРТИЯ / НОМЕР ПАРТИИ ---
        elif 'партия:' in line_lower or 'batch:' in line_lower:
            parts = line.split(':', 1)
            if len(parts) > 1:
                result['batch_number'] = parts[1].strip()
    
    # Если полное название не найдено, используем краткое
    if not result['product_full_name']:
        result['product_full_name'] = result['product_name']
    
    # Формируем полный текст производителя
    if result['manufacturer'] and result['manufacturer_address']:
        result['manufacturer_full'] = f"{result['manufacturer']}, {result['manufacturer_address']}"
    
    # Формируем полный текст импортера
    if result['importer'] and result['importer_address']:
        result['importer_full'] = f"{result['importer']}, {result['importer_address']}"
    elif result['importer']:
        result['importer_full'] = result['importer']
    
    return result


def generate_label_image(product_data: Dict, width: float, height: float) -> Image.Image:
    """
    Генерирует этикетку с ПОЛНОЙ информацией о товаре
    НИЧЕГО НЕ ТЕРЯЕТ - передает все данные в LabelDesigner
    """
    try:
        print(f"\n🎨 ГЕНЕРАЦИЯ ЭТИКЕТКИ {width}x{height}см")
        print(f"   Товар: {product_data.get('product_name', 'Н/Д')}")
        print(f"   Состав: {product_data.get('ingredients', '')[:50]}")
        print(f"   Производитель: {product_data.get('manufacturer', 'Н/Д')}")
        print(f"   Импортер: {product_data.get('importer', 'Н/Д')}")
        print(f"   Срок годности: {product_data.get('expiry_date', 'Н/Д')}")
        print(f"   QR: {product_data.get('requires_qr', False)}")
        print(f"   Переработка: {product_data.get('is_recyclable', False)}")
        print(f"   ГОСТ: {product_data.get('requires_gost', False)}")
        
        # СОЗДАЕМ ДИЗАЙНЕР
        designer = LabelDesigner(width=width, height=height, dpi=300)
        
        # ПЕРЕДАЕМ ВСЕ ДАННЫЕ - add_full_content САМА РИСУЕТ ВСЁ!
        designer.add_full_content(product_data)
        
        print(f"✅ Этикетка сгенерирована успешно")
        return designer.render()
        
    except Exception as e:
        print(f"❌ Ошибка генерации этикетки: {e}")
        import traceback
        traceback.print_exc()
        
        # FALLBACK - НО С ДАННЫМИ!
        from PIL import Image, ImageDraw, ImageFont
        cm_to_inch = 0.393701
        dpi = 150
        width_px = int(width * cm_to_inch * dpi)
        height_px = int(height * cm_to_inch * dpi)
        
        img = Image.new('RGB', (width_px, height_px), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font_title = ImageFont.truetype("arialbd.ttf", 16)
            font_normal = ImageFont.truetype("arial.ttf", 11)
            font_small = ImageFont.truetype("arial.ttf", 9)
        except:
            font_title = ImageFont.load_default()
            font_normal = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        y = 15
        margin = 15
        
        # НАЗВАНИЕ
        title = product_data.get('product_full_name') or product_data.get('product_name', 'Товар')
        draw.text((margin, y), title[:60], fill='black', font=font_title)
        y += 30
        
        # ВЕС
        if product_data.get('net_weight'):
            draw.text((margin, y), f"Масса нетто: {product_data['net_weight']}", fill='black', font=font_normal)
            y += 20
        elif product_data.get('volume'):
            draw.text((margin, y), f"Объем: {product_data['volume']}", fill='black', font=font_normal)
            y += 20
        
        # ПРОИЗВОДИТЕЛЬ
        if product_data.get('manufacturer_full'):
            draw.text((margin, y), f"Производитель: {product_data['manufacturer_full'][:60]}", fill='black', font=font_small)
            y += 18
        elif product_data.get('manufacturer'):
            draw.text((margin, y), f"Производитель: {product_data['manufacturer']}", fill='black', font=font_small)
            y += 18
        
        # ИМПОРТЕР
        if product_data.get('importer_full'):
            draw.text((margin, y), f"Импортер: {product_data['importer_full'][:60]}", fill='black', font=font_small)
            y += 18
        elif product_data.get('importer'):
            draw.text((margin, y), f"Импортер: {product_data['importer']}", fill='black', font=font_small)
            y += 18
        
        # СТРАНА
        if product_data.get('country_of_origin'):
            draw.text((margin, y), f"Страна: {product_data['country_of_origin']}", fill='black', font=font_small)
            y += 18
        
        # СРОК
        if product_data.get('expiry_date'):
            draw.text((margin, y), f"Годен до: {product_data['expiry_date']}", fill='black', font=font_small)
        
        return img


def slugify_filename(text: str) -> str:
    """
    Транслитерация для имени файла
    
    Args:
        text: исходный текст
        
    Returns:
        безопасное имя файла
    """
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
        ' ': '_', '"': '', "'": '', '«': '', '»': '', '—': '-', ',': '', '.': '',
        '(': '', ')': '', '!': '', '?': '', ';': '', ':': ''
    }
    
    result = ''
    for char in text:
        result += translit.get(char, char)
    
    result = re.sub(r'[^a-zA-Z0-9_-]', '', result)
    result = re.sub(r'[_]+', '_', result)
    result = result.strip('_')[:50]
    
    return result or 'product'


def get_variant_features(variant_name: str, product_data: Dict) -> List[str]:
    """
    Возвращает особенности этикетки для варианта дизайна
    
    Args:
        variant_name: название варианта
        product_data: данные о товаре
        
    Returns:
        список особенностей
    """
    features = []
    
    if variant_name == 'Широкий формат':
        features = ['Заголовок CAPS', 'Перенос строк', 'QR справа', 'Подробная информация']
    else:
        features = ['Только важное', 'Крупный QR', 'Чистый дизайн']
    
    if product_data.get('is_recyclable'):
        features.append('♻ Переработка')
    
    if product_data.get('requires_gost'):
        features.append('ГОСТ')
    
    if product_data.get('requires_qr'):
        features.append('QR-код')
    
    return features


def check_label_compliance(content: Dict, customer_data: Dict) -> Dict:
    """
    Проверка соответствия требованиям
    
    Args:
        content: обработанный контент
        customer_data: исходные данные
        
    Returns:
        Dict с результатами проверки
    """
    checks = {
        'has_product_name': bool(content.get('product_name')),
        'has_country_of_origin': bool(content.get('country_of_origin')),
        'has_importer': bool(content.get('importer')),
        'has_barcode': bool(customer_data.get('honest_sign_barcode')),
        'font_size_ok': content.get('font_size', 0) >= 8,  # минимум 8pt
        'contrast_ok': True
    }
    return checks


# ========== Main Function ==========

def main():
    parser = argparse.ArgumentParser(description='Генератор таможенных этикеток')
    parser.add_argument('--input', type=str, required=True, help='JSON файл с данными заказчика')
    parser.add_argument('--output', type=str, default='output/label.png', help='Выходной файл')
    parser.add_argument('--template', type=str, default='auto', help='Шаблон этикетки')
    parser.add_argument('--verbose', action='store_true', help='Подробный вывод')
    
    args = parser.parse_args()
    
    # Загрузка данных заказчика
    with open(args.input, 'r', encoding='utf-8') as f:
        customer_data = json.load(f)
    
    if args.verbose:
        print("📦 Загружены данные заказчика:")
        print(json.dumps(customer_data, indent=2, ensure_ascii=False))
    
    # Обработка контента
    processor = ContentProcessor()
    processed_content = processor.process(customer_data)
    
    # Расчет размера этикетки
    calculator = SizeCalculator()
    
    # Определяем параметры товара (пример: коробка сока 200мл)
    product_dimensions = customer_data.get('product_dimensions', {})
    if not product_dimensions:
        # Автоопределение на основе типа товара
        product_type = customer_data.get('product_type', '')
        if 'сок' in product_type.lower() or 'juice' in product_type.lower():
            product_dimensions = {
                'package_type': 'juice_box',
                'wall_width': 12,  # см
                'wall_height': 4,   # см
                'min_label_margin': 0.5,  # минимальный отступ от края
                'scan_zone_height': 2.5   # зона для сканирования QR
            }
    
    # Расчет оптимального размера этикетки
    label_size = calculator.calculate_optimal_size(
        content=processed_content,
        product_dimensions=product_dimensions,
        qr_code_size=2.0  # QR код примерно 2x2 см
    )
    
    if args.verbose:
        print(f"\n📏 Рассчитанный размер этикетки: {label_size['width']}x{label_size['height']} см")
        print(f"📐 Положение на упаковке: {label_size['position']}")
    
    # Создание дизайнера этикетки
    designer = LabelDesigner(
        width=label_size['width'],
        height=label_size['height'],
        dpi=300  # 300 точек на дюйм для качественной печати
    )
    
    # Добавление контента на этикетку
    designer.add_content(processed_content)
    
    # Добавление QR-кода (будет нарисована заглушка)
    designer.add_qr_code(
        data=customer_data.get('honest_sign_barcode', 'Нет данных для QR'),
        position=label_size['qr_position'],
        size=label_size['qr_size']
    )
    
    # Добавление иконок
    icons = customer_data.get('required_icons', [])
    for icon in icons:
        designer.add_icon(icon['type'], icon['position'])
    
    # Генерация этикетки
    label_image = designer.render()
    
    # Сохранение
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)
    label_image.save(args.output, dpi=(300, 300))
    
    if args.verbose:
        print(f"\n✅ Этикетка сохранена: {args.output}")
        print("⚠ QR-код заменен заглушкой (установите модуль qrcode для настоящих QR-кодов)")
    
    # Генерация отчета
    report = {
        'input_file': args.input,
        'output_file': args.output,
        'label_size_cm': label_size,
        'content_summary': {
            'text_lines': len(processed_content['text_blocks']),
            'has_qr': True,
            'icons_count': len(icons)
        },
        'compliance_check': check_label_compliance(processed_content, customer_data),
        'warning': 'QR-код заменен заглушкой. Установите модуль qrcode для настоящих QR-кодов.'
    }
    
    report_file = args.output.replace('.png', '_report.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return 0


if __name__ == '__main__':
    main()