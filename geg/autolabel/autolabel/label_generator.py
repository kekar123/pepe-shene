"""
AutoLabel Designer - автоматический дизайнер таможенных этикеток
ИСПРАВЛЕННАЯ ВЕРСИЯ - текст отображается правильно
"""

import re
import json
import argparse
import math
import os
import time 
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ========== ИСПРАВЛЕННЫЙ LabelDesigner ==========
class LabelDesigner:
    """Дизайнер этикеток - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    def __init__(self, width: float, height: float, dpi: int = 300):
        """
        Args:
            width: ширина этикетки в СМ
            height: высота этикетки в СМ
            dpi: разрешение для печати
        """
        self.width_cm = width
        self.height_cm = height
        self.dpi = dpi
        
        # Конвертация см в пиксели (1 дюйм = 2.54 см)
        cm_to_inch = 0.393701  # 1/2.54
        self.width_px = int(width * cm_to_inch * dpi)
        self.height_px = int(height * cm_to_inch * dpi)
        
        print(f"📐 Размеры: {width:.1f}x{height:.1f} см → {self.width_px}x{self.height_px} px @{dpi}dpi")
        
        # Создание холста
        self.image = Image.new('RGB', (self.width_px, self.height_px), 'white')
        self.draw = ImageDraw.Draw(self.image)
        
        # Отступы от краев (в пикселях)
        self.margin = int(min(self.width_px, self.height_px) * 0.05)  # 5% от меньшей стороны
        
        # Базовая область для текста
        self.text_area = {
            'x': self.margin,
            'y': self.margin,
            'width': self.width_px - 2 * self.margin,
            'height': self.height_px - 2 * self.margin
        }
        
        # Загружаем шрифты
        self.fonts = self._load_fonts()
        
        print(f"  📐 Рабочая область: {self.text_area['width']}x{self.text_area['height']}px")
    
    def _load_fonts(self) -> Dict:
        """Загружает шрифты с правильными размерами"""
        fonts = {}
        
        # РАЗМЕРЫ ШРИФТОВ (в пикселях)
        # Для больших этикеток делаем шрифты поменьше, чтобы влезло больше текста
        base_size = int(self.height_px * 0.03)  # 3% от высоты
        
        font_sizes = {
            'small': max(12, int(base_size * 0.7)),
            'normal': max(14, int(base_size * 0.9)),
            'medium': max(16, int(base_size * 1.1)),
            'large': max(18, int(base_size * 1.3)),
            'title': max(20, int(base_size * 1.5))
        }
        
        print(f"  🔤 Размеры шрифтов: title={font_sizes['title']}pt, normal={font_sizes['normal']}pt")
        
        # Пытаемся загрузить Arial
        try:
            fonts['small'] = ImageFont.truetype("arial.ttf", font_sizes['small'])
            fonts['normal'] = ImageFont.truetype("arial.ttf", font_sizes['normal'])
            fonts['medium'] = ImageFont.truetype("arialbd.ttf", font_sizes['medium'])
            fonts['large'] = ImageFont.truetype("arialbd.ttf", font_sizes['large'])
            fonts['title'] = ImageFont.truetype("arialbd.ttf", font_sizes['title'])
        except:
            # Fallback
            default = ImageFont.load_default()
            for key in font_sizes:
                fonts[key] = default
            print("  ⚠️ Используется шрифт по умолчанию")
        
        return fonts
    
    def add_full_content(self, data: Dict):
        """
        Рисует всю информацию на этикетке
        """
        print(f"📝 Рисуем этикетку {self.width_cm:.1f}x{self.height_cm:.1f}см")
        
        # Текущая позиция Y для текста
        y = self.text_area['y']
        
        # 1. НАЗВАНИЕ ТОВАРА (всегда по центру, крупно)
        product_name = data.get('product_full_name') or data.get('product_name', 'Товар')
        if product_name:
            font = self.fonts['title']
            lines = self._wrap_text(product_name.upper(), font, self.text_area['width'])
            for line in lines[:2]:  # Максимум 2 строки
                text_width = self._get_text_width(line, font)
                x = self.text_area['x'] + (self.text_area['width'] - text_width) // 2
                self.draw.text((x, y), line, fill='black', font=font)
                y += self._get_text_height(line, font) + 10
            y += 10  # Дополнительный отступ
        
        # 2. СОСТАВ
        if data.get('ingredients'):
            font = self.fonts['normal']
            text = f"Состав: {data['ingredients']}"
            lines = self._wrap_text(text, font, self.text_area['width'])
            for line in lines[:3]:  # Максимум 3 строки
                self.draw.text((self.text_area['x'], y), line, fill='black', font=font)
                y += self._get_text_height(line, font) + 5
            y += 5
        
        # 3. ПИЩЕВАЯ ЦЕННОСТЬ
        if data.get('nutrition'):
            font = self.fonts['small']
            text = data['nutrition']
            self.draw.text((self.text_area['x'], y), text, fill='black', font=font)
            y += self._get_text_height(text, font) + 5
        
        # 4. ЭНЕРГЕТИЧЕСКАЯ ЦЕННОСТЬ
        if data.get('energy_value'):
            font = self.fonts['small']
            text = data['energy_value']
            self.draw.text((self.text_area['x'], y), text, fill='black', font=font)
            y += self._get_text_height(text, font) + 5
        
        # 5. МАССА НЕТТО
        if data.get('net_weight'):
            font = self.fonts['medium']
            text = f"Масса нетто: {data['net_weight']}"
            lines = self._wrap_text(text, font, self.text_area['width'])
            for line in lines:
                self.draw.text((self.text_area['x'], y), line, fill='black', font=font)
                y += self._get_text_height(line, font) + 8
            y += 5
        
        # 6. ПРОИЗВОДИТЕЛЬ
        if data.get('manufacturer'):
            font = self.fonts['normal']
            text = f"Производитель: {data['manufacturer']}"
            lines = self._wrap_text(text, font, self.text_area['width'])
            for line in lines[:2]:
                self.draw.text((self.text_area['x'], y), line, fill='black', font=font)
                y += self._get_text_height(line, font) + 5
            y += 5
        
        # 7. ИМПОРТЕР
        if data.get('importer'):
            font = self.fonts['normal']
            text = f"Импортер: {data['importer']}"
            lines = self._wrap_text(text, font, self.text_area['width'])
            for line in lines[:2]:
                self.draw.text((self.text_area['x'], y), line, fill='black', font=font)
                y += self._get_text_height(line, font) + 5
            y += 5
        
        # 8. СТРАНА
        if data.get('country_of_origin'):
            font = self.fonts['normal']
            text = f"Страна: {data['country_of_origin']}"
            self.draw.text((self.text_area['x'], y), text, fill='black', font=font)
            y += self._get_text_height(text, font) + 5
        
        # 9. СРОК ГОДНОСТИ
        shelf_parts = []
        if data.get('shelf_life'):
            shelf_parts.append(f"годен: {data['shelf_life']}")
        if data.get('expiry_date'):
            shelf_parts.append(f"до: {data['expiry_date']}")
        
        if shelf_parts:
            font = self.fonts['small']
            text = ' • '.join(shelf_parts)
            self.draw.text((self.text_area['x'], y), text, fill='black', font=font)
            y += self._get_text_height(text, font) + 5
        
        # 10. ШТРИХКОД
        if data.get('barcode'):
            font = self.fonts['medium']
            text = f"ШК: {data['barcode']}"
            # Центрируем штрихкод
            text_width = self._get_text_width(text, font)
            x = self.text_area['x'] + (self.text_area['width'] - text_width) // 2
            self.draw.text((x, y), text, fill='black', font=font)
            y += self._get_text_height(text, font) + 5
        
        # 11. УСЛОВИЯ ХРАНЕНИЯ (если есть место)
        if data.get('storage_conditions') and y < self.text_area['y'] + self.text_area['height'] * 0.8:
            font = self.fonts['small']
            text = f"Хранение: {data['storage_conditions'][:50]}"
            lines = self._wrap_text(text, font, self.text_area['width'])
            for line in lines[:2]:
                self.draw.text((self.text_area['x'], y), line, fill='black', font=font)
                y += self._get_text_height(line, font) + 3
        
        # РИСУЕМ РАМКУ ВОКРУГ ЭТИКЕТКИ
        self.draw.rectangle(
            [(0, 0), (self.width_px - 1, self.height_px - 1)],
            outline='#cccccc',
            width=2
        )
        
        print(f"✅ Этикетка отрисована")
    
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
                    # Длинное слово - разрезаем посимвольно
                    chars = []
                    for char in word:
                        test_word = ''.join(chars + [char])
                        if self.draw.textlength(test_word, font=font) <= max_width - 10:
                            chars.append(char)
                        else:
                            if chars:
                                lines.append(''.join(chars) + '-')
                            chars = [char]
                    if chars:
                        lines.append(''.join(chars))
                    current_line = []
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def _get_text_height(self, text: str, font) -> int:
        """Возвращает высоту текста"""
        bbox = self.draw.textbbox((0, 0), text, font=font)
        return bbox[3] - bbox[1] + 5  # Добавляем небольшой отступ
    
    def _get_text_width(self, text: str, font) -> int:
        """Возвращает ширину текста"""
        bbox = self.draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]
    
    def render(self) -> Image.Image:
        """Возвращает готовое изображение этикетки"""
        return self.image


# ========== ПАРСЕР ТЕКСТА ==========

def parse_product_text(text: str) -> Dict:
    """
    Парсит текст пользователя с полной информацией о товаре
    """
    result = {
        'product_name': 'Товар',
        'product_full_name': '',
        'ingredients': '',
        'nutrition': '',
        'energy_value': '',
        'net_weight': '',
        'manufacturer': '',
        'importer': '',
        'country_of_origin': '',
        'barcode': '',
        'shelf_life': '',
        'expiry_date': '',
        'storage_conditions': '',
        'requires_qr': False,
        'requires_gost': False,
        'is_recyclable': False,
        'customs_union': False
    }
    
    if not text:
        return result
    
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        line_lower = line.lower()
        
        # Наименование продукта
        if 'товар:' in line_lower:
            result['product_full_name'] = line.split(':', 1)[1].strip()
            result['product_name'] = result['product_full_name']
        
        # Состав
        elif 'состав:' in line_lower:
            result['ingredients'] = line.split(':', 1)[1].strip()
        
        # Пищевая ценность
        elif 'пищевая ценность:' in line_lower:
            result['nutrition'] = line.split(':', 1)[1].strip()
        
        # Энергетическая ценность
        elif 'энергетическая ценность:' in line_lower:
            result['energy_value'] = line.split(':', 1)[1].strip()
        
        # Масса нетто
        elif 'масса нетто:' in line_lower:
            result['net_weight'] = line.split(':', 1)[1].strip()
        
        # Производитель
        elif 'изготовитель:' in line_lower:
            result['manufacturer'] = line.split(':', 1)[1].strip()
        
        # Импортер
        elif 'импортер:' in line_lower:
            result['importer'] = line.split(':', 1)[1].strip()
        
        # Страна
        elif 'страна:' in line_lower:
            result['country_of_origin'] = line.split(':', 1)[1].strip()
        
        # Штрихкод
        elif 'штрихкод:' in line_lower:
            result['barcode'] = line.split(':', 1)[1].strip()
        
        # Срок годности
        elif 'срок годности:' in line_lower:
            result['shelf_life'] = line.split(':', 1)[1].strip()
        
        # QR-код
        elif 'qr-код' in line_lower:
            result['requires_qr'] = True
        
        # Знак переработки
        elif 'знак переработки' in line_lower:
            result['is_recyclable'] = True
        
        # ГОСТ
        elif 'гост' in line_lower:
            result['requires_gost'] = True
    
    return result


def generate_label_image(product_data: Dict, width: float, height: float) -> Image.Image:
    """
    Генерирует этикетку
    """
    try:
        print(f"\n🎨 ГЕНЕРАЦИЯ ЭТИКЕТКИ {width}x{height}см")
        print(f"   Товар: {product_data.get('product_name', 'Н/Д')}")
        print(f"   Состав: {product_data.get('ingredients', 'Н/Д')[:50]}")
        print(f"   Страна: {product_data.get('country_of_origin', 'Н/Д')}")
        print(f"   Вес: {product_data.get('net_weight', 'Н/Д')}")
        print(f"   Производитель: {product_data.get('manufacturer', 'Н/Д')}")
        print(f"   Импортер: {product_data.get('importer', 'Н/Д')}")
        
        designer = LabelDesigner(width=width, height=height, dpi=300)
        designer.add_full_content(product_data)
        
        return designer.render()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        
        # Создаем простую этикетку с ошибкой
        from PIL import Image, ImageDraw, ImageFont
        cm_to_inch = 0.393701
        dpi = 150
        width_px = int(width * cm_to_inch * dpi)
        height_px = int(height * cm_to_inch * dpi)
        
        img = Image.new('RGB', (width_px, height_px), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        y = 20
        for key, value in product_data.items():
            if value:
                draw.text((20, y), f"{key}: {value}", fill='black', font=font)
                y += 30
        
        return img


def slugify_filename(text: str) -> str:
    """Транслитерация для имени файла"""
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        ' ': '_', '"': '', "'": '', '«': '', '»': '', '—': '-', ',': '', '.': ''
    }
    
    result = ''
    for char in text.lower():
        result += translit.get(char, char)
    
    result = re.sub(r'[^a-zA-Z0-9_-]', '', result)
    result = re.sub(r'[_]+', '_', result)
    return result[:50] or 'product'


if __name__ == '__main__':
    print("LabelFlow AI Generator - ИСПРАВЛЕННАЯ ВЕРСИЯ")