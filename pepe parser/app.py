from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from pathlib import Path
from excel_parser import xls_to_json_single
from analyzer import perform_abc_xyz_analysis
import pandas as pd
from sqlalchemy import func
from db.models import Analysis 

# =============== ДОПОЛНЕНИЯ ДЛЯ БАЗЫ ДАННЫХ ===============
import sys
import os

# Добавляем путь к корню проекта для импорта модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)  # Добавляем текущую директорию

try:
    from db.database import db
    
    from services.data_loader import JSONToDBLoader
    DB_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Модули БД не найдены: {e}")
    DB_AVAILABLE = False

# =============== ДОПОЛНЕНИЯ ДЛЯ ГРАФИКОВ ===============
try:
    from chart_generator import ChartGenerator
    CHARTS_AVAILABLE = True
    print("✅ ChartGenerator загружен")
except ImportError as e:
    print(f"⚠️  ChartGenerator не найден: {e}")
    print("⚠️  Графики не будут работать. Убедитесь что файл chart_generator.py в корне проекта.")
    ChartGenerator = None
    CHARTS_AVAILABLE = False
# ========================================================

app = Flask(__name__)
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
    return render_template('form4.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Обработка загрузки файла с автоматической генерацией графиков"""
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
        
        # =============== АВТОМАТИЧЕСКАЯ ГЕНЕРАЦИЯ ГРАФИКОВ ===============
        charts_info = {
            'generated': False,
            'count': 0,
            'errors': []
        }
        
        if DB_AVAILABLE and CHARTS_AVAILABLE and db_info['loaded']:
            try:
                session = db.get_session()
                generator = ChartGenerator(session)
                charts = generator.generate_all_charts()
                session.close()
                
                if charts:
                    charts_info = {
                        'generated': True,
                        'count': len(charts),
                        'charts': charts
                    }
                    print(f"✅ Автоматически сгенерировано {len(charts)} графиков")
            except Exception as chart_error:
                print(f"⚠️  Ошибка генерации графиков: {chart_error}")
                charts_info['errors'] = [str(chart_error)]
        # =================================================================
        
        response_data = {
            'success': True,
            'message': f'Файл "{filename}" успешно обработан',
            'original_file': filename,
            'json_file': json_result['file_name'],
            'analysis_file': Path(analysis_result).name,
            'db_info': db_info,
            'charts_info': charts_info,  # Добавляем информацию о графиках
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
        }
        
        return jsonify(response_data)
        
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

# =============== НОВЫЕ ЭНДПОИНТЫ ДЛЯ ГРАФИКОВ ===============
@app.route('/api/charts', methods=['GET'])
def get_charts():
    """API для получения всех графиков с отладочной информацией"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    if not CHARTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Модуль графиков не доступен'}), 500
    
    try:
        session = db.get_session()
        from db.models import Analysis
        
        # Проверяем количество записей и распределение по категориям
        total_count = session.query(Analysis).count()
        abc_count = session.query(Analysis).filter(Analysis.abc_category.isnot(None)).count()
        xyz_count = session.query(Analysis).filter(Analysis.xyz_category.isnot(None)).count()
        
        print(f"📊 Статистика БД для графиков:")
        print(f"   • Всего записей: {total_count}")
        print(f"   • С ABC категорией: {abc_count}")
        print(f"   • С XYZ категорией: {xyz_count}")
        
        if total_count == 0:
            session.close()
            return jsonify({
                'success': False,
                'error': 'В базе данных нет данных. Сначала загрузите Excel файл через форму.',
                'db_stats': {
                    'total': 0,
                    'with_abc': 0,
                    'with_xyz': 0
                }
            }), 404
        
        generator = ChartGenerator(session)
        charts = generator.generate_all_charts()
        
        session.close()
        
        if charts:
            return jsonify({
                'success': True,
                'count': len(charts),
                'charts': charts,
                'db_stats': {
                    'total': total_count,
                    'with_abc': abc_count,
                    'with_xyz': xyz_count
                },
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Не удалось создать графики (проверьте данные в БД)',
                'db_stats': {
                    'total': total_count,
                    'with_abc': abc_count,
                    'with_xyz': xyz_count
                }
            }), 404
        
    except Exception as e:
        print(f"❌ Критическая ошибка генерации графиков: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chart/<chart_type>')
def get_specific_chart(chart_type):
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    if not CHARTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Модуль графиков не доступен'}), 500
    
    try:
        session = db.get_session()
        generator = ChartGenerator(session)
        
        chart_map = {
            'abc_pie': generator.create_abc_pie_chart,
            'xyz_bar': generator.create_xyz_bar_chart,
            'abc_xyz_matrix': generator.create_abc_xyz_matrix,
            'top_products': generator.create_top_products_chart,
            'category_comparison': generator.create_category_comparison
        }
        
        if chart_type not in chart_map:
            session.close()
            return jsonify({'success': False, 'error': 'Неизвестный тип графика'}), 400
        
        chart_data = chart_map[chart_type]()
        session.close()
        
        if chart_data:
            return jsonify({
                'success': True,
                'chart_type': chart_type,
                'image': chart_data,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Не удалось создать график (нет данных)'
            }), 404
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats')
def get_basic_stats():
    """Основная статистика для дашборда"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    try:
        session = db.get_session()
        
        # Общая статистика
        total_items = session.query(func.count('*')).select_from(db.models.Analysis).scalar() or 0
        
        # Получаем сумму выручки
        revenue_result = session.query(func.sum(db.models.Analysis.revenue)).scalar()
        total_revenue = float(revenue_result) if revenue_result else 0
        
        # Статистика по категориям ABC
        abc_stats_query = session.query(
            db.models.Analysis.abc_category,
            func.count(db.models.Analysis.id).label('count'),
            func.sum(db.models.Analysis.revenue).label('total_revenue')
        ).filter(db.models.Analysis.abc_category.isnot(None)).group_by(db.models.Analysis.abc_category)
        
        abc_stats = abc_stats_query.all()
        
        # Статистика по категориям XYZ
        xyz_stats_query = session.query(
            db.models.Analysis.xyz_category,
            func.count(db.models.Analysis.id).label('count'),
            func.sum(db.models.Analysis.revenue).label('total_revenue')
        ).filter(db.models.Analysis.xyz_category.isnot(None)).group_by(db.models.Analysis.xyz_category)
        
        xyz_stats = xyz_stats_query.all()
        
        # Топ 5 товаров
        top_products = session.query(
            db.models.Analysis.product_name,
            db.models.Analysis.revenue,
            db.models.Analysis.abc_xyz_category
        ).order_by(db.models.Analysis.revenue.desc()).limit(5).all()
        
        session.close()
        
        # Форматируем результаты ABC
        abc_data = {}
        for cat, count, revenue in abc_stats:
            if cat:
                abc_data[cat] = {
                    'count': count,
                    'revenue': float(revenue) if revenue else 0,
                    'percentage': (float(revenue) / total_revenue * 100) if total_revenue > 0 else 0
                }
        
        # Форматируем результаты XYZ
        xyz_data = {}
        for cat, count, revenue in xyz_stats:
            if cat:
                xyz_data[cat] = {
                    'count': count,
                    'revenue': float(revenue) if revenue else 0
                }
        
        # Форматируем топ товаров
        top_products_data = []
        for name, revenue, category in top_products:
            top_products_data.append({
                'name': name,
                'revenue': float(revenue) if revenue else 0,
                'category': category or ''
            })
        
        # Информация о последнем обновлении
        last_update_file = Path(ANALYSIS_RESULTS_FOLDER)
        last_update = None
        if last_update_file.exists():
            analysis_files = list(last_update_file.glob('*_analysis.json'))
            if analysis_files:
                last_file = max(analysis_files, key=lambda f: f.stat().st_mtime)
                last_update = datetime.fromtimestamp(last_file.stat().st_mtime).isoformat()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_items': total_items,
                'total_revenue': total_revenue,
                'average_revenue': total_revenue / total_items if total_items > 0 else 0,
                'abc_distribution': abc_data,
                'xyz_distribution': xyz_data,
                'top_products': top_products_data,
                'last_update': last_update or datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analysis-data')
def get_analysis_data():
    """API для получения данных анализа из БД в формате для таблицы"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    try:
        session = db.get_session()
        
        # Получаем все записи анализа
        analyses = session.query(
            db.models.Analysis.id,
            db.models.Analysis.product_name,
            db.models.Analysis.revenue,
            db.models.Analysis.abc_category,
            db.models.Analysis.xyz_category,
            db.models.Analysis.abc_xyz_category,
            db.models.Analysis.analysis_date
        ).order_by(db.models.Analysis.revenue.desc()).all()
        
        session.close()
        
        result = []
        for analysis in analyses:
            result.append({
                'id': analysis.id,
                'name': analysis.product_name,
                'revenue': float(analysis.revenue) if analysis.revenue else 0,
                'ABC': analysis.abc_category or '',
                'XYZ': analysis.xyz_category or '',
                'ABC_XYZ': analysis.abc_xyz_category or '',
                'analysis_date': analysis.analysis_date.isoformat() if analysis.analysis_date else None
            })
        
        return jsonify({
            'success': True,
            'count': len(result),
            'data': result
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения данных анализа: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/check-data')
def check_data():
    """Проверка наличия данных в БД"""
    if not DB_AVAILABLE:
        return jsonify({'has_data': False, 'error': 'База данных не доступна'}), 500
    
    try:
        session = db.get_session()
        from db.models import Analysis
        count = session.query(Analysis).count()
        session.close()
        
        return jsonify({
            'has_data': count > 0,
            'count': count,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'has_data': False, 'error': str(e)}), 500

@app.route('/api/test-charts')
def test_charts():
    """Тестовый эндпоинт для проверки генерации графиков"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    if not CHARTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'ChartGenerator не доступен'}), 500
    
    try:
        session = db.get_session()
        
        # Проверяем, есть ли данные
        from db.models import Analysis
        count = session.query(Analysis).count()
        
        if count == 0:
            session.close()
            return jsonify({
                'success': False,
                'error': 'В БД нет данных. Сначала загрузите Excel файл.'
            }), 404
        
        # Создаем тестовый график
        generator = ChartGenerator(session)
        test_chart = generator.create_abc_pie_chart()
        
        session.close()
        
        if test_chart:
            return jsonify({
                'success': True,
                'message': f'В БД найдено {count} записей. Графики могут быть сгенерированы.',
                'test_chart_length': len(test_chart)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Не удалось создать тестовый график',
                'db_records': count
            }), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/system-status')
def system_status():
    """Проверка статуса системы"""
    status = {
        'database': DB_AVAILABLE,
        'charts': CHARTS_AVAILABLE,
        'upload_folder': os.path.exists(UPLOAD_FOLDER),
        'analysis_folder': os.path.exists(ANALYSIS_RESULTS_FOLDER),
        'total_analysis_files': len(list(Path(ANALYSIS_RESULTS_FOLDER).glob('*.json'))),
        'timestamp': datetime.now().isoformat()
    }
    
    if DB_AVAILABLE:
        try:
            session = db.get_session()
            from db.models import Analysis
            status['db_records'] = session.query(Analysis).count()
            session.close()
        except:
            status['db_records'] = 'error'
    
    return jsonify(status)

# =============== СТАРЫЕ ЭНДПОИНТЫ ДЛЯ БАЗЫ ДАННЫХ ===============
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
                'store_id': analysis.store_id,
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
# ===============================================================

# =============== ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ ===============
@app.route('/health')
def health_check():
    """Проверка работоспособности сервера"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'ABC/XYZ Analyzer API',
        'version': '2.0'
    })

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """Очистка кэша (для разработки)"""
    try:
        # Здесь можно добавить логику очистки кэша
        return jsonify({
            'success': True,
            'message': 'Кэш очищен',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export-data', methods=['GET'])
def export_data():
    """Экспорт данных в формате CSV"""
    try:
        # Получаем данные из БД
        if DB_AVAILABLE:
            session = db.get_session()
            from db.models import Analysis
            
            analyses = session.query(Analysis).all()
            
            # Создаем DataFrame
            data = []
            for analysis in analyses:
                data.append({
                    'ID': analysis.id,
                    'Название товара': analysis.product_name,
                    'Выручка': float(analysis.revenue) if analysis.revenue else 0,
                    'ABC категория': analysis.abc_category,
                    'XYZ категория': analysis.xyz_category,
                    'ABC-XYZ матрица': analysis.abc_xyz_category,
                    'Дата анализа': analysis.analysis_date.isoformat() if analysis.analysis_date else ''
                })
            
            session.close()
            
            df = pd.DataFrame(data)
            
            # Сохраняем во временный файл
            export_path = Path(ANALYSIS_RESULTS_FOLDER) / f'export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            df.to_csv(export_path, index=False, encoding='utf-8-sig')
            
            return send_from_directory(
                ANALYSIS_RESULTS_FOLDER,
                export_path.name,
                as_attachment=True,
                mimetype='text/csv'
            )
        else:
            return jsonify({'success': False, 'error': 'БД не доступна'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get-latest-analysis')
def get_latest_analysis():
    """Получение последнего файла анализа"""
    try:
        analysis_folder = Path(ANALYSIS_RESULTS_FOLDER)
        if not analysis_folder.exists():
            return jsonify({'success': False, 'error': 'Папка с анализами не найдена'}), 404
        
        analysis_files = list(analysis_folder.glob('*_analysis.json'))
        if not analysis_files:
            return jsonify({'success': False, 'error': 'Файлы анализа не найдены'}), 404
        
        # Берем самый новый файл
        latest_file = max(analysis_files, key=lambda f: f.stat().st_mtime)
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
        
        return jsonify({
            'success': True,
            'file': latest_file.name,
            'data': analysis_data,
            'timestamp': datetime.fromtimestamp(latest_file.stat().st_mtime).isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auto-load-charts')
def auto_load_charts():
    """Автоматическая загрузка графиков на основе последних данных"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    if not CHARTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Модуль графиков не доступен'}), 500
    
    try:
        session = db.get_session()
        from db.models import Analysis
        
        # Проверяем, есть ли данные
        count = session.query(Analysis).count()
        if count == 0:
            session.close()
            return jsonify({
                'success': False,
                'error': 'В БД нет данных. Сначала загрузите Excel файл.'
            }), 404
        
        # Генерируем графики
        generator = ChartGenerator(session)
        charts = generator.generate_all_charts()
        session.close()
        
        if charts:
            return jsonify({
                'success': True,
                'message': f'Сгенерировано {len(charts)} графиков',
                'count': len(charts),
                'charts': charts,
                'db_records': count,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Не удалось сгенерировать графики',
                'db_records': count
            }), 500
            
    except Exception as e:
        print(f"❌ Ошибка автоматической загрузки графиков: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    

    # Отладочные эндпоинты
@app.route('/api/debug-matrix')
def debug_matrix():
    """Отладочный эндпоинт для проверки данных матрицы"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    try:
        session = db.get_session()
        from db.models import Analysis
        
        # Получаем все записи для отладки
        analyses = session.query(
            Analysis.id,
            Analysis.product_name,
            Analysis.abc_category,
            Analysis.xyz_category,
            Analysis.revenue
        ).all()
        
        debug_info = []
        for a in analyses:
            debug_info.append({
                'id': a.id,
                'name': a.product_name,
                'abc': a.abc_category,
                'xyz': a.xyz_category,
                'revenue': float(a.revenue) if a.revenue else 0
            })
        
        # Статистика по категориям
        abc_stats = {}
        xyz_stats = {}
        
        for item in debug_info:
            abc = item['abc']
            xyz = item['xyz']
            
            if abc:
                abc_stats[abc] = abc_stats.get(abc, 0) + 1
            if xyz:
                xyz_stats[xyz] = xyz_stats.get(xyz, 0) + 1
        
        session.close()
        
        return jsonify({
            'success': True,
            'total_records': len(debug_info),
            'abc_stats': abc_stats,
            'xyz_stats': xyz_stats,
            'data': debug_info[:20]  # Первые 20 записей
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/debug/matrix-only')
def debug_matrix_only():
    """Только матрица для отладки"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    if not CHARTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'Модуль графиков не доступен'}), 500
    
    try:
        session = db.get_session()
        generator = ChartGenerator(session)
        
        # Генерируем только матрицу
        matrix_chart = generator.create_abc_xyz_matrix()
        
        session.close()
        
        if matrix_chart:
            return jsonify({
                'success': True,
                'chart': matrix_chart,
                'length': len(matrix_chart),
                'message': 'Матрица сгенерирована'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Не удалось создать матрицу'
            }), 404
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
# ======================================================

# =============== ОБРАБОТКА ОШИБОК ===============
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Ресурс не найден'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Внутренняя ошибка сервера'}), 500

@app.errorhandler(413)
def too_large(error):
    return jsonify({'error': 'Файл слишком большой (макс. 10 МБ)'}), 413
# ===============================================

@app.route('/api/analysis-data')
def get_analysis_data():
    """API для получения данных анализа из БД в формате для таблицы"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных не доступна'}), 500
    
    try:
        session = db.get_session()
        
        # Получаем все записи анализа
        analyses = session.query(
            Analysis.id,
            Analysis.product_name,
            Analysis.revenue,
            Analysis.abc_category,
            Analysis.xyz_category,
            Analysis.abc_xyz_category,
            Analysis.analysis_date
        ).order_by(Analysis.revenue.desc()).all()
        
        session.close()
        
        result = []
        for analysis in analyses:
            result.append({
                'id': analysis.id,
                'name': analysis.product_name,
                'revenue': float(analysis.revenue) if analysis.revenue else 0,
                'ABC': analysis.abc_category or '',
                'XYZ': analysis.xyz_category or '',
                'ABC_XYZ': analysis.abc_xyz_category or '',
                'analysis_date': analysis.analysis_date.isoformat() if analysis.analysis_date else None
            })
        
        return jsonify({
            'success': True,
            'count': len(result),
            'data': result
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения данных анализа: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Вывод информации о системе при запуске
    print("=" * 60)
    print("🚀 ABC/XYZ Analyzer API v2.0 запускается...")
    print(f"📁 Рабочая директория: {os.getcwd()}")
    print(f"📊 База данных: {'✅ Доступна' if DB_AVAILABLE else '❌ Не доступна'}")
    print(f"📈 Графики: {'✅ Доступны' if CHARTS_AVAILABLE else '❌ Не доступны'}")
    print(f"📂 Папка загрузок: {UPLOAD_FOLDER} ({'✅ Существует' if os.path.exists(UPLOAD_FOLDER) else '❌ Не существует'})")
    print(f"📂 Папка результатов: {ANALYSIS_RESULTS_FOLDER} ({'✅ Существует' if os.path.exists(ANALYSIS_RESULTS_FOLDER) else '❌ Не существует'})")
    print(f"🌐 Сервер запустится по адресу: http://localhost:5000")
    print("=" * 60)
    print("🔧 Доступные эндпоинты:")
    print("   • /                    - Главная страница")
    print("   • /upload              - Загрузка файла")
    print("   • /api/charts          - Все графики")
    print("   • /api/stats           - Статистика")
    print("   • /api/analysis-data   - Данные для таблицы")
    print("   • /api/system-status   - Статус системы")
    print("   • /health              - Проверка здоровья")
    print("=" * 60)
    
    app.run(debug=True, port=5000, host='0.0.0.0')

