"""
server.py - Главный сервер LabelFlow с интеграцией парсера
"""
import http.server
import socketserver
import json
import os
import sys
import time
import uuid
import mimetypes
import io
import base64
from urllib.parse import urlparse, unquote, quote
from pathlib import Path

# Добавляем текущую директорию в путь
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Импортируем наш модуль этикеток
try:
    from etoile_layout import EtoileLabelLayout, extract_data_from_text, get_available_sizes, PREDEFINED_SIZES
    print("✅ Модуль etoile_layout загружен")
except ImportError as e:
    print(f"❌ Ошибка импорта etoile_layout: {e}")
    sys.exit(1)

# Импортируем парсер
try:
    from product_parser import ProductInfoParser
    print("✅ Модуль product_parser загружен")
except ImportError as e:
    print(f"❌ Ошибка импорта product_parser: {e}")
    # Создаем заглушку если файл не найден
    class ProductInfoParser:
        def parse_text(self, text):
            return {'product_name': 'Товар', 'raw_text': text}
        def to_json(self, data):
            return json.dumps(data, ensure_ascii=False)

PORT = 8000
RENDER_SUPERSAMPLE = 4.0
PREVIEW_SUPERSAMPLE = 6.0

# Проверяем права на запись
output_dir = os.path.join(BASE_DIR, 'output')
try:
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    test_file = os.path.join(output_dir, 'test.txt')
    with open(test_file, 'w') as f:
        f.write('test')
    os.remove(test_file)
    print("✅ Права на запись есть")
except Exception as e:
    print(f"❌ Нет прав на запись: {e}")


class Handler(http.server.SimpleHTTPRequestHandler):
    
    def __init__(self, *args, **kwargs):
        self.base_path = BASE_DIR
        self.parser = ProductInfoParser()  # Инициализируем парсер
        super().__init__(*args, directory=self.base_path, **kwargs)
    
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")
    
    def do_GET(self):
        """Обработка GET запросов"""
        parsed_url = urlparse(self.path)
        request_path = unquote(parsed_url.path)
        print(f"📥 GET: {self.path} -> {request_path}")

        if request_path == '/' or request_path == '/index.html':
            self.serve_file('index.html', 'text/html')
            return
        
        elif request_path == '/api/status':
            self.send_json_response({
                'status': 'running',
                'version': '2.0',
                'message': 'LabelFlow API с парсером работает',
                'available_sizes': get_available_sizes(),
                'parser_loaded': True
            })
            return
        
        elif request_path.startswith('/output/'):
            filepath = os.path.join(BASE_DIR, request_path.lstrip('/'))
            print(f"🔍 Ищем файл: {filepath}")
            
            if os.path.exists(filepath):
                print(f"✅ Файл найден: {filepath}")
                self.serve_static_file(filepath)
                return
            else:
                print(f"❌ Файл не найден: {filepath}")
                self.send_error(404, f"File not found: {request_path}")
                return
        
        elif request_path == '/api/parser-info':
            self.send_json_response({
                'success': True,
                'parser_fields': [
                    'product_name', 'brand', 'description', 'features',
                    'ingredients', 'application', 'precautions', 'storage_conditions',
                    'manufacturer', 'importer', 'country', 'expiry_date',
                    'batch_number', 'article_number', 'barcode'
                ]
            })
            return
        
        filepath = os.path.join(BASE_DIR, request_path.lstrip('/'))
        if os.path.exists(filepath) and os.path.isfile(filepath):
            self.serve_static_file(filepath)
            return
        
        self.send_error(404, f"File not found: {request_path}")
    
    def do_POST(self):
        """Обработка POST запросов"""
        print(f"📥 POST: {self.path}")
        
        if self.path == '/api/generate':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                response = self._handle_generate(data)
                self.send_json_response(response)
                
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                import traceback
                traceback.print_exc()
                self.send_json_response({'error': str(e), 'success': False}, 500)
            return
        
        elif self.path == '/api/parse':
            """Отдельный эндпоинт для парсинга текста"""
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                text = data.get('text', '')
                if not text:
                    self.send_json_response({'error': 'Текст не передан', 'success': False}, 400)
                    return
                
                # Используем парсер
                parsed_data = self.parser.parse_text(text)
                
                # Добавляем мета-информацию
                response = {
                    'success': True,
                    'parsed_data': parsed_data,
                    'stats': {
                        'char_count': len(text),
                        'word_count': len(text.split()),
                        'line_count': len(text.split('\n'))
                    }
                }
                
                self.send_json_response(response)
                
            except Exception as e:
                print(f"❌ Ошибка парсинга: {e}")
                import traceback
                traceback.print_exc()
                self.send_json_response({'error': str(e), 'success': False}, 500)
            return
        
        elif self.path == '/api/sizes':
            self.send_json_response({
                'success': True,
                'sizes': get_available_sizes()
            })
            return
        
        else:
            self.send_error(404, f"Endpoint not found: {self.path}")
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _read_text_with_fallback(self, filepath):
        """Читает файл с попытками разных кодировок."""
        with open(filepath, 'rb') as f:
            raw = f.read()

        for encoding in ('utf-8-sig', 'utf-8', 'cp1251'):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        return raw.decode('utf-8', errors='replace')

    def serve_file(self, filename, content_type):
        filepath = os.path.join(BASE_DIR, filename)
        if os.path.exists(filepath):
            self.send_response(200)
            self.send_header('Content-type', f'{content_type}; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            text = self._read_text_with_fallback(filepath)
            self.wfile.write(text.encode('utf-8'))
        else:
            self.send_error(404, f"File not found: {filename}")
    
    def serve_static_file(self, filepath):
        if os.path.exists(filepath):
            self.send_response(200)
            content_type, _ = mimetypes.guess_type(filepath)
            self.send_header('Content-type', content_type or 'application/octet-stream')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            
            with open(filepath, 'rb') as f:
                file_content = f.read()
                print(f"📤 Отправляем файл: {filepath}, размер: {len(file_content)} байт")
                self.wfile.write(file_content)
        else:
            print(f"❌ Файл не найден при отправке: {filepath}")
            self.send_error(404, f"File not found: {filepath}")
    
    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def _handle_generate(self, data):
        """Генерация этикетки с использованием парсера"""
        user_text = data.get('text', '')
        size_id = self._normalize_size_id(data.get('size_id', '46x46'))
        preview_mode = data.get('preview_mode', False)
        output_format = str(data.get('format', 'png')).strip().lower()
        high_quality_png = bool(data.get('high_quality_png', False))
        qr_position = str(data.get('qr_position', 'auto')).strip().lower()
        symbols_position = str(data.get('symbols_position', 'auto')).strip().lower()
        graphic_symbols = data.get('graphic_symbols', [])
        symbol_positions = data.get('symbol_positions', {})
        title_size_multiplier = float(data.get('title_size_multiplier', 3.5))
        text_size_multiplier = float(data.get('text_size_multiplier', 1.0))
        if not isinstance(graphic_symbols, list):
            graphic_symbols = []
        if not isinstance(symbol_positions, dict):
            symbol_positions = {}
        symbol_positions = {str(k).strip().lower(): str(v).strip().lower() for k, v in symbol_positions.items()}
        if output_format not in {'png', 'svg'}:
            output_format = 'png'
        
        print(f"📝 Текст: {user_text[:50]}...")
        print(f"📏 Размер: {size_id}")
        print(f"👁 Режим: {'предпросмотр' if preview_mode else 'обычный'}")
        print(f"🧩 Формат: {output_format}")
        print(f"📌 QR position: {qr_position}, symbols: {symbols_position}, list={graphic_symbols}, symbol_positions={symbol_positions}")
        if output_format == 'png':
            print(f"🎯 PNG quality: {'HD' if high_quality_png else 'standard'}")
        
        if not user_text:
            return {'error': 'Текст не передан', 'success': False}
        
        try:
            # Используем парсер для извлечения данных
            parsed_data = self.parser.parse_text(user_text)
            
            # Конвертируем в формат для этикетки
            label_data = self._convert_parsed_to_label(parsed_data)
            label_data['qr_position'] = qr_position
            label_data['symbols_position'] = symbols_position
            label_data['graphic_symbols'] = graphic_symbols
            label_data['symbol_positions'] = symbol_positions
            label_data['title_size_multiplier'] = title_size_multiplier
            label_data['text_size_multiplier'] = text_size_multiplier
            
            # Для SVG не нужен supersampling (вектор масштабируется без потерь).
            # Для HD PNG увеличиваем реальное разрешение (без downscale), удобно для графредакторов.
            keep_target_size = True
            if output_format == 'svg':
                supersample = 1.0
            elif preview_mode:
                supersample = PREVIEW_SUPERSAMPLE
            elif high_quality_png:
                max_side_px = max(
                    PREDEFINED_SIZES[size_id]['width_px'],
                    PREDEFINED_SIZES[size_id]['height_px']
                )
                # Ограничиваем пиксельный размер по длинной стороне, чтобы не перегружать память.
                adaptive_supersample = min(8.0, 4200.0 / max(1, float(max_side_px)))
                supersample = max(RENDER_SUPERSAMPLE, adaptive_supersample)
                keep_target_size = False
            else:
                supersample = RENDER_SUPERSAMPLE
            layout = EtoileLabelLayout(
                size_key=size_id,
                supersample=supersample,
                keep_target_size=keep_target_size
            )
            image = None
            svg_content = None
            if output_format == 'svg':
                svg_content = layout.render_svg(label_data)
            else:
                image = layout.render(label_data)

            # Для предпросмотра не пишем файл на диск - отдаем data URL из памяти.
            preview_data_url = None
            filename = None
            if preview_mode:
                if output_format == 'svg':
                    svg_b64 = base64.b64encode(svg_content.encode('utf-8')).decode('ascii')
                    preview_data_url = f"data:image/svg+xml;base64,{svg_b64}"
                else:
                    buffer = io.BytesIO()
                    image.save(buffer, format='PNG', dpi=(300, 300))
                    image_b64 = base64.b64encode(buffer.getvalue()).decode('ascii')
                    preview_data_url = f"data:image/png;base64,{image_b64}"
                print("💾 Preview сформирован в памяти (без записи файла)")
            else:
                # Обычную генерацию сохраняем в output для скачивания/печати.
                output_dir = os.path.join(BASE_DIR, 'output')
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    print(f"📁 Создана папка: {output_dir}")

                filename = f"label_{size_id}.{output_format}"
                filepath = os.path.join(output_dir, filename)
                if output_format == 'svg':
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(svg_content)
                else:
                    png_dpi = 600 if high_quality_png else 300
                    image.save(filepath, dpi=(png_dpi, png_dpi), optimize=True)
                print(f"💾 Файл сохранен: {filepath}")

                if os.path.exists(filepath):
                    file_size = os.path.getsize(filepath)
                    print(f"✅ Файл подтвержден: {file_size} байт")
                else:
                    print(f"❌ Ошибка: файл не создан!")
            
            size_info = PREDEFINED_SIZES[size_id]
            variant = {
                'id': 1,
                'name': f"{size_info['width_mm']}x{size_info['height_mm']} мм",
                'size': f"{size_info['width_mm']} x {size_info['height_mm']} мм",
                'size_id': size_id,
                'width_mm': size_info['width_mm'],
                'height_mm': size_info['height_mm'],
                'width_px': size_info['width_px'],
                'height_px': size_info['height_px'],
                'actual_width_px': image.size[0] if image is not None else layout.target_width_px,
                'actual_height_px': image.size[1] if image is not None else layout.target_height_px,
                'image_url': f"/output/{quote(filename)}" if filename else None,
                'image_data_url': preview_data_url,
                'filename': filename,
                'format': output_format,
                'quality': 'hd' if (output_format == 'png' and high_quality_png) else 'standard',
                'qr_position': qr_position,
                'symbols_position': symbols_position,
                'graphic_symbols': graphic_symbols,
                'symbol_positions': symbol_positions,
                'features': self._get_features(size_id, parsed_data)
            }
            
            if preview_mode:
                print("✅ Предпросмотр создан (in-memory)")
            else:
                print(f"✅ Этикетка создана: {filename}")
                print(f"🔗 URL: /output/{filename}")
            
            return {
                'success': True,
                'product_name': parsed_data.get('product_name', 'Товар'),
                'parsed_data': parsed_data,
                'variants': [variant]
            }
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e), 'success': False}

    def _normalize_size_id(self, size_id):
        """Приводит входной size_id к поддерживаемому ключу."""
        if not size_id:
            return '46x46'

        size_id = str(size_id).strip()

        aliases = {
            '100x100': '99.5x99.5'
        }
        if size_id in aliases:
            size_id = aliases[size_id]

        if size_id not in PREDEFINED_SIZES:
            print(f"⚠️ Размер {size_id} не найден, используем 46x46")
            return '46x46'
        return size_id
    
    def _convert_parsed_to_label(self, parsed_data):
        """Конвертирует данные из парсера в формат для этикетки"""
        label_data = {}
        
        # Заголовок - используем структурированное название
        if parsed_data.get('product_name'):
            label_data['title'] = parsed_data['product_name']
        
        # Оригинальное название (английское)
        if parsed_data.get('original_name'):
            label_data['original_name'] = parsed_data['original_name']
        
        # Описание товара - используем структурированное описание
        if parsed_data.get('product_description'):
            label_data['description'] = parsed_data['product_description']
        else:
            # Фолбэк на старое описание
            description_parts = []
            
            if parsed_data.get('description'):
                description_parts.append(parsed_data['description'])

            if parsed_data.get('features'):
                for feature in parsed_data['features'][:5]:
                    clean_feature = str(feature).strip()
                    if clean_feature:
                        description_parts.append('- ' + clean_feature)

            if parsed_data.get('ingredients'):
                description_parts.append(f"Состав: {parsed_data['ingredients']}")
            
            if parsed_data.get('manufacturer'):
                description_parts.append(f"Произв: {parsed_data['manufacturer']}")

            if parsed_data.get('country'):
                description_parts.append(f"Страна: {parsed_data['country']}")

            if parsed_data.get('expiry_date'):
                description_parts.append(f"Годен до: {parsed_data['expiry_date']}")
            
            if description_parts:
                label_data['description'] = "\n".join(description_parts)
            else:
                # Если ничего не найдено, используем весь текст
                raw_text = str(parsed_data.get('raw_text') or '').strip()
                if raw_text:
                    label_data['description'] = raw_text
                    label_data['full_text_mode'] = True
        
        # Артикул
        if parsed_data.get('article_number'):
            label_data['article'] = str(parsed_data['article_number'])
        elif parsed_data.get('article'):
            label_data['article'] = parsed_data['article']
        
        # Штрихкод
        if parsed_data.get('barcode'):
            label_data['barcode_data'] = parsed_data['barcode']
        else:
            label_data['barcode_data'] = "4600966003792"
        
        # Короткий код
        if parsed_data.get('article_number'):
            label_data['short_code'] = str(parsed_data['article_number'])
        elif parsed_data.get('batch_number'):
            label_data['short_code'] = parsed_data['batch_number']
        else:
            label_data['short_code'] = "5eBqWK"
        
        # Номер партии
        if parsed_data.get('batch_number'):
            label_data['batch_number'] = parsed_data['batch_number']
        
        # Срок годности
        if parsed_data.get('expiry_date'):
            label_data['expiry_date'] = parsed_data['expiry_date']
        
        return label_data
    
    def _get_features(self, size_id, data):
        """Возвращает особенности этикетки"""
        features = []
        
        if size_id in {'17x15', '16x16', '20x15'}:
            return ['Только QR']

        size_info = PREDEFINED_SIZES.get(size_id, {})
        if size_info.get('width_mm', 0) >= 40:
            features.append('Полный текст')
        elif size_info.get('width_mm', 0) >= 20:
            features.append('Сжатый текст')
        else:
            features.append('Минимальный')
        
        return list(set(features))[:3]


def main():
    print("=" * 60)
    print("LabelFlow Server v2.0 с AI-парсером")
    print("=" * 60)
    
    # Проверяем и создаем папку output
    output_dir = os.path.join(BASE_DIR, 'output')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"📁 Создана папка: {output_dir}")
    else:
        print(f"📁 Папка output существует: {output_dir}")
    
    # Проверяем файлы
    required_files = ['index.html', 'product_parser.py', 'etoile_layout.py']
    for file in required_files:
        filepath = os.path.join(BASE_DIR, file)
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            print(f"✅ {file} ({file_size} байт)")
        else:
            print(f"⚠️ {file} - не найден")
    
    print(f"\n📁 Рабочая папка: {BASE_DIR}")
    print(f"🌐 http://localhost:{PORT}")
    print("=" * 60)
    
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"\n✅ Сервер запущен с парсером!")
            print(f"🌐 Откройте: http://localhost:{PORT}")
            print("📝 Эндпоинты:")
            print("   - GET  /api/status       - статус")
            print("   - POST /api/parse        - парсинг текста")
            print("   - POST /api/generate     - генерация этикетки")
            print("🛑 Ctrl+C для остановки")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Сервер остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
