import http.server
import socketserver
import json
import os
import sys
from pathlib import Path
import mimetypes
import time
import io
import urllib.parse
from urllib.parse import urlparse, parse_qs
import re

# Получаем абсолютный путь к текущей директории
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"📁 Текущая директория: {BASE_DIR}")

# Добавляем текущую директорию в путь
sys.path.insert(0, BASE_DIR)

# Импортируем ТОЛЬКО нужные функции из label_generator
try:
    from label_generator import (
        parse_product_text,
        generate_label_image,
        slugify_filename
    )
    print("✅ Модули label_generator загружены")
    print(f"   - parse_product_text")
    print(f"   - generate_label_image")
    print(f"   - slugify_filename")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print(f"🔍 Поиск в: {BASE_DIR}")
    print("📋 Содержимое папки:")
    for file in os.listdir(BASE_DIR):
        print(f"   - {file}")
    sys.exit(1)

PORT = 8000

class Handler(http.server.SimpleHTTPRequestHandler):
    
    def __init__(self, *args, **kwargs):
        self.base_path = BASE_DIR
        super().__init__(*args, directory=self.base_path, **kwargs)
    
    def log_message(self, format, *args):
        """Кастомное логирование"""
        print(f"[{self.log_date_time_string()}] {format % args}")
    
    def do_GET(self):
        """Обработка GET запросов"""
        print(f"📥 GET запрос: {self.path}")
        
        # Главная страница
        if self.path == '/' or self.path.startswith('/index.html'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', 'Mon, 01 Jan 1990 00:00:00 GMT')
            self.end_headers()
            
            filepath = os.path.join(BASE_DIR, 'index.html')
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Добавляем мета-теги для отключения кэширования
                meta_tags = '''
                <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
                <meta http-equiv="Pragma" content="no-cache">
                <meta http-equiv="Expires" content="0">
                '''
                
                if '<head>' in content:
                    content = content.replace('<head>', '<head>' + meta_tags)
                
                self.wfile.write(content.encode('utf-8'))
                print(f"✅ Отдан index.html")
            except FileNotFoundError:
                self.send_error(404, "index.html not found")
            return
        
        # API статус
        elif self.path == '/api/status':
            self.send_json_response({
                'status': 'running',
                'version': '3.0',
                'timestamp': time.time(),
                'message': 'LabelFlow API работает'
            })
            return
        
        # ЭКСПОРТ ЭТИКЕТКИ
        elif self.path.startswith('/api/export/custom'):
            try:
                self.handle_custom_export()
            except Exception as e:
                print(f"❌ Ошибка экспорта: {e}")
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Export failed: {str(e)}")
            return
        
        # ЭКСПОРТ ПО ID
        elif self.path.startswith('/api/export/'):
            try:
                path_parts = self.path.split('/')
                if len(path_parts) >= 4:
                    variant_id_str = path_parts[3].split('?')[0]
                    if variant_id_str.isdigit():
                        variant_id = int(variant_id_str)
                        self.handle_export_by_id(variant_id)
                    else:
                        self.handle_custom_export()
                else:
                    self.send_error(400, "Invalid export URL")
            except Exception as e:
                print(f"❌ Ошибка экспорта: {e}")
                import traceback
                traceback.print_exc()
                self.send_error(500, f"Export failed: {str(e)}")
            return
        
        # Статические файлы
        else:
            file_path = self.path.split('?')[0].lstrip('/')
            filepath = os.path.join(BASE_DIR, file_path)
            
            if os.path.exists(filepath) and os.path.isfile(filepath):
                self.serve_static_file(filepath)
                return
        
        self.send_error(404, f"File not found: {self.path}")
    
    def do_POST(self):
        """Обработка POST запросов"""
        print(f"📥 POST запрос: {self.path}")
        
        if self.path == '/api/generate':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                response = self.handle_generate(data)
                self.send_json_response(response)
                
            except Exception as e:
                print(f"❌ Ошибка обработки POST: {e}")
                import traceback
                traceback.print_exc()
                self.send_json_response({'error': str(e), 'success': False}, 500)
            return
        
        else:
            self.send_error(404, f"Endpoint not found: {self.path}")
    
    def do_OPTIONS(self):
        """Обработка CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.end_headers()
    
    def serve_static_file(self, filepath):
        """Отдает статические файлы"""
        if os.path.exists(filepath) and os.path.isfile(filepath):
            self.send_response(200)
            mime_type = mimetypes.guess_type(filepath)[0] or 'application/octet-stream'
            self.send_header('Content-type', mime_type)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, f"File not found: {filepath}")
    
    def send_json_response(self, data, status=200):
        """Отправляет JSON ответ"""
        self.send_response(status)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    # ========== ОБРАБОТЧИК ЭКСПОРТА ==========
    
    def handle_custom_export(self):
        """Экспорт этикетки с пользовательскими размерами"""
        print(f"\n📤 ЭКСПОРТ ПОЛЬЗОВАТЕЛЬСКОЙ ЭТИКЕТКИ")
        print("=" * 50)
        
        # Получаем данные из query параметров
        parsed_url = urlparse(self.path)
        query = parse_qs(parsed_url.query)
        
        print("📋 ПОЛУЧЕННЫЕ ПАРАМЕТРЫ:")
        for key in query:
            value = query[key][0]
            if len(value) > 100:
                print(f"   {key}: {value[:100]}...")
            else:
                print(f"   {key}: {value}")
        print("=" * 50)
        
        # Проверяем, это предпросмотр или скачивание
        is_preview = self._get_query_param(query, 'preview', 'false').lower() == 'true'
        
        # Получаем данные напрямую из параметров
        product_data = {
            'product_name': self._get_query_param(query, 'product_name', 'Товар'),
            'product_full_name': self._get_query_param(query, 'product_full_name', ''),
            'ingredients': self._get_query_param(query, 'ingredients', ''),
            'country_of_origin': self._get_query_param(query, 'country', ''),
            'net_weight': self._get_query_param(query, 'net_weight', ''),
            'manufacturer': self._get_query_param(query, 'manufacturer', ''),
            'importer': self._get_query_param(query, 'importer', ''),
            'barcode': self._get_query_param(query, 'barcode', ''),
            'requires_qr': self._get_query_param(query, 'requires_qr', 'false').lower() == 'true',
            'requires_gost': self._get_query_param(query, 'requires_gost', 'false').lower() == 'true',
            'is_recyclable': self._get_query_param(query, 'is_recyclable', 'false').lower() == 'true',
            'nutrition': self._get_query_param(query, 'nutrition', ''),
            'energy_value': self._get_query_param(query, 'energy', ''),
            'shelf_life': self._get_query_param(query, 'shelf_life', ''),
            'expiry_date': self._get_query_param(query, 'expiry', '')
        }
        
        # Декодируем URL-encoded строки
        for key, value in product_data.items():
            if isinstance(value, str):
                try:
                    product_data[key] = urllib.parse.unquote(value)
                except:
                    pass
        
        # Получаем размеры (в СМ)
        try:
            width_cm = float(self._get_query_param(query, 'width', '46'))
            height_cm = float(self._get_query_param(query, 'height', '46'))
        except ValueError:
            width_cm = 46
            height_cm = 46
        
        # Получаем номер дизайна
        design_id = int(self._get_query_param(query, 'design', '0'))
        
        print(f"\n📦 ДАННЫЕ ДЛЯ ГЕНЕРАЦИИ:")
        print(f"   product_name: {product_data.get('product_name', 'Н/Д')}")
        print(f"   ingredients: {product_data.get('ingredients', 'Н/Д')[:50]}")
        print(f"   country_of_origin: {product_data.get('country_of_origin', 'Н/Д')}")
        print(f"   net_weight: {product_data.get('net_weight', 'Н/Д')}")
        print(f"   manufacturer: {product_data.get('manufacturer', 'Н/Д')}")
        print(f"   importer: {product_data.get('importer', 'Н/Д')}")
        print(f"   barcode: {product_data.get('barcode', 'Н/Д')}")
        print(f"   Размер: {width_cm}×{height_cm} см")
        print("=" * 50)
        
        try:
            # Генерируем этикетку
            image = generate_label_image(product_data, width_cm, height_cm)
            
            # Сохраняем в BytesIO
            img_io = io.BytesIO()
            
            # Для предпросмотра используем меньшее качество
            if is_preview:
                image.save(img_io, format='PNG', dpi=(72, 72), optimize=True)
            else:
                image.save(img_io, format='PNG', dpi=(300, 300))
            
            img_io.seek(0)
            
            if is_preview:
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'public, max-age=30')
                self.end_headers()
            else:
                timestamp = int(time.time())
                safe_name = slugify_filename(product_data.get('product_name', 'product'))
                filename = f"labelflow_{safe_name}_{int(width_cm)}x{int(height_cm)}_cm_{timestamp}.png"
                
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
            
            self.wfile.write(img_io.getvalue())
            
            if is_preview:
                print(f"✅ Отправлен предпросмотр для дизайна #{design_id}")
            else:
                print(f"✅ УСПЕШНО экспортирован: {filename}")
            
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Export failed: {str(e)}")
    
    def handle_export_by_id(self, variant_id):
        """Экспорт этикетки по ID"""
        print(f"\n📤 ЭКСПОРТ ВАРИАНТА #{variant_id}")
        
        parsed_url = urlparse(self.path)
        query = parse_qs(parsed_url.query)
        
        is_preview = self._get_query_param(query, 'preview', 'false').lower() == 'true'
        
        product_data = {
            'product_name': self._get_query_param(query, 'product_name', 'Товар'),
            'product_full_name': self._get_query_param(query, 'product_full_name', ''),
            'ingredients': self._get_query_param(query, 'ingredients', ''),
            'country_of_origin': self._get_query_param(query, 'country', ''),
            'net_weight': self._get_query_param(query, 'net_weight', ''),
            'manufacturer': self._get_query_param(query, 'manufacturer', ''),
            'importer': self._get_query_param(query, 'importer', ''),
            'requires_qr': self._get_query_param(query, 'requires_qr', 'false').lower() == 'true',
            'requires_gost': self._get_query_param(query, 'requires_gost', 'false').lower() == 'true',
            'is_recyclable': self._get_query_param(query, 'is_recyclable', 'false').lower() == 'true'
        }
        
        # Размеры для старых вариантов (в СМ)
        sizes = {
            0: {'width': 46, 'height': 46},
            1: {'width': 48, 'height': 30},
            2: {'width': 40, 'height': 20},
            3: {'width': 30, 'height': 15},
            4: {'width': 43, 'height': 63},
            5: {'width': 22, 'height': 22},
            6: {'width': 99.5, 'height': 99.5},
            7: {'width': 20, 'height': 15},
            8: {'width': 17, 'height': 15},
            9: {'width': 16, 'height': 16},
            10: {'width': 58, 'height': 60},
            11: {'width': 40, 'height': 15},
            12: {'width': 55, 'height': 60},
            13: {'width': 50, 'height': 70}
        }
        
        size = sizes.get(variant_id, sizes[0])
        
        for key, value in product_data.items():
            if isinstance(value, str):
                try:
                    product_data[key] = urllib.parse.unquote(value)
                except:
                    pass
        
        try:
            image = generate_label_image(product_data, size['width'], size['height'])
            
            img_io = io.BytesIO()
            
            if is_preview:
                image.save(img_io, format='PNG', dpi=(72, 72), optimize=True)
            else:
                image.save(img_io, format='PNG', dpi=(300, 300))
            
            img_io.seek(0)
            
            if is_preview:
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'public, max-age=30')
                self.end_headers()
            else:
                timestamp = int(time.time())
                safe_name = slugify_filename(product_data.get('product_name', 'product'))
                filename = f"labelflow_{safe_name}_{size['width']}x{size['height']}_cm_{timestamp}.png"
                
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
            
            self.wfile.write(img_io.getvalue())
            print(f"✅ УСПЕШНО экспортирован вариант #{variant_id}")
            
        except Exception as e:
            print(f"❌ Ошибка экспорта: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Export failed: {str(e)}")
    
    def handle_generate(self, data):
        """Генерация метаданных для предпросмотра"""
        user_text = data.get('text', '')
        print(f"📝 Получен текст для парсинга: {user_text[:100]}...")
        
        if not user_text:
            return {'error': 'No text provided', 'success': False}
        
        try:
            parsed_data = parse_product_text(user_text)
            
            return {
                'success': True,
                'product_name': parsed_data.get('product_name', 'Товар'),
                'product_full_name': parsed_data.get('product_full_name', ''),
                'ingredients': parsed_data.get('ingredients', ''),
                'has_qr': parsed_data.get('requires_qr', False),
                'has_recycle': parsed_data.get('is_recyclable', False),
                'has_gost': parsed_data.get('requires_gost', False)
            }
            
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e), 'success': False}
    
    def _get_query_param(self, query, key, default=''):
        """Безопасное получение параметра из query"""
        if key in query and query[key] and len(query[key]) > 0:
            return query[key][0]
        return default


def main():
    print("=" * 70)
    print("🚀 LabelFlow Server v3.0 - ИСПРАВЛЕННАЯ ВЕРСИЯ")
    print("=" * 70)
    print(f"📁 Папка проекта: {BASE_DIR}")
    print(f"🌐 Сервер: http://localhost:{PORT}")
    print("=" * 70)
    
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"\n✅ Сервер запущен!")
            print(f"🌐 Откройте: http://localhost:{PORT}")
            print("🛑 Нажмите Ctrl+C для остановки")
            print("-" * 70)
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Сервер остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка запуска сервера: {e}")

if __name__ == '__main__':
    main()