from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os
import json
from werkzeug.utils import secure_filename
from pathlib import Path
from parser import xls_to_json_single
from analyzer import perform_abc_xyz_analysis
import pandas as pd

app = Flask(__name__)
CORS(app)

# Конфигурация
UPLOAD_FOLDER = 'uploads'
OUTPUT_JSON_FOLDER = 'output_json'
ANALYSIS_RESULTS_FOLDER = 'analysis_results'
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

# Создаем необходимые папки
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
    """Обработка загрузки файла"""
    try:
        # Проверяем наличие файла в запросе
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)