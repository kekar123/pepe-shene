"""
etoile_layout.py - Стиль расположения как в шаблоне L'Etoile
С метриками Arial и адаптивным соотношением текст/графика 80-90% / 10-20%
Версия 2.1
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import List, Dict, Tuple, Optional
import math
import os
import base64
from xml.sax.saxutils import escape


# Предопределенные размеры этикеток (мм -> px при 1 мм = 8 px)
PREDEFINED_SIZES = {
    "46x46": {"width_mm": 46, "height_mm": 46, "width_px": 368, "height_px": 368, "name": "46x46 мм"},
    "48x30": {"width_mm": 48, "height_mm": 30, "width_px": 384, "height_px": 240, "name": "48x30 мм"},
    "40x20": {"width_mm": 40, "height_mm": 20, "width_px": 320, "height_px": 160, "name": "40x20 мм"},
    "30x15": {"width_mm": 30, "height_mm": 15, "width_px": 240, "height_px": 120, "name": "30x15 мм"},
    "43x63": {"width_mm": 43, "height_mm": 63, "width_px": 344, "height_px": 504, "name": "43x63 мм"},
    "22x22": {"width_mm": 22, "height_mm": 22, "width_px": 176, "height_px": 176, "name": "22x22 мм"},
    "99.5x99.5": {"width_mm": 99.5, "height_mm": 99.5, "width_px": 796, "height_px": 796, "name": "99.5x99.5 мм"},
    "20x15": {"width_mm": 20, "height_mm": 15, "width_px": 160, "height_px": 120, "name": "20x15 мм"},
    "17x15": {"width_mm": 17, "height_mm": 15, "width_px": 136, "height_px": 120, "name": "17x15 мм"},
    "16x16": {"width_mm": 16, "height_mm": 16, "width_px": 128, "height_px": 128, "name": "16x16 мм"},
    "58x60": {"width_mm": 58, "height_mm": 60, "width_px": 464, "height_px": 480, "name": "58x60 мм"},
    "40x15": {"width_mm": 40, "height_mm": 15, "width_px": 320, "height_px": 120, "name": "40x15 мм"},
    "55x60": {"width_mm": 55, "height_mm": 60, "width_px": 440, "height_px": 480, "name": "55x60 мм"},
    "50x70": {"width_mm": 50, "height_mm": 70, "width_px": 400, "height_px": 560, "name": "50x70 мм"},
}

# Коэффициент пересчета: 1 мм = 8 px
MM_TO_PX = 8
QR_ONLY_SIZE_KEYS = {"17x15", "16x16", "20x15"}
SYMBOL_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "symbols")
SYMBOL_ASSET_CANDIDATES = {
    "eac": ["eac.png"],
    "glass": ["glass.png", "fragile.png", "glass_fork.png"],
    "pp5": ["pp5.png", "recycle_pp5.png", "mobius_pp5.png"],
    "pet1": ["pet1.png", "recycle_pet1.png", "mobius_pet1.png", "01_pet.png"],
    "recycle": ["recycle.png"],
    "gost": ["gost.png"],
}


class ArialMetrics:
    """Точные метрики шрифта Arial"""
    
    # Таблица кегля в мм (из требования). Пересчёт: 1 мм = 8 px.
    FONT_MM_VALUES = [0.6, 0.8, 0.9, 1.0, 1.2, 1.3, 1.4, 1.5, 1.8, 2.5, 3.0]
    TITLE_MM_VALUES = [3.0, 2.5]
    BODY_MM_VALUES = [1.8, 1.5, 1.4, 1.3, 1.2, 1.0, 0.9, 0.8, 0.6]
    MICRO_PX_VALUES = [4, 3]
    # Для Arial Regular:
    # - заглавные ~72-73% кегля
    # - строчные ~52-53% кегля
    # - воздух ~25-30% кегля
    UPPERCASE_RATIO = 0.725
    LOWERCASE_RATIO = 0.525
    AIR_RATIO = 0.275
    
    # Для жирного начертания ширина увеличивается на 15-20%
    CHAR_WIDTH_RATIO = {
        'regular': 1.0,
        'bold': 1.18,  # +18%
    }
    
    # Средняя ширина символа (в % от высоты заглавной)
    AVG_CHAR_WIDTH_RATIO = 0.65

    @classmethod
    def _closest_font_px(cls, font_size_px: int) -> int:
        size_table_px = [max(5, int(round(mm * MM_TO_PX))) for mm in cls.FONT_MM_VALUES]
        return min(size_table_px, key=lambda x: abs(x - font_size_px))

    @classmethod
    def body_px_scale_desc(cls, allow_micro: bool = False) -> List[int]:
        scale = [max(5, int(round(mm * MM_TO_PX))) for mm in cls.BODY_MM_VALUES]
        if allow_micro:
            scale.extend(cls.MICRO_PX_VALUES)
        # unique + desc
        return sorted(set(scale), reverse=True)

    @classmethod
    def title_px_scale_desc(cls) -> List[int]:
        return [max(5, int(round(mm * MM_TO_PX))) for mm in cls.TITLE_MM_VALUES]
    
    @classmethod
    def get_char_height(cls, font_size_px: int, is_uppercase: bool = True) -> float:
        """Возвращает высоту символа в пикселях"""
        # В supersample-режиме нельзя привязываться к дискретной таблице:
        # иначе кегль и интерлиньяж оказываются в разных шкалах.
        real_size = max(1.0, float(font_size_px))
        if is_uppercase:
            return real_size * cls.UPPERCASE_RATIO
        return real_size * cls.LOWERCASE_RATIO
    
    @classmethod
    def get_line_height(cls, font_size_px: int) -> float:
        """Возвращает полную высоту строки"""
        real_size = max(1.0, float(font_size_px))
        uppercase = real_size * cls.UPPERCASE_RATIO
        air = real_size * cls.AIR_RATIO
        return uppercase + air
    
    @classmethod
    def estimate_text_width(cls, text: str, font_size_px: int, is_bold: bool = False) -> int:
        """Оценивает ширину текста"""
        char_height = cls.get_char_height(font_size_px, True)
        avg_char_width = char_height * cls.AVG_CHAR_WIDTH_RATIO
        width_mult = cls.CHAR_WIDTH_RATIO['bold'] if is_bold else cls.CHAR_WIDTH_RATIO['regular']
        
        space_count = text.count(' ')
        text_without_spaces = text.replace(' ', '')
        
        width = len(text_without_spaces) * avg_char_width * width_mult
        width += space_count * (avg_char_width * 0.33)
        
        return int(width)


class GraphicElement:
    """Графический элемент на этикетке"""
    
    def __init__(
        self,
        element_type: str,
        size_mm: float = 8,
        required: bool = True,
        mm_to_px: float = MM_TO_PX,
        anchor: Optional[str] = None
    ):
        self.type = element_type
        self.size_mm = size_mm
        self.size_px = int(round(size_mm * mm_to_px))
        self.required = required
        self.anchor = anchor
        self.x = 0
        self.y = 0
        self.placed = False
    
    def to_dict(self) -> Dict:
        return {
            'type': self.type,
            'size_mm': self.size_mm,
            'size_px': self.size_px,
            'required': self.required,
            'anchor': self.anchor,
            'x': self.x,
            'y': self.y
        }


class EtoileLabelLayout:
    """
    Макет этикетки в стиле L'Etoile
    """
    
    QR_POSITION_OPTIONS = {'auto', 'top_left', 'top_right', 'bottom_left', 'bottom_right'}
    SYMBOLS_POSITION_OPTIONS = {'auto', 'top_left', 'top_right', 'bottom_left', 'bottom_center', 'bottom_right'}

    def __init__(self, size_key: str = "46x46", supersample: float = 1.0, keep_target_size: bool = True):
        if size_key not in PREDEFINED_SIZES:
            raise ValueError(f"Неизвестный размер: {size_key}. Доступны: {list(PREDEFINED_SIZES.keys())}")
        
        self.size_key = size_key
        self.size_info = PREDEFINED_SIZES[size_key]
        self.supersample = max(1.0, float(supersample))
        self.keep_target_size = bool(keep_target_size)
        self.width_mm = self.size_info["width_mm"]
        self.height_mm = self.size_info["height_mm"]
        self.target_width_px = self.size_info["width_px"]
        self.target_height_px = self.size_info["height_px"]
        self.width_px = int(round(self.target_width_px * self.supersample))
        self.height_px = int(round(self.target_height_px * self.supersample))
        self.qr_only_layout = size_key in QR_ONLY_SIZE_KEYS
        
        self.mm_to_px = MM_TO_PX * self.supersample
        self.margin = self.mm(1.0)
        self.text_padding = self.mm(1.25)
        self.zone_gap = self.mm(1.25)
        self.block_gap = self.mm(1.25)
        self.graphics_safe_padding = self.mm(0.6)
        
        self.work_x = self.margin
        self.work_y = self.margin
        self.work_width = self.width_px - 2 * self.margin
        self.work_height = self.height_px - 2 * self.margin
        self.text_bottom_limit = self.work_y + self.work_height - self.zone_gap
        self.last_text_end_y = self.work_y + self.text_padding
        
        # Больше пространства отдаём тексту.
        self.text_area_ratio = 0.94
        self.graphics_area_ratio = 0.06
        
        self.graphic_elements: List[GraphicElement] = []
        self.qr_position = 'auto'
        self.symbols_position = 'auto'
        self.symbol_positions: Dict[str, str] = {}
        self.symbol_image_cache: Dict[str, Optional[Image.Image]] = {}
        
        # Кэш шрифтов
        self.font_cache = {}
        self.font_regular_path = self._find_font_path(
            ["arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf"]
        )
        self.font_bold_path = self._find_font_path(
            ["arialbd.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf"]
        ) or self.font_regular_path
        self.font_regular = self._load_font(self.font_regular_path, 10)
        self.font_bold = self._load_font(self.font_bold_path, 10) or self.font_regular
        
        print(f"\n📐 Этикетка: {self.size_info['name']} → {self.target_width_px}x{self.target_height_px} px")
        if self.supersample > 1.0:
            print(f"   Supersample x{self.supersample:.1f}: {self.width_px}x{self.height_px} px")
        print(f"   Рабочая область: {self.work_width}x{self.work_height} px")
        print(f"   Соотношение: текст {self.text_area_ratio*100:.0f}% / графика {self.graphics_area_ratio*100:.0f}%")

    def mm(self, value_mm: float) -> int:
        """Конвертирует миллиметры в пиксели по формуле 1 мм = 8 px."""
        return max(1, int(round(value_mm * self.mm_to_px)))
    
    def _find_font_path(self, font_names: List[str]) -> Optional[str]:
        """Ищет доступный файл шрифта по списку кандидатов."""
        for font_name in font_names:
            font_paths = [
                font_name,
                f"C:/Windows/Fonts/{font_name}",
                f"/usr/share/fonts/truetype/msttcorefonts/{font_name}",
                f"/usr/share/fonts/truetype/liberation/{font_name}",
                f"/System/Library/Fonts/{font_name}",
                f"/Library/Fonts/{font_name}",
            ]
            for path in font_paths:
                if os.path.exists(path):
                    return path
        return None

    def _load_font(self, font_path: Optional[str], size_px: int) -> Optional[ImageFont.FreeTypeFont]:
        """Загружает шрифт конкретного размера."""
        if not font_path:
            return None
        try:
            return ImageFont.truetype(font_path, size_px)
        except:
            return None
    
    def get_font(self, size_px: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Получает шрифт нужного размера"""
        cache_key = f"{size_px}_{bold}"
        
        if cache_key in self.font_cache:
            return self.font_cache[cache_key]
        
        font_path = self.font_bold_path if bold else self.font_regular_path
        font = self._load_font(font_path, size_px)
        if font is None:
            try:
                fallback = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
                font = ImageFont.truetype(fallback, size_px)
            except Exception:
                font = ImageFont.load_default()
        
        self.font_cache[cache_key] = font
        return font
    
    def add_graphic_element(self, element_type: str, size_mm: float = 8, required: bool = True, anchor: Optional[str] = None):
        """Добавляет графический элемент"""
        self.graphic_elements.append(GraphicElement(element_type, size_mm, required, mm_to_px=self.mm_to_px, anchor=anchor))
    
    def calculate_required_graphics_area(self) -> int:
        """Рассчитывает площадь для графики"""
        total_area = 0
        for element in self.graphic_elements:
            element_area = element.size_px * element.size_px
            safe_area = (element.size_px + 2 * self.graphics_safe_padding) ** 2
            total_area += max(element_area, safe_area)
        return total_area

    def update_content_ratios(self):
        """Обновляет соотношения: графика 6%, текст 94%."""
        work_area = self.work_width * self.work_height
        if work_area <= 0:
            self.text_area_ratio = 0.94
            self.graphics_area_ratio = 0.06
            return

        # Фиксируем компактную область под графику.
        self.graphics_area_ratio = 0.06
        self.text_area_ratio = 0.94
    
    def optimize_text_font_size(self, text_blocks: List[Dict], text_size_multiplier: float = 1.0) -> int:
        """Находит лучший размер: чем меньше текст, тем крупнее шрифт (адаптивное масштабирование)."""
        required_graphics_area = self.calculate_required_graphics_area()
        work_area = self.work_width * self.work_height
        rules_area = self.target_width_px * self.target_height_px
        reserved_graphics_area = max(required_graphics_area, int(work_area * self.graphics_area_ratio))
        available_text_area = max(1, work_area - reserved_graphics_area)

        # Исключаем заголовок из подсчета для адаптивного масштабирования
        body_blocks = [b for b in text_blocks if b.get('type') != 'title']
        total_chars = sum(len(block.get('text', '')) for block in body_blocks)
        if total_chars == 0:
            return int(round(8 * text_size_multiplier))

        char_width_ratio = 0.65
        raw_optimal = math.sqrt(available_text_area / (total_chars * char_width_ratio))

        # Адаптивное масштабирование: чем меньше текста, тем крупнее шрифт
        # Используем обратную зависимость от количества символов
        text_volume_factor = 1.0
        if total_chars < 100:
            text_volume_factor = 2.5  # Очень мало текста - очень крупный шрифт
        elif total_chars < 300:
            text_volume_factor = 2.0
        elif total_chars < 500:
            text_volume_factor = 1.7
        elif total_chars < 1000:
            text_volume_factor = 1.4
        elif total_chars < 2000:
            text_volume_factor = 1.2
        # Для больших объемов текста используем стандартное масштабирование
        
        raw_optimal *= text_volume_factor

        # Корректировка для больших этикеток.
        if rules_area >= 300000:
            raw_optimal *= 1.45
        elif rules_area >= 200000:
            raw_optimal *= 1.35
        elif rules_area >= 140000:
            raw_optimal *= 1.25

        # Применяем множитель из настроек
        raw_optimal *= text_size_multiplier

        allow_micro = rules_area <= 120000
        body_scale = self._body_size_candidates()

        optimal_size = body_scale[-1]
        for size_px in body_scale:
            if raw_optimal >= size_px:
                optimal_size = size_px
                break

        # Защита от слишком мелкого шрифта, если текста не так много.
        if rules_area >= 200000 and total_chars <= 10000:
            optimal_size = max(optimal_size, self._scale_font_px(9))
        elif rules_area >= 140000 and total_chars <= 8000:
            optimal_size = max(optimal_size, self._scale_font_px(8))

        # Ограничиваем верхний порог, чтобы не получать "кашу" при больших px-размерах макета.
        max_readable = self._max_readable_body_font_px()
        optimal_size = min(optimal_size, max_readable)

        print(f"   Оптимизация: {total_chars} символов, кегль {optimal_size}px (область={work_area}, множитель={text_size_multiplier:.2f})")
        return optimal_size


    def _body_size_candidates(self) -> List[int]:
        work_area = self.target_width_px * self.target_height_px
        allow_micro = True
        base = [self._scale_font_px(px) for px in ArialMetrics.body_px_scale_desc(allow_micro=allow_micro)]
        base = sorted(
            set(base + [self._scale_font_px(8), self._scale_font_px(7), self._scale_font_px(6)]),
            reverse=True
        )

        # Для крупных этикеток добавляем значительно более крупные body-кегли.
        if work_area >= 500000:
            base = sorted(set([self._scale_font_px(v) for v in [30, 28, 26, 24, 22, 20, 18, 16]] + base), reverse=True)
        elif work_area >= 300000:
            base = sorted(set([self._scale_font_px(v) for v in [26, 24, 22, 20, 18, 16]] + base), reverse=True)
        elif work_area >= 200000:
            base = sorted(set([self._scale_font_px(v) for v in [22, 20, 18, 16]] + base), reverse=True)

        return base

    def _scale_font_px(self, px: int) -> int:
        return max(1, int(round(px * self.supersample)))

    def _max_readable_body_font_px(self) -> int:
        """Верхняя граница body-кегля для читаемого плотного набора."""
        shortest_side = max(1, min(self.width_px, self.height_px))
        # Эмпирический предел: ~4.5% короткой стороны.
        cap = int(round(shortest_side * 0.045))
        return max(self._scale_font_px(8), cap)

    def _font_try_order(self, base_font_size: int) -> List[int]:
        candidates = self._body_size_candidates()
        if not candidates:
            return [base_font_size]
        # Начинаем с самого крупного, чтобы максимально использовать пространство.
        return candidates

    def _text_capacity_height(self) -> int:
        start_y = self.work_y + self.text_padding
        return max(1, self.text_bottom_limit - start_y)

    def _fit_score(self, used_height: int) -> float:
        return float(used_height) / float(self._text_capacity_height())

    def _choose_best_font_size(self, draw, text_blocks: List[Dict], base_font_size: int) -> int:
        best_fit = base_font_size
        best_score = -1.0
        # Меньшая целевая плотность = лучше читаемость.
        target_fill = 0.78

        for candidate in self._font_try_order(base_font_size):
            if not self._place_text_blocks(draw, text_blocks, candidate, dry_run=True):
                continue
            used_height = self.last_text_end_y - (self.work_y + self.text_padding)
            score = self._fit_score(used_height)
            if score > best_score:
                best_score = score
                best_fit = candidate
            if score >= target_fill:
                return candidate

        return best_fit

    def _text_flow_region(self) -> Dict[str, int]:
        """Возвращает область основного потока (без графики)."""
        x = self.work_x + self.text_padding
        w = self.work_width - (2 * self.text_padding)
        return {'x': x, 'w': max(self.mm(8), w)}
    
    def render(self, data: Dict) -> Image.Image:
        """Рисует готовую этикетку."""
        image = Image.new('RGB', (self.width_px, self.height_px), 'white')
        draw = ImageDraw.Draw(image)
        self.qr_position = self._normalize_qr_position(data.get('qr_position'))
        self.symbols_position = self._normalize_symbols_position(data.get('symbols_position'))
        self.symbol_positions = self._normalize_symbol_positions(data.get('symbol_positions'))

        draw.rectangle([(0, 0), (self.width_px - 1, self.height_px - 1)], outline='#000000', width=1)

        # Особый случай: только QR.
        if self.qr_only_layout:
            self.graphic_elements = []
            if data.get('barcode_data'):
                self.add_graphic_element('qr', size_mm=min(self.width_mm, self.height_mm) * 0.85, required=True)
            self._place_graphic_elements()
            self._draw_graphic_elements(draw, image)
            return self._finalize_image(image)

        full_text_mode = bool(data.get('full_text_mode'))
        text_blocks = []
        if full_text_mode:
            if data.get('description'):
                text_blocks.append({'type': 'description', 'text': data['description'], 'priority': 1, 'bold': False, 'multiplier': 1.0, 'align': 'left'})
        else:
            # Заголовок - крупный, жирный, по центру
            title_multiplier = float(data.get('title_size_multiplier', 3.5))
            if data.get('title'):
                text_blocks.append({'type': 'title', 'text': data['title'].upper(), 'priority': 1, 'bold': True, 'multiplier': title_multiplier, 'align': 'center'})
            # Оригинальное название - по центру, под заголовком
            if data.get('original_name'):
                text_blocks.append({'type': 'original_name', 'text': data['original_name'], 'priority': 2, 'bold': False, 'multiplier': 1.0, 'align': 'center'})
            # Описание товара
            if data.get('description'):
                text_blocks.append({'type': 'description', 'text': data['description'], 'priority': 3, 'bold': False, 'multiplier': 1.0, 'align': 'left'})
            # Артикул - внизу
            if data.get('article'):
                text_blocks.append({'type': 'article', 'text': data['article'], 'priority': 4, 'bold': False, 'multiplier': 0.9, 'align': 'left'})
            # Дополнительные поля
            if data.get('short_code'):
                text_blocks.append({'type': 'short_code', 'text': data['short_code'], 'priority': 5, 'bold': False, 'multiplier': 0.85, 'align': 'left'})
            if data.get('batch_number'):
                text_blocks.append({'type': 'batch', 'text': f"№ партии: {data['batch_number']}", 'priority': 5, 'bold': False, 'multiplier': 0.9, 'align': 'left'})
            if data.get('expiry_date'):
                text_blocks.append({'type': 'expiry', 'text': f"Годен до: {data['expiry_date']}", 'priority': 5, 'bold': False, 'multiplier': 0.9, 'align': 'left'})

        # Графика
        self.graphic_elements = []
        qr_size_mm = None
        if data.get('barcode_data'):
            qr_size_mm = max(4.5, min(10.0, min(self.width_mm, self.height_mm) * 0.10))
            self.add_graphic_element('qr', size_mm=qr_size_mm, required=True, anchor=self.qr_position)
        symbol_size_mm = self._symbol_size_mm_limit(qr_size_mm)
        for symbol in self._collect_graphic_symbols(data):
            symbol_anchor = self.symbol_positions.get(symbol, self.symbols_position)
            if symbol == 'recycle':
                self.add_graphic_element('recycle', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)
            elif symbol == 'gost':
                self.add_graphic_element('gost', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)
            elif symbol == 'eac':
                self.add_graphic_element('eac', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)
            elif symbol == 'glass':
                self.add_graphic_element('glass', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)
            elif symbol == 'pp5':
                self.add_graphic_element('pp5', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)
            elif symbol == 'pet1':
                self.add_graphic_element('pet1', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)

        self.update_content_ratios()
        print(f"   Соотношение: текст {self.text_area_ratio*100:.0f}% / графика {self.graphics_area_ratio*100:.0f}%")

        # Применяем адаптивное масштабирование и множители из настроек
        text_size_multiplier = float(data.get('text_size_multiplier', 1.0))
        base_font_size = self.optimize_text_font_size(text_blocks, text_size_multiplier=text_size_multiplier)

        # Сначала размещаем графику, затем гарантированно подбираем кегль текста.
        self._place_graphic_elements()
        final_font_size = self._fit_font_size_guaranteed(draw, text_blocks, base_font_size)
        self._place_text_blocks(draw, text_blocks, final_font_size, dry_run=False)
        self._draw_graphic_elements(draw, image)

        return self._finalize_image(image)

    def render_svg(self, data: Dict) -> str:
        """Рисует готовую этикетку в SVG (векторный текст)."""
        image = Image.new('RGB', (self.width_px, self.height_px), 'white')
        draw = ImageDraw.Draw(image)
        self.qr_position = self._normalize_qr_position(data.get('qr_position'))
        self.symbols_position = self._normalize_symbols_position(data.get('symbols_position'))
        self.symbol_positions = self._normalize_symbol_positions(data.get('symbol_positions'))

        if self.qr_only_layout:
            self.graphic_elements = []
            if data.get('barcode_data'):
                self.add_graphic_element('qr', size_mm=min(self.width_mm, self.height_mm) * 0.85, required=True)
            self._place_graphic_elements()
            return self._build_svg_document([], include_border=True)

        full_text_mode = bool(data.get('full_text_mode'))
        text_blocks = []
        if full_text_mode:
            if data.get('description'):
                text_blocks.append({'type': 'description', 'text': data['description'], 'priority': 1, 'bold': False, 'multiplier': 1.0, 'align': 'left'})
        else:
            # Заголовок - крупный, жирный, по центру
            title_multiplier = float(data.get('title_size_multiplier', 3.5))
            if data.get('title'):
                text_blocks.append({'type': 'title', 'text': data['title'].upper(), 'priority': 1, 'bold': True, 'multiplier': title_multiplier, 'align': 'center'})
            # Оригинальное название - по центру, под заголовком
            if data.get('original_name'):
                text_blocks.append({'type': 'original_name', 'text': data['original_name'], 'priority': 2, 'bold': False, 'multiplier': 1.0, 'align': 'center'})
            # Описание товара
            if data.get('description'):
                text_blocks.append({'type': 'description', 'text': data['description'], 'priority': 3, 'bold': False, 'multiplier': 1.0, 'align': 'left'})
            # Артикул - внизу
            if data.get('article'):
                text_blocks.append({'type': 'article', 'text': data['article'], 'priority': 4, 'bold': False, 'multiplier': 0.9, 'align': 'left'})
            # Дополнительные поля
            if data.get('short_code'):
                text_blocks.append({'type': 'short_code', 'text': data['short_code'], 'priority': 5, 'bold': False, 'multiplier': 0.85, 'align': 'left'})
            if data.get('batch_number'):
                text_blocks.append({'type': 'batch', 'text': f"№ партии: {data['batch_number']}", 'priority': 5, 'bold': False, 'multiplier': 0.9, 'align': 'left'})
            if data.get('expiry_date'):
                text_blocks.append({'type': 'expiry', 'text': f"Годен до: {data['expiry_date']}", 'priority': 5, 'bold': False, 'multiplier': 0.9, 'align': 'left'})

        self.graphic_elements = []
        qr_size_mm = None
        if data.get('barcode_data'):
            qr_size_mm = max(4.5, min(10.0, min(self.width_mm, self.height_mm) * 0.10))
            self.add_graphic_element('qr', size_mm=qr_size_mm, required=True, anchor=self.qr_position)
        symbol_size_mm = self._symbol_size_mm_limit(qr_size_mm)
        for symbol in self._collect_graphic_symbols(data):
            symbol_anchor = self.symbol_positions.get(symbol, self.symbols_position)
            if symbol == 'recycle':
                self.add_graphic_element('recycle', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)
            elif symbol == 'gost':
                self.add_graphic_element('gost', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)
            elif symbol == 'eac':
                self.add_graphic_element('eac', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)
            elif symbol == 'glass':
                self.add_graphic_element('glass', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)
            elif symbol == 'pp5':
                self.add_graphic_element('pp5', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)
            elif symbol == 'pet1':
                self.add_graphic_element('pet1', size_mm=symbol_size_mm, required=False, anchor=symbol_anchor)

        self.update_content_ratios()
        # Применяем адаптивное масштабирование и множители из настроек
        text_size_multiplier = float(data.get('text_size_multiplier', 1.0))
        base_font_size = self.optimize_text_font_size(text_blocks, text_size_multiplier=text_size_multiplier)
        self._place_graphic_elements()
        final_font_size = self._fit_font_size_guaranteed(draw, text_blocks, base_font_size)

        _, text_lines = self._collect_text_layout(draw, text_blocks, final_font_size)
        return self._build_svg_document(text_lines, include_border=True)

    def _fit_font_size_guaranteed(self, draw, text_blocks: List[Dict], base_font_size: int) -> int:
        """Гарантированно подбирает кегль, чтобы текст полностью влезал."""
        candidates = []
        candidates.extend(self._font_try_order(base_font_size))
        # Добавляем аварийную шкалу уменьшения до очень мелкого кегля.
        candidates.extend([self._scale_font_px(v) for v in [6, 5, 4, 3, 2]])
        candidates = sorted(set(candidates), reverse=True)

        for size in candidates:
            if self._place_text_blocks(draw, text_blocks, size, dry_run=True):
                return size
        return candidates[-1] if candidates else max(1, base_font_size)

    def _collect_text_layout(self, draw, text_blocks: List[Dict], base_font_size: int) -> Tuple[bool, List[Dict]]:
        """Возвращает рассчитанные строки текста для SVG-рендера."""
        return self._layout_text_blocks_internal(draw, text_blocks, base_font_size, dry_run=True, collect_lines=True)

    def _build_svg_document(self, text_lines: List[Dict], include_border: bool = True) -> str:
        parts: List[str] = []
        parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width_px}" height="{self.height_px}" viewBox="0 0 {self.width_px} {self.height_px}">')
        parts.append(f'<rect x="0" y="0" width="{self.width_px}" height="{self.height_px}" fill="white"/>')
        if include_border:
            parts.append(f'<rect x="0.5" y="0.5" width="{self.width_px - 1}" height="{self.height_px - 1}" fill="none" stroke="#000000" stroke-width="1"/>')

        for line in text_lines:
            baseline_y = line['y'] + int(round(line['font_size'] * 0.82))
            font_weight = '700' if line['bold'] else '400'
            align = line.get('align', 'left')
            # Для SVG: если центрирование, используем text-anchor="middle" и центр этикетки
            if align == 'center':
                text_anchor = 'middle'
                # x должен быть центром текста (центр этикетки)
                x_pos = self.width_px // 2
            else:
                text_anchor = 'start'
                x_pos = line['x']
            parts.append(
                f'<text x="{x_pos}" y="{baseline_y}" '
                f'font-family="Arial, Liberation Sans, DejaVu Sans, sans-serif" '
                f'font-size="{line["font_size"]}" font-weight="{font_weight}" '
                f'text-anchor="{text_anchor}" fill="#000000">'
                f'{escape(str(line["text"]))}</text>'
            )

        parts.extend(self._graphic_elements_svg())
        parts.append('</svg>')
        return ''.join(parts)

    def _graphic_elements_svg(self) -> List[str]:
        parts: List[str] = []
        for element in self.graphic_elements:
            if not element.placed:
                continue
            x, y, size = element.x, element.y, element.size_px
            if element.type == 'qr':
                parts.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="white" stroke="black" stroke-width="1"/>')
                cell_size = max(2, size // 10)
                for i in range(8):
                    for j in range(8):
                        if (i + j) % 2 == 0:
                            cx = x + i * cell_size + cell_size // 2
                            cy = y + j * cell_size + cell_size // 2
                            parts.append(
                                f'<rect x="{cx - cell_size//2}" y="{cy - cell_size//2}" '
                                f'width="{cell_size}" height="{cell_size}" fill="black"/>'
                            )
                parts.append(
                    f'<text x="{x + 2}" y="{y + size - max(3, size // 10)}" '
                    f'font-family="Arial, Liberation Sans, DejaVu Sans, sans-serif" '
                    f'font-size="{max(6, size // 6)}" fill="black">QR</text>'
                )
            elif element.type in SYMBOL_ASSET_CANDIDATES:
                symbol_data = self._symbol_asset_data_uri(element.type)
                if symbol_data:
                    parts.append(
                        f'<image x="{x}" y="{y}" width="{size}" height="{size}" preserveAspectRatio="xMidYMid meet" '
                        f'href="{symbol_data}" />'
                    )
                else:
                    label = element.type.upper()
                    parts.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="none" stroke="#444" stroke-width="1"/>')
                    parts.append(
                        f'<text x="{x + 2}" y="{y + max(10, size // 2)}" '
                        f'font-family="Arial, Liberation Sans, DejaVu Sans, sans-serif" '
                        f'font-size="{max(8, size // 3)}" fill="#222">{escape(label)}</text>'
                    )
        return parts

    def _finalize_image(self, image: Image.Image) -> Image.Image:
        if self.supersample <= 1.0 or not self.keep_target_size:
            return image
        resampling = getattr(Image, 'Resampling', Image)
        downscaled = image.resize((self.target_width_px, self.target_height_px), resample=resampling.LANCZOS)
        return downscaled.filter(ImageFilter.UnsharpMask(radius=1.1, percent=120, threshold=2))

    def _place_graphic_elements(self):
        """Размещает графику с поддержкой пользовательских позиций."""
        if not self.graphic_elements:
            self.text_bottom_limit = self.work_y + self.work_height - self.zone_gap
            return

        for element in self.graphic_elements:
            element.placed = False

        self.graphic_elements.sort(key=lambda e: e.size_px, reverse=True)

        if self.qr_only_layout and len(self.graphic_elements) == 1 and self.graphic_elements[0].type == 'qr':
            element = self.graphic_elements[0]
            element.x = self.work_x + (self.work_width - element.size_px) // 2
            element.y = self.work_y + (self.work_height - element.size_px) // 2
            element.x = max(self.work_x, min(element.x, self.work_x + self.work_width - element.size_px))
            element.y = max(self.work_y, min(element.y, self.work_y + self.work_height - element.size_px))
            element.placed = True
            self.text_bottom_limit = self.work_y + self.zone_gap
            print("   Размещён QR (QR-only)")
            return

        qr_elements = [e for e in self.graphic_elements if e.type == 'qr']
        symbol_elements = [e for e in self.graphic_elements if e.type != 'qr']

        if qr_elements and self.qr_position != 'auto':
            self._place_element_by_anchor(qr_elements[0], self.qr_position)
            print(f"   Размещён qr ({self.qr_position})")

        anchored_symbols = [e for e in symbol_elements if e.anchor and e.anchor != 'auto']
        auto_symbols = [e for e in symbol_elements if not e.anchor or e.anchor == 'auto']

        if anchored_symbols:
            self._place_anchored_symbols_without_overlap(anchored_symbols, qr_elements[0] if qr_elements else None)
        if auto_symbols and self.symbols_position != 'auto':
            self._place_symbol_group_by_anchor(auto_symbols, self.symbols_position)
            print(f"   Размещены символы ({self.symbols_position})")

        # Если QR и символы выбраны в одном углу, разводим их без наложения.
        if (
            qr_elements
            and auto_symbols
            and self.qr_position != 'auto'
            and self.symbols_position != 'auto'
            and self.qr_position == self.symbols_position
        ):
            self._resolve_qr_symbol_overlap(qr_elements[0], auto_symbols, self.qr_position)

        remaining = [e for e in self.graphic_elements if not e.placed]
        if remaining:
            self._place_remaining_elements_bottom_strip(remaining)
        else:
            self.text_bottom_limit = self.work_y + self.work_height - self.zone_gap
            self._recalculate_text_bottom_limit_from_graphics()

    def _normalize_qr_position(self, raw_position: Optional[str]) -> str:
        position = str(raw_position or 'auto').strip().lower()
        if position not in self.QR_POSITION_OPTIONS:
            return 'auto'
        return position

    def _normalize_symbols_position(self, raw_position: Optional[str]) -> str:
        position = str(raw_position or 'auto').strip().lower()
        if position not in self.SYMBOLS_POSITION_OPTIONS:
            return 'auto'
        return position

    def _normalize_symbol_positions(self, raw_positions) -> Dict[str, str]:
        if not isinstance(raw_positions, dict):
            return {}
        normalized: Dict[str, str] = {}
        for key, value in raw_positions.items():
            symbol = str(key).strip().lower()
            anchor = str(value).strip().lower()
            if symbol in {'eac', 'glass', 'pp5', 'pet1', 'recycle', 'gost'} and anchor in self.SYMBOLS_POSITION_OPTIONS:
                normalized[symbol] = anchor
        return normalized

    def _collect_graphic_symbols(self, data: Dict) -> List[str]:
        symbols: List[str] = []
        # Если graphic_symbols передан, считаем его единственным источником (управление чекбоксами UI).
        if 'graphic_symbols' in data:
            raw_symbols = data.get('graphic_symbols')
            if isinstance(raw_symbols, str):
                raw_symbols = [x.strip() for x in raw_symbols.split(',')]
            if isinstance(raw_symbols, list):
                for symbol in raw_symbols:
                    normalized = str(symbol).strip().lower()
                    if normalized in {'recycle', 'gost', 'eac', 'glass', 'pp5', 'pet1'}:
                        symbols.append(normalized)
            # unique preserving order
            unique: List[str] = []
            seen = set()
            for symbol in symbols:
                if symbol in seen:
                    continue
                seen.add(symbol)
                unique.append(symbol)
            return unique

        # Фолбэк для старых вызовов API без graphic_symbols.
        icons_text = str(data.get('icons', ''))
        if '♻' in icons_text:
            symbols.append('recycle')
        if 'ГОСТ' in icons_text.upper():
            symbols.append('gost')
        if 'EAC' in icons_text.upper():
            symbols.append('eac')

        # unique preserving order
        unique: List[str] = []
        seen = set()
        for symbol in symbols:
            if symbol in seen:
                continue
            seen.add(symbol)
            unique.append(symbol)
        return unique

    def _anchor_origin(self, anchor: str, object_w: int, object_h: int) -> Tuple[int, int]:
        safe_left = self.work_x + self.graphics_safe_padding
        safe_top = self.work_y + self.graphics_safe_padding
        safe_right = self.work_x + self.work_width - self.graphics_safe_padding
        safe_bottom = self.work_y + self.work_height - self.graphics_safe_padding

        if anchor == 'top_left':
            x = safe_left
            y = safe_top
        elif anchor == 'top_right':
            x = safe_right - object_w
            y = safe_top
        elif anchor == 'bottom_left':
            x = safe_left
            y = safe_bottom - object_h
        elif anchor == 'bottom_center':
            x = safe_left + (safe_right - safe_left - object_w) // 2
            y = safe_bottom - object_h
        else:  # bottom_right
            x = safe_right - object_w
            y = safe_bottom - object_h

        x = max(safe_left, min(x, safe_right - object_w))
        y = max(safe_top, min(y, safe_bottom - object_h))
        return x, y

    def _place_element_by_anchor(self, element: GraphicElement, anchor: str):
        x, y = self._anchor_origin(anchor, element.size_px, element.size_px)
        element.x = x
        element.y = y
        element.placed = True

    def _place_symbol_group_by_anchor(self, elements: List[GraphicElement], anchor: str):
        if not elements:
            return
        gap = self.mm(0.9)
        group_w = sum(e.size_px for e in elements) + gap * (len(elements) - 1)
        group_h = max(e.size_px for e in elements)
        start_x, start_y = self._anchor_origin(anchor, group_w, group_h)
        self._place_symbol_group_at(elements, start_x, start_y)

    def _place_anchored_symbols_without_overlap(self, elements: List[GraphicElement], qr_element: Optional[GraphicElement]):
        by_anchor: Dict[str, List[GraphicElement]] = {}
        for element in elements:
            by_anchor.setdefault(element.anchor or 'auto', []).append(element)

        occupied_rects: List[Tuple[int, int, int, int]] = []
        if qr_element is not None and qr_element.placed:
            occupied_rects.append((qr_element.x, qr_element.y, qr_element.x + qr_element.size_px, qr_element.y + qr_element.size_px))

        anchor_order = ['top_left', 'top_right', 'bottom_left', 'bottom_center', 'bottom_right']
        for anchor in anchor_order:
            group = by_anchor.get(anchor, [])
            if not group:
                continue
            self._place_symbol_group_by_anchor(group, anchor)
            self._nudge_group_from_occupied(group, anchor, occupied_rects)
            bounds = self._elements_bounds(group)
            if bounds:
                occupied_rects.append(bounds)
            print(f"   Размещены символы ({anchor})")

    def _nudge_group_from_occupied(self, elements: List[GraphicElement], anchor: str, occupied_rects: List[Tuple[int, int, int, int]]):
        bounds = self._elements_bounds(elements)
        if not bounds:
            return
        if not any(self._rects_overlap(bounds, rect) for rect in occupied_rects):
            return

        group_w = bounds[2] - bounds[0]
        group_h = bounds[3] - bounds[1]
        base_x, base_y = self._anchor_origin(anchor, group_w, group_h)
        step = self.mm(1.0)
        safe_left = self.work_x + self.graphics_safe_padding
        safe_top = self.work_y + self.graphics_safe_padding
        safe_right = self.work_x + self.work_width - self.graphics_safe_padding
        safe_bottom = self.work_y + self.work_height - self.graphics_safe_padding

        def clamp(x, y):
            cx = max(safe_left, min(x, safe_right - group_w))
            cy = max(safe_top, min(y, safe_bottom - group_h))
            return cx, cy

        for i in range(1, 32):
            d = i * step
            if anchor == 'top_left':
                offsets = [(0, d), (d, 0), (d, d)]
            elif anchor == 'top_right':
                offsets = [(0, d), (-d, 0), (-d, d)]
            elif anchor == 'bottom_left':
                offsets = [(0, -d), (d, 0), (d, -d)]
            elif anchor == 'bottom_center':
                offsets = [(0, -d), (d, -d), (-d, -d), (d, 0), (-d, 0)]
            else:  # bottom_right
                offsets = [(0, -d), (-d, 0), (-d, -d)]

            for ox, oy in offsets:
                cx, cy = clamp(base_x + ox, base_y + oy)
                self._place_symbol_group_at(elements, cx, cy)
                test_bounds = self._elements_bounds(elements)
                if test_bounds and not any(self._rects_overlap(test_bounds, rect) for rect in occupied_rects):
                    return

    def _place_symbol_group_at(self, elements: List[GraphicElement], start_x: int, start_y: int):
        if not elements:
            return
        gap = self.mm(0.9)
        group_h = max(e.size_px for e in elements)
        safe_left = self.work_x + self.graphics_safe_padding
        safe_top = self.work_y + self.graphics_safe_padding
        safe_right = self.work_x + self.work_width - self.graphics_safe_padding
        safe_bottom = self.work_y + self.work_height - self.graphics_safe_padding

        cursor_x = max(safe_left, start_x)
        start_y = max(safe_top, min(start_y, safe_bottom - group_h))
        for element in elements:
            element.x = max(safe_left, min(cursor_x, safe_right - element.size_px))
            element.y = start_y + (group_h - element.size_px) // 2
            element.placed = True
            cursor_x += element.size_px + gap

    def _elements_bounds(self, elements: List[GraphicElement]) -> Optional[Tuple[int, int, int, int]]:
        placed = [e for e in elements if e.placed]
        if not placed:
            return None
        x1 = min(e.x for e in placed)
        y1 = min(e.y for e in placed)
        x2 = max(e.x + e.size_px for e in placed)
        y2 = max(e.y + e.size_px for e in placed)
        return (x1, y1, x2, y2)

    def _rects_overlap(self, a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> bool:
        return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    def _resolve_qr_symbol_overlap(self, qr_element: GraphicElement, symbol_elements: List[GraphicElement], anchor: str):
        group_bounds = self._elements_bounds(symbol_elements)
        if not group_bounds:
            return
        qr_rect = (qr_element.x, qr_element.y, qr_element.x + qr_element.size_px, qr_element.y + qr_element.size_px)
        if not self._rects_overlap(qr_rect, group_bounds):
            return

        gap = self.mm(0.9)
        group_w = group_bounds[2] - group_bounds[0]
        group_h = group_bounds[3] - group_bounds[1]
        base_x, _ = self._anchor_origin(anchor, group_w, group_h)
        safe_top = self.work_y + self.graphics_safe_padding
        safe_bottom = self.work_y + self.work_height - self.graphics_safe_padding

        # Сначала двигаем вдоль "угла" (вниз для верхних углов, вверх для нижних).
        if anchor in {'top_left', 'top_right'}:
            candidate_y = qr_element.y + qr_element.size_px + gap
        else:
            candidate_y = qr_element.y - group_h - gap
        candidate_y = max(safe_top, min(candidate_y, safe_bottom - group_h))
        self._place_symbol_group_at(symbol_elements, base_x, candidate_y)

        group_bounds = self._elements_bounds(symbol_elements)
        if group_bounds and not self._rects_overlap(qr_rect, group_bounds):
            return

        # Фолбэк: сдвиг по горизонтали от QR, сохраняя привязку к углу.
        if anchor in {'top_left', 'bottom_left'}:
            candidate_x = qr_element.x + qr_element.size_px + gap
        else:
            candidate_x = qr_element.x - group_w - gap
        self._place_symbol_group_at(symbol_elements, candidate_x, candidate_y)

    def _place_remaining_elements_bottom_strip(self, elements: List[GraphicElement]):
        max_graphic_size = max(e.size_px for e in elements)
        min_strip = max_graphic_size + (2 * self.graphics_safe_padding)
        ratio_strip = int(self.work_height * self.graphics_area_ratio)
        strip_height = max(min_strip, ratio_strip)
        strip_height = min(strip_height, int(self.work_height * 0.16))

        strip_top = self.work_y + self.work_height - strip_height
        self.text_bottom_limit = max(self.work_y + self.mm(8), strip_top - self.zone_gap)

        left_edge = self.work_x + self.graphics_safe_padding
        right_edge = self.work_x + self.work_width - self.graphics_safe_padding
        gap = self.mm(1.5)

        cursor_right = right_edge
        cursor_y = strip_top + self.graphics_safe_padding

        for element in elements:
            x = cursor_right - element.size_px
            if x < left_edge:
                cursor_right = right_edge
                cursor_y += element.size_px + gap
                x = cursor_right - element.size_px

            y = min(cursor_y, self.work_y + self.work_height - self.graphics_safe_padding - element.size_px)
            element.x = max(left_edge, x)
            element.y = max(strip_top + self.graphics_safe_padding, y)
            element.placed = True
            cursor_right = element.x - gap
            print(f"   Размещён {element.type}")

        self._recalculate_text_bottom_limit_from_graphics()

    def _symbol_size_mm_limit(self, qr_size_mm: Optional[float]) -> float:
        """
        Ограничивает размер символов: их площадь не больше площади QR.
        Для квадратных символов это эквивалентно ограничению стороны.
        """
        default_mm = 4.8
        if qr_size_mm is None:
            return default_mm
        return max(3.6, min(default_mm, float(qr_size_mm)))

    def _recalculate_text_bottom_limit_from_graphics(self):
        default_bottom = self.work_y + self.work_height - self.zone_gap
        limit = default_bottom
        cutoff = self.work_y + int(self.work_height * 0.58)
        for element in self.graphic_elements:
            if not element.placed:
                continue
            if element.y >= cutoff:
                limit = min(limit, element.y - self.zone_gap)
        self.text_bottom_limit = max(self.work_y + self.mm(8), limit)

    def _place_text_blocks(self, draw, text_blocks: List[Dict], base_font_size: int, dry_run: bool = False) -> bool:
        """Размещает блоки текста по области, обходя графику."""
        success, _ = self._layout_text_blocks_internal(draw, text_blocks, base_font_size, dry_run=dry_run, collect_lines=False)
        return success

    def _layout_text_blocks_internal(
        self,
        draw,
        text_blocks: List[Dict],
        base_font_size: int,
        dry_run: bool = False,
        collect_lines: bool = False
    ) -> Tuple[bool, List[Dict]]:
        """Единый движок текста: построчное адаптивное обтекание графики."""
        region = self._text_flow_region()
        current_y = self.work_y + self.text_padding
        bottom_y = self.text_bottom_limit
        min_line_width = self.mm(6.25)
        collected_lines: List[Dict] = []

        occupied_zones = self._occupied_zones()

        for block in text_blocks:
            probe_x, probe_width = self._get_text_line_region(current_y, region['x'], region['w'], occupied_zones)
            probe_width = max(min_line_width, probe_width)

            font_size = self._resolve_block_font_size(block, base_font_size, probe_width, draw)
            font = self.get_font(font_size, block.get('bold', False))
            line_height = self._line_height_for_block(font_size, block.get('type', 'description'))
            align = block.get('align', 'left')
            success, current_y, block_lines = self._layout_block_lines_dynamic(
                text=str(block.get('text', '')),
                font=font,
                draw=draw,
                current_y=current_y,
                bottom_y=bottom_y,
                line_height=line_height,
                base_x=region['x'],
                base_w=region['w'],
                occupied_zones=occupied_zones,
                min_line_width=min_line_width,
                align=align
            )
            if not success:
                self.last_text_end_y = current_y
                return False, collected_lines

            if not dry_run:
                for item in block_lines:
                    draw.text((item['x'], item['y']), item['text'], fill='black', font=font)

            if not dry_run:
                print(f"   Блок {block['type']}: {font_size}px")
            if collect_lines:
                for item in block_lines:
                    collected_lines.append({
                        'x': item['x'],
                        'y': item['y'],
                        'text': item['text'],
                        'font_size': font_size,
                        'bold': bool(block.get('bold', False)),
                        'block_type': block.get('type', 'description'),
                        'align': block.get('align', 'left')
                    })
            current_y += self.block_gap

        self.last_text_end_y = current_y
        return True, collected_lines

    def _occupied_zones(self) -> List[Dict]:
        zones = []
        for element in self.graphic_elements:
            if element.placed:
                zones.append({
                    'x': element.x - self.graphics_safe_padding,
                    'y': element.y - self.graphics_safe_padding,
                    'w': element.size_px + (2 * self.graphics_safe_padding),
                    'h': element.size_px + (2 * self.graphics_safe_padding)
                })
        return zones

    def _layout_block_lines_dynamic(
        self,
        text: str,
        font,
        draw,
        current_y: int,
        bottom_y: int,
        line_height: int,
        base_x: int,
        base_w: int,
        occupied_zones: List[Dict],
        min_line_width: int,
        align: str = 'left'
    ) -> Tuple[bool, int, List[Dict]]:
        lines_out: List[Dict] = []
        paragraphs = [p.strip() for p in str(text).split('\n') if p.strip()]

        for paragraph in paragraphs:
            words = paragraph.split()
            if not words:
                continue

            while words:
                if current_y + line_height > bottom_y:
                    return False, current_y, lines_out

                line_x, line_w = self._get_text_line_region(current_y, base_x, base_w, occupied_zones)
                # Если на этой высоте полезная ширина слишком мала - опускаемся ниже.
                if line_w < min_line_width:
                    current_y += line_height
                    continue

                used = 0
                while used < len(words):
                    candidate = ' '.join(words[:used + 1])
                    if self._get_text_width(candidate, font, draw) <= line_w:
                        used += 1
                        continue
                    break

                if used == 0:
                    # Очень длинное слово: режем по символам под текущую ширину.
                    word = words[0]
                    chunk = []
                    idx = 0
                    while idx < len(word):
                        test = ''.join(chunk + [word[idx]])
                        if self._get_text_width(test, font, draw) <= max(1, line_w - self.mm(0.25)):
                            chunk.append(word[idx])
                            idx += 1
                        else:
                            break
                    if not chunk:
                        return False, current_y, lines_out
                    head = ''.join(chunk)
                    tail = word[len(head):]
                    line_text = head + ('-' if tail else '')
                    words = ([tail] if tail else []) + words[1:]
                else:
                    line_text = ' '.join(words[:used])
                    words = words[used:]

                # Вычисляем позицию x в зависимости от выравнивания
                if align == 'center':
                    text_width = self._get_text_width(line_text, font, draw)
                    # Для центрирования используем центр всей этикетки
                    center_x = self.width_px // 2
                    line_x = center_x - text_width // 2
                    # Минимальные ограничения только для очень длинного текста
                    # Не ограничиваем жестко, чтобы заголовок был точно по центру
                    if line_x < 0:
                        line_x = 0
                    elif line_x + text_width > self.width_px:
                        line_x = self.width_px - text_width
                else:  # left
                    pass  # Используем вычисленную позицию line_x

                lines_out.append({'x': line_x, 'y': current_y, 'text': line_text})
                current_y += line_height

        return True, current_y, lines_out

    def _line_height_for_block(self, font_size: int, block_type: str) -> int:
        """Возвращает интерлиньяж для соответствующего блока."""
        is_title = block_type == 'title'
        font = self.get_font(font_size, is_title)
        try:
            bbox = font.getbbox("Ag")
            glyph_h = max(1, bbox[3] - bbox[1])
        except Exception:
            glyph_h = max(1, int(round(ArialMetrics.get_line_height(font_size))))

        leading = 1.24 if is_title else 1.22
        return max(1, int(math.ceil(glyph_h * leading)))

    def _resolve_block_font_size(self, block: Dict, body_font_size: int, max_width: int, draw) -> int:
        """Динамический подбор шрифта: пытаемся крупнее body по возможности."""
        body_scale = self._body_size_candidates()

        if block.get('type') == 'title':
            # Пытаемся вписать заголовок покрупнее
            title_candidates = [self._scale_font_px(px) for px in ArialMetrics.title_px_scale_desc()]
            for size_px in title_candidates:
                font = self.get_font(size_px, True)
                lines = self._wrap_text_block(block.get('text', ''), font, max_width, draw)
                if len(lines) <= 2:
                    return size_px

            # Если не влезло при 2.5/3.0, пробуем, но уже по более пологой шкале body.
            for size_px in body_scale:
                if size_px <= body_font_size:
                    continue
                font = self.get_font(size_px, True)
                lines = self._wrap_text_block(block.get('text', ''), font, max_width, draw)
                if len(lines) <= 3:
                    return size_px

            return max(body_font_size + 1, body_scale[-1])

        if block.get('type') in {'short_code', 'batch', 'expiry'}:
            if body_font_size in body_scale:
                idx = body_scale.index(body_font_size)
                return body_scale[min(idx + 1, len(body_scale) - 1)]
            return body_scale[min(1, len(body_scale) - 1)]

        return min(body_font_size, self._max_readable_body_font_px())

    def _get_available_width(self, current_x: int, column_width: int, occupied_zones: List[Dict], current_y: int) -> int:
        max_width = column_width
        for zone in occupied_zones:
            zone_top = zone['y']
            zone_bottom = zone['y'] + zone['h']
            if current_y < zone_top or current_y > zone_bottom:
                continue
            if zone['x'] < current_x + max_width and zone['x'] + zone['w'] > current_x:
                max_width = min(max_width, zone['x'] - current_x - self.zone_gap)
        return max_width

    def _get_text_line_region(self, current_y: int, base_x: int, base_w: int, occupied_zones: List[Dict]) -> Tuple[int, int]:
        """Возвращает лучший горизонтальный сегмент для строки на текущем Y (эффект обтекания)."""
        line_left = base_x
        line_right = base_x + max(1, base_w)
        intervals = [(line_left, line_right)]

        for zone in occupied_zones:
            zone_top = zone['y']
            zone_bottom = zone['y'] + zone['h']
            if current_y < zone_top or current_y > zone_bottom:
                continue

            cut_left = max(line_left, zone['x'] - self.zone_gap)
            cut_right = min(line_right, zone['x'] + zone['w'] + self.zone_gap)
            if cut_left >= cut_right:
                continue

            next_intervals = []
            for a, b in intervals:
                if cut_right <= a or cut_left >= b:
                    next_intervals.append((a, b))
                    continue
                if cut_left > a:
                    next_intervals.append((a, cut_left))
                if cut_right < b:
                    next_intervals.append((cut_right, b))
            intervals = next_intervals if next_intervals else intervals

        if not intervals:
            return base_x, max(1, base_w)

        best = max(intervals, key=lambda p: p[1] - p[0])
        return best[0], max(1, best[1] - best[0])

    def _wrap_text_block(self, text: str, font, max_width: int, draw) -> List[str]:
        """Перенос текста с сохранением абзацев (переводов строк)."""
        lines: List[str] = []
        for paragraph in str(text).split('\n'):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            lines.extend(self._wrap_text(paragraph, font, max_width, draw))
        return lines
    
    def _draw_graphic_elements(self, draw, image=None):
        """Рисует графические элементы"""
        for element in self.graphic_elements:
            if not element.placed:
                continue
            
            x, y = element.x, element.y
            size = element.size_px
            
            if element.type == 'qr':
                # Рамка QR
                draw.rectangle([(x, y), (x + size, y + size)], fill='white', outline='black', width=1)
                
                # Узор DataMatrix
                cell_size = max(2, size // 10)
                for i in range(8):
                    for j in range(8):
                        if (i + j) % 2 == 0:
                            cx = x + i * cell_size + cell_size // 2
                            cy = y + j * cell_size + cell_size // 2
                            draw.rectangle(
                                [(cx - cell_size//2, cy - cell_size//2),
                                 (cx + cell_size//2, cy + cell_size//2)],
                                fill='black'
                            )
                
                font = self.get_font(max(6, size // 6))
                draw.text((x + 2, y + size - 16), "QR", fill='black', font=font)
            
            elif element.type in SYMBOL_ASSET_CANDIDATES:
                symbol_img = self._load_symbol_image(element.type, size)
                if symbol_img is not None and image is not None:
                    image.paste(symbol_img, (x, y), symbol_img)
                else:
                    draw.rectangle([(x, y), (x + size, y + size)], outline='#444444', width=1)
                    font = self.get_font(max(8, size // 3), bold=True)
                    draw.text((x + 2, y + max(1, size // 3)), element.type.upper(), fill='#222222', font=font)

    def _resolve_symbol_asset_path(self, symbol_type: str) -> Optional[str]:
        candidates = SYMBOL_ASSET_CANDIDATES.get(symbol_type, [])
        for name in candidates:
            path = os.path.join(SYMBOL_ASSET_DIR, name)
            if os.path.exists(path):
                return path
        return None

    def _load_symbol_image(self, symbol_type: str, target_size: int) -> Optional[Image.Image]:
        cache_key = f"{symbol_type}:{target_size}"
        if cache_key in self.symbol_image_cache:
            return self.symbol_image_cache[cache_key]

        asset_path = self._resolve_symbol_asset_path(symbol_type)
        if not asset_path:
            self.symbol_image_cache[cache_key] = None
            return None
        try:
            img = Image.open(asset_path).convert("RGBA")
            # Для ассетов с "черным фоном" автоматически делаем темные пиксели прозрачными.
            alpha = img.getchannel("A")
            if alpha.getextrema() == (255, 255):
                luminance = img.convert("RGB").convert("L")
                auto_alpha = luminance.point(lambda p: 0 if p < 16 else min(255, int((p - 16) * 1.4)))
                img.putalpha(auto_alpha)

            resampling = getattr(Image, 'Resampling', Image)
            resized = img.resize((target_size, target_size), resample=resampling.LANCZOS)
            self.symbol_image_cache[cache_key] = resized
            return resized
        except Exception:
            self.symbol_image_cache[cache_key] = None
            return None

    def _symbol_asset_data_uri(self, symbol_type: str) -> Optional[str]:
        asset_path = self._resolve_symbol_asset_path(symbol_type)
        if not asset_path:
            return None
        try:
            with open(asset_path, 'rb') as f:
                raw = f.read()
            b64 = base64.b64encode(raw).decode('ascii')
            return f"data:image/png;base64,{b64}"
        except Exception:
            return None
    
    def _wrap_text(self, text: str, font, max_width: int, draw) -> List[str]:
        """Перенос текста"""
        words = text.split()
        if not words:
            return []
        
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            if self._get_text_width(test_line, font, draw) <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Длинное слово
                    chars = []
                    for char in word:
                        test_word = ''.join(chars + [char])
                        if self._get_text_width(test_word, font, draw) <= max_width - 5:
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
    
    def _get_text_width(self, text: str, font, draw) -> int:
        """Получает ширину текста"""
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0]
        except:
            font_size = font.size
            is_bold = 'bold' in str(font).lower()
            return ArialMetrics.estimate_text_width(text, font_size, is_bold)


def extract_data_from_text(parsed_data: Dict) -> Dict:
    """Извлекает данные из распарсенного текста"""
    result = {}
    
    # Заголовок
    if parsed_data.get('product_full_name'):
        result['title'] = parsed_data['product_full_name']
    elif parsed_data.get('product_name'):
        result['title'] = parsed_data['product_name']
    
    # Основной текст
    description_parts = []
    
    if parsed_data.get('ingredients'):
        description_parts.append(f"Состав: {parsed_data['ingredients']}")
    
    if parsed_data.get('manufacturer'):
        description_parts.append(f"Производитель: {parsed_data['manufacturer']}")
    
    if parsed_data.get('importer'):
        description_parts.append(f"Импортер: {parsed_data['importer']}")
    
    if parsed_data.get('country_of_origin'):
        country_text = f"Страна: {parsed_data['country_of_origin']}"
        description_parts.append(country_text)
    
    result['description'] = "\n".join(description_parts)
    
    # Штрихкод
    if parsed_data.get('barcode'):
        result['barcode_data'] = parsed_data['barcode']
    else:
        result['barcode_data'] = "4600966003792"
    
    # Короткий код
    if parsed_data.get('batch_number'):
        result['short_code'] = parsed_data['batch_number']
    else:
        result['short_code'] = "5eBqWK"
    
    # Номер партии
    if parsed_data.get('batch_number'):
        result['batch_number'] = parsed_data['batch_number']
    
    # Срок годности
    if parsed_data.get('expiry_date'):
        result['expiry_date'] = parsed_data['expiry_date']
    
    # Иконки
    icons = []
    if parsed_data.get('requires_gost'):
        icons.append("ГОСТ")
    if parsed_data.get('is_recyclable'):
        icons.append("♻")
    
    if icons:
        result['icons'] = ' • '.join(icons)
    
    return result


def get_available_sizes() -> List[Dict]:
    """Возвращает список доступных размеров"""
    sizes = []
    for key, info in PREDEFINED_SIZES.items():
        width_mm = info['width_mm']
        height_mm = info['height_mm']
        sizes.append({
            'id': key,
            'name': f"{width_mm}x{height_mm} мм",
            'width_mm': width_mm,
            'height_mm': height_mm,
            'width_px': info['width_px'],
            'height_px': info['height_px']
        })
    return sizes


