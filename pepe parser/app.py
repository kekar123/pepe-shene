from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
from flask_cors import CORS
import os
import json
from werkzeug.utils import secure_filename
from pathlib import Path
from excel_parser import xls_to_json_single
from analyzer import perform_abc_xyz_analysis
import pandas as pd

# =============== ДОПОЛНЕНИЯ ДЛЯ БАЗЫ ДАННЫХ ===============
import sys

# Добавляем путь к корню проекта для импорта модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from db.database import db
    from services.data_loader import JSONToDBLoader
    DB_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Модули БД не найдены: {e}")
    DB_AVAILABLE = False
# ==========================================================

app = Flask(__name__, 
            static_folder='pepe parser/static',
            template_folder='pepe parser/templates')
CORS(app)

# =============== ИНИЦИАЛИЗАЦИЯ БД ===============
if DB_AVAILABLE:
    try:
        db.connect()
        print("✅ База данных подключена")
    except Exception as e:
        print(f"⚠️  Не удалось подключиться к БД: {e}")
# ================================================

# Конфигурация
UPLOAD_FOLDER = 'uploads'
OUTPUT_JSON_FOLDER = 'output_json'
ANALYSIS_RESULTS_FOLDER = 'analysis_results'
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

for folder in [UPLOAD_FOLDER, OUTPUT_JSON_FOLDER, ANALYSIS_RESULTS_FOLDER]:
    Path(folder).mkdir(exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 МБ

def allowed_file(filename):
    """Проверка расширения файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Главная страница с формой"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Обработка загрузки файла"""
    try:
        
        if 'file' not in request.files:
            return jsonify({'error': 'Файл не найден в запросе'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'Файл не выбран'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Разрешены только файлы Excel (.xls, .xlsx)'}), 400
        
        # Сохраняем файл
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Парсим Excel в JSON
        json_result = xls_to_json_single(
            input_file=filepath,
            output_folder=OUTPUT_JSON_FOLDER
        )
        
        if not json_result:
            return jsonify({'error': 'Ошибка при парсинге файла'}), 500
        
        # Выполняем ABC-XYZ анализ
        analysis_result = perform_abc_xyz_analysis(
            json_file_path=json_result['output'],
            output_file_name=f"{Path(filename).stem}_analysis.json"
        )
        
        if not analysis_result:
            return jsonify({'error': 'Ошибка при выполнении анализа'}), 500
        
        # =============== ЗАГРУЗКА В БАЗУ ДАННЫХ ===============
        db_info = {
            'loaded': False,
            'store_items': 0,
            'analysis_items': 0,
            'errors': []
        }
        
        if DB_AVAILABLE:
            try:
                loader = JSONToDBLoader()
                db_result = loader.load_from_json(analysis_result)
                db_info = {
                    'loaded': True,
                    'store_items': db_result.get('store_inserted', 0),
                    'analysis_items': db_result.get('analysis_inserted', 0),
                    'errors': db_result.get('errors', [])
                }
            except Exception as db_error:
                db_info['errors'] = [str(db_error)]
        # ======================================================
        
        # Читаем результаты анализа
        with open(analysis_result, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
        
        # Подсчитываем статистику
        abc_stats = {}
        xyz_stats = {}
        abc_xyz_stats = {}
        
        for item in analysis_data:
            abc_stats[item['ABC']] = abc_stats.get(item['ABC'], 0) + 1
            xyz_stats[item['XYZ']] = xyz_stats.get(item['XYZ'], 0) + 1
            abc_xyz_stats[item['ABC_XYZ']] = abc_xyz_stats.get(item['ABC_XYZ'], 0) + 1
        
        return jsonify({
            'success': True,
            'message': f'Файл "{filename}" успешно обработан',
            'original_file': filename,
            'json_file': json_result['file_name'],
            'analysis_file': Path(analysis_result).name,
            'db_info': db_info,  # ДОБАВЛЕНО
            'stats': {
                'total_items': len(analysis_data),
                'abc_distribution': abc_stats,
                'xyz_distribution': xyz_stats,
                'abc_xyz_matrix': abc_xyz_stats
            },
            'download_links': {
                'json': f'/download/{OUTPUT_JSON_FOLDER}/{json_result["file_name"]}',
                'analysis': f'/download/{ANALYSIS_RESULTS_FOLDER}/{Path(analysis_result).name}'
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reorder-warehouse', methods=['POST'])
def reorder_warehouse():
    """Обработка пересортировки склада"""
    try:
        # Здесь будет логика пересортировки
        # Пока что имитация
        
        return jsonify({
            'success': True,
            'message': 'Пересортировка склада успешно завершена',
            'details': {
                'optimized_positions': 150,
                'saved_space': '15%',
                'estimated_efficiency_gain': '25%'
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<folder>/<filename>')
def download_file(folder, filename):
    """Скачивание обработанных файлов"""
    return send_from_directory(folder, filename, as_attachment=True)

@app.route('/files')
def list_files():
    """Получение списка обработанных файлов"""
    files = []
    
    # Собираем JSON файлы
    json_folder = Path(OUTPUT_JSON_FOLDER)
    if json_folder.exists():
        for json_file in json_folder.glob('*.json'):
            analysis_file = Path(ANALYSIS_RESULTS_FOLDER) / f"{json_file.stem}_analysis.json"
            files.append({
                'name': json_file.name,
                'type': 'json',
                'size': json_file.stat().st_size,
                'has_analysis': analysis_file.exists(),
                'download_url': f'/download/{OUTPUT_JSON_FOLDER}/{json_file.name}'
            })
    
    # Собираем файлы анализа
    analysis_folder = Path(ANALYSIS_RESULTS_FOLDER)
    if analysis_folder.exists():
        for analysis_file in analysis_folder.glob('*_analysis.json'):
            files.append({
                'name': analysis_file.name,
                'type': 'analysis',
                'size': analysis_file.stat().st_size,
                'download_url': f'/download/{ANALYSIS_RESULTS_FOLDER}/{analysis_file.name}'
            })
    
    return jsonify({'files': files})

# =============== НОВЫЕ ЭНДПОИНТЫ ДЛЯ БАЗЫ ДАННЫХ ===============
@app.route('/api/load-to-db', methods=['POST'])
def load_json_to_db():
    """API для загрузки JSON файла в базу данных"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    try:
        data = request.json
        if not data or 'file_path' not in data:
            return jsonify({'success': False, 'error': 'Не указан путь к файлу'}), 400
        
        json_file_path = data['file_path']
        
        # Проверяем существование файла
        if not os.path.exists(json_file_path):
            # Пробуем найти в папке output_json
            possible_paths = [
                json_file_path,
                os.path.join(OUTPUT_JSON_FOLDER, os.path.basename(json_file_path)),
                os.path.join('output_json', os.path.basename(json_file_path)),
                os.path.join(parent_dir, 'output_json', os.path.basename(json_file_path))
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    json_file_path = path
                    break
            else:
                return jsonify({'success': False, 'error': f'Файл не найден: {data["file_path"]}'}), 404
        
        # Загружаем данные в БД
        loader = JSONToDBLoader()
        result = loader.load_from_json(json_file_path)
        
        return jsonify({
            'success': True,
            'message': 'Данные успешно загружены в БД',
            'result': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/store', methods=['GET'])
def get_store_items():
    """API для получения товаров со склада из БД"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    try:
        session = db.get_session()
        from db.models import Store
        
        items = session.query(Store).all()
        
        result = []
        for item in items:
            result.append({
                'id': item.id,
                'product_name': item.product_name,
                'revenue': float(item.revenue) if item.revenue else 0,
                'created_at': item.created_at.isoformat() if item.created_at else None
            })
        
        session.close()
        return jsonify({
            'success': True,
            'count': len(result),
            'data': result
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analysis', methods=['GET'])
def get_analysis():
    """API для получения результатов анализа из БД"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    try:
        session = db.get_session()
        from db.models import Analysis
        
        analyses = session.query(Analysis).all()
        
        result = []
        for analysis in analyses:
            result.append({
                'id': analysis.id,
                'product_name': analysis.product_name,
                'abc_category': analysis.abc_category,
                'xyz_category': analysis.xyz_category,
                'abc_xyz_category': analysis.abc_xyz_category,
                'revenue': float(analysis.revenue) if analysis.revenue else 0,
                'analysis_date': analysis.analysis_date.isoformat() if analysis.analysis_date else None
            })
        
        session.close()
        return jsonify({
            'success': True,
            'count': len(result),
            'data': result
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
# ================================================================

# =============== УПРОЩЕННЫЙ СПОСОБ ОБСЛУЖИВАНИЯ СТАТИЧЕСКИХ ФАЙЛОВ ===============
@app.route('/static/<path:filename>')
def serve_static(filename):
    """Сервис для статических файлов"""
    return send_from_directory(app.static_folder, filename)

# Альтернативные маршруты для обратной совместимости
@app.route('/styles.css')
def serve_styles():
    """Прямой доступ к CSS"""
    try:
        return send_file(os.path.join(app.static_folder, 'css', 'styles.css'), mimetype='text/css')
    except FileNotFoundError:
        return "CSS file not found", 404

@app.route('/script.js')
def serve_script():
    """Прямой доступ к JS"""
    try:
        return send_file(os.path.join(app.static_folder, 'js', 'script.js'), mimetype='application/javascript')
    except FileNotFoundError:
        return "JavaScript file not found", 404

# Маршрут для любых статических файлов (резервный)
@app.route('/<path:filename>')
def serve_any(filename):
    """Сервис для любых файлов в статической папке"""
    if filename.endswith('.css'):
        return send_from_directory(app.static_folder, filename, mimetype='text/css')
    elif filename.endswith('.js'):
        return send_from_directory(app.static_folder, filename, mimetype='application/javascript')
    else:
        return "File not found", 404
# ================================================================

if __name__ == '__main__':
    print("🚀 Запуск сервера...")
    print(f"📁 Текущая директория: {os.getcwd()}")
    print(f"📁 Папка шаблонов: {app.template_folder}")
    print(f"📁 Папка статики: {app.static_folder}")
    
    # Проверяем существование папок и файлов
    print("\n🔍 Проверка файлов:")
    
    # Проверяем папку templates
    if not os.path.exists('templates'):
        print("⚠️  Папка templates не существует! Создаю...")
        os.makedirs('templates')
    else:
        print("✅ Папка templates существует")
    
    # Проверяем index.html
    if os.path.exists('templates/index.html'):
        print("✅ Файл templates/index.html существует")
    else:
        print("❌ Файл templates/index.html не найден!")
        print("   Убедитесь, что form4.html переименован в index.html и находится в папке templates/")
    
    # Проверяем папку static
    if not os.path.exists('static'):
        print("⚠️  Папка static не существует! Создаю...")
        os.makedirs('static')
        os.makedirs('static/css')
        os.makedirs('static/js')
    else:
        print("✅ Папка static существует")
        
        if os.path.exists('static/css'):
            print("✅ Папка static/css существует")
        else:
            print("⚠️  Папка static/css не существует! Создаю...")
            os.makedirs('static/css')
            
        if os.path.exists('static/js'):
            print("✅ Папка static/js существует")
        else:
            print("⚠️  Папка static/js не существует! Создаю...")
            os.makedirs('static/js')
    
    # Проверяем CSS файл
    css_path = os.path.join('static', 'css', 'styles.css')
    if os.path.exists(css_path):
        print(f"✅ CSS файл найден: {css_path}")
    else:
        print(f"❌ CSS файл не найден: {css_path}")
        print("   Создаю простой CSS файл...")
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write("/* Basic CSS */\nbody { font-family: Arial, sans-serif; }")
    
    # Проверяем JS файл
    js_path = os.path.join('static', 'js', 'script.js')
    if os.path.exists(js_path):
        print(f"✅ JS файл найден: {js_path}")
    else:
        print(f"❌ JS файл не найден: {js_path}")
        print("   Создаю простой JS файл...")
        with open(js_path, 'w', encoding='utf-8') as f:
            f.write("// Basic JavaScript\nconsole.log('Script loaded');")
    
    print("\n🌐 Сервер запущен: http://localhost:5000")
    app.run(debug=True, port=5000, host='0.0.0.0')