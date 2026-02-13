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

# Получаем абсолютный путь к текущей директории
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"📁 Текущая директория: {BASE_DIR}")

# Добавляем текущую директорию в путь
sys.path.append(BASE_DIR)

# Импортируем ВСЕ функции генерации из label_generator
try:
    from label_generator import (
        ContentProcessor, 
        SizeCalculator, 
        LabelDesigner,
        parse_product_text,
        generate_label_image,
        slugify_filename,
        get_variant_features,
        check_label_compliance
    )
    print("✅ Модули label_generator загружены")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("ℹ️ Убедитесь, что label_generator.py находится в той же папке")
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
        
        # API эндпоинты
        elif self.path == '/api/status':
            self.send_json_response({
                'status': 'running',
                'version': '2.0',
                'timestamp': time.time(),
                'message': 'LabelFlow API работает'
            })
            return
        
        # ЭКСПОРТ ЭТИКЕТКИ
        elif self.path.startswith('/api/export/'):
            try:
                # Извлекаем ID варианта из URL
                path_parts = self.path.split('/')
                if len(path_parts) >= 4:
                    variant_id_str = path_parts[3].split('?')[0]
                    variant_id = int(variant_id_str)
                    self.handle_export(variant_id)
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
            filepath = os.path.join(BASE_DIR, self.path[1:].split('?')[0])
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
    
    # ========== ОБРАБОТЧИКИ API ==========
    
    def handle_generate(self, data):
        """Генерация этикеток - метаданные"""
        user_text = data.get('text', '')
        print(f"📝 Получен текст: {user_text[:50]}...")
        
        if not user_text:
            return {'error': 'No text provided', 'success': False}
        
        try:
            # Используем функцию парсинга из label_generator
            parsed_data = parse_product_text(user_text)
            
            variants = []
            sizes = [
                {'id': 1, 'name': 'Широкий формат', 'width': 16, 'height': 9},
                {'id': 2, 'name': 'Минимализм', 'width': 10, 'height': 7}
            ]
            
            for i, size in enumerate(sizes):
                variant = {
                    'id': size['id'],
                    'name': size['name'],
                    'size': f"{size['width']} × {size['height']} см",
                    'width': size['width'],
                    'height': size['height'],
                    'features': get_variant_features(size['name'], parsed_data)
                }
                variants.append(variant)
                print(f"✅ Создан вариант: {variant['name']}")
            
            return {
                'success': True,
                'product_name': parsed_data['product_name'],
                'variants': variants
            }
            
        except Exception as e:
            print(f"❌ Ошибка генерации: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e), 'success': False}
    
    def handle_export(self, variant_id):
        """Экспорт этикетки с ПОЛНЫМИ данными товара"""
        print(f"\n📤 ЭКСПОРТ ВАРИАНТА #{variant_id}")
        
        # Получаем данные товара из query параметров
        parsed_url = urlparse(self.path)
        query = parse_qs(parsed_url.query)
        
        # ========== ПОЛНЫЙ ПАРСИНГ ВСЕХ ПОЛЕЙ ==========
        product_data = {
            # ОСНОВНОЕ
            'product_name': self._get_query_param(query, 'product_name', 'Товар'),
            'product_full_name': self._get_query_param(query, 'product_full_name', ''),
            'product_subtitle': self._get_query_param(query, 'product_subtitle', ''),
            
            # СОСТАВ И ПИЩЕВАЯ ЦЕННОСТЬ
            'ingredients': self._get_query_param(query, 'ingredients', ''),
            'nutrition': self._get_query_param(query, 'nutrition', ''),
            'nutrition_facts': {},
            'energy_value': self._get_query_param(query, 'energy_value', ''),
            'energy_value_kj': self._get_query_param(query, 'energy_value_kj', ''),
            
            # ВЕС И ОБЪЕМ
            'net_weight': self._get_query_param(query, 'net_weight', ''),
            'volume': self._get_query_param(query, 'volume', ''),
            
            # СРОКИ И ДАТЫ
            'expiry_date': self._get_query_param(query, 'expiry_date', ''),
            'manufacture_date': self._get_query_param(query, 'manufacture_date', ''),
            'shelf_life': self._get_query_param(query, 'shelf_life', ''),
            'shelf_life_days': self._get_query_param(query, 'shelf_life_days', ''),
            'after_opening': self._get_query_param(query, 'after_opening', ''),
            
            # УСЛОВИЯ ХРАНЕНИЯ
            'storage_conditions': self._get_query_param(query, 'storage_conditions', ''),
            'storage_temp': self._get_query_param(query, 'storage_temp', ''),
            
            # ПРОИЗВОДИТЕЛЬ
            'manufacturer': self._get_query_param(query, 'manufacturer', ''),
            'manufacturer_address': self._get_query_param(query, 'manufacturer_address', ''),
            'manufacturer_full': self._get_query_param(query, 'manufacturer_full', ''),
            
            # ИМПОРТЕР
            'importer': self._get_query_param(query, 'importer', ''),
            'importer_address': self._get_query_param(query, 'importer_address', ''),
            'importer_full': self._get_query_param(query, 'importer_full', ''),
            
            # СТРАНА
            'country_of_origin': self._get_query_param(query, 'country_of_origin', 
                                                       self._get_query_param(query, 'country', '')),
            'country_code': self._get_query_param(query, 'country_code', ''),
            'customs_union': self._get_query_param(query, 'customs_union', 'false').lower() == 'true',
            'eaeu': self._get_query_param(query, 'eaeu', 'false').lower() == 'true',
            
            # СЕРТИФИКАЦИЯ
            'certification': self._get_query_param_list(query, 'certification'),
            'technical_regulations': self._get_query_param_list(query, 'technical_regulations'),
            'tr_codes': self._get_query_param_list(query, 'tr_codes'),
            
            # МАРКИРОВКА
            'barcode': self._get_query_param(query, 'barcode', ''),
            'ean13': self._get_query_param(query, 'ean13', ''),
            'requires_qr': self._get_query_param(query, 'qr_required', 'false').lower() == 'true',
            'qr_data': self._get_query_param(query, 'qr_data', 
                                             self._get_query_param(query, 'qr', '')),
            'honest_sign_barcode': self._get_query_param(query, 'honest_sign_barcode', ''),
            
            # ИКОНКИ И ЗНАКИ
            'is_recyclable': self._get_query_param(query, 'recycle', 'false').lower() == 'true',
            'recycle_code': self._get_query_param(query, 'recycle_code', ''),
            'requires_gost': self._get_query_param(query, 'gost', 'false').lower() == 'true',
            'gost_numbers': self._get_query_param_list(query, 'gost_numbers'),
            
            # ИНСТРУКЦИИ
            'usage_instructions': self._get_query_param(query, 'usage_instructions', ''),
            'dilution': self._get_query_param(query, 'dilution', ''),
            'preparation': self._get_query_param(query, 'preparation', ''),
            
            # ПРЕДУПРЕЖДЕНИЯ
            'warnings': self._get_query_param_list(query, 'warnings'),
            'allergens': self._get_query_param_list(query, 'allergens'),
            
            # ДОПОЛНИТЕЛЬНО
            'batch_number': self._get_query_param(query, 'batch_number', ''),
            'package_type': self._get_query_param(query, 'package_type', ''),
            'serving_size': self._get_query_param(query, 'serving_size', ''),
            'servings_per_package': self._get_query_param(query, 'servings_per_package', '')
        }
        
        # Декодируем URL-encoded строки
        for key, value in product_data.items():
            if isinstance(value, str):
                try:
                    product_data[key] = urllib.parse.unquote(value)
                except:
                    pass
            elif isinstance(value, list):
                decoded_list = []
                for item in value:
                    try:
                        decoded_list.append(urllib.parse.unquote(item))
                    except:
                        decoded_list.append(item)
                product_data[key] = decoded_list
        
        print(f"📦 ЭКСПОРТ ПОЛНЫХ ДАННЫХ:")
        print(f"   Товар: {product_data['product_name']}")
        print(f"   Состав: {product_data['ingredients'][:50] if product_data['ingredients'] else 'Н/Д'}...")
        print(f"   Производитель: {product_data['manufacturer'] or 'Н/Д'}")
        print(f"   Импортер: {product_data['importer'] or 'Н/Д'}")
        print(f"   Срок годности: {product_data['expiry_date'] or 'Н/Д'}")
        print(f"   QR: {product_data['requires_qr']}")
        print(f"   Переработка: {product_data['is_recyclable']}")
        print(f"   ГОСТ: {product_data['requires_gost']}")
        
        # Определяем размер этикетки по ID варианта
        sizes = {
            1: {'name': 'wide', 'display_name': 'Широкий формат', 'width': 16, 'height': 9},
            2: {'name': 'minimal', 'display_name': 'Минимализм', 'width': 10, 'height': 7}
        }
        
        size = sizes.get(variant_id, sizes[1])
        print(f"   Формат: {size['width']}x{size['height']} см ({size['display_name']})")
        
        try:
            # ВАЖНО: Передаем ВСЕ данные в генератор
            image = generate_label_image(product_data, size['width'], size['height'])
            
            # Сохраняем в BytesIO
            img_io = io.BytesIO()
            image.save(img_io, format='PNG', dpi=(300, 300))
            img_io.seek(0)
            
            # Создаем имя файла
            timestamp = int(time.time())
            safe_name = slugify_filename(product_data['product_name'] or 'product')
            filename = f"labelflow_{safe_name}_{timestamp}.png"
            
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            
            self.wfile.write(img_io.getvalue())
            print(f"✅ УСПЕШНО экспортирован: {filename}")
            print(f"   Размер файла: {len(img_io.getvalue())} байт")
            
        except Exception as e:
            print(f"❌ Ошибка экспорта: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Export failed: {str(e)}")
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    
    def _get_query_param(self, query, key, default=''):
        """Безопасное получение параметра из query"""
        if key in query and query[key] and len(query[key]) > 0:
            return query[key][0]
        return default
    
    def _get_query_param_list(self, query, key):
        """Получение списка параметров из query"""
        if key in query and query[key]:
            # Разделяем по | если это закодированный список
            if len(query[key]) == 1 and '|' in query[key][0]:
                return query[key][0].split('|')
            return query[key]
        return []

# Запуск сервера
def main():
    print("=" * 70)
    print("🚀 LabelFlow Server v2.0 - ПОЛНАЯ ИНФОРМАЦИЯ")
    print("=" * 70)
    print("✅ Файлы сохраняются ТОЛЬКО при экспорте")
    print("✅ Поддерживаются ЛЮБЫЕ товары")
    print("✅ Полный парсинг состава, сроков, производителей")
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
    # ВАЖНО: Здесь ТОЛЬКО вызов main() без argparse!
    main()