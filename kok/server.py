from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
from datetime import datetime
import uuid
import glob

app = Flask(__name__, static_folder='.')
CORS(app)

# Создаем необходимые папки
UPLOAD_FOLDER = 'uploads'
SAVED_FOLDER = 'saved'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SAVED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

# Автоматически находим HTML файл в папке
html_files = glob.glob('*.html')
if html_files:
    DEFAULT_HTML = html_files[0]  # Берем первый HTML файл
    print(f"📄 Найден HTML файл: {DEFAULT_HTML}")
else:
    DEFAULT_HTML = 'label_editor_fixed.html'
    print("⚠️ HTML файл не найден, используется имя по умолчанию")

# Главная страница
@app.route('/')
def index():
    return send_from_directory('.', DEFAULT_HTML)

# API для сохранения этикетки
@app.route('/api/save-label', methods=['POST'])
def save_label():
    try:
        data = request.json
        filename = data.get('filename', f'label_{uuid.uuid4()}.json')
        
        # Убеждаемся, что filename безопасен
        filename = os.path.basename(filename)
        
        filepath = os.path.join(SAVED_FOLDER, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data.get('data', {}), f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True, 
            'path': filepath,
            'message': 'Файл успешно сохранен'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API для загрузки этикетки
@app.route('/api/upload-label', methods=['POST'])
def upload_label():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'Файл не загружен'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Имя файла пустое'}), 400
        
        if not file.filename.endswith('.json'):
            return jsonify({'success': False, 'error': 'Файл должен быть в формате JSON'}), 400
        
        # Сохраняем файл временно
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Читаем содержимое
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Удаляем временный файл
        os.remove(filepath)
        
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API для списка сохраненных этикеток
@app.route('/api/labels', methods=['GET'])
def get_labels():
    try:
        labels = []
        for filename in os.listdir(SAVED_FOLDER):
            if filename.endswith('.json'):
                filepath = os.path.join(SAVED_FOLDER, filename)
                stat = os.stat(filepath)
                labels.append({
                    'name': filename,
                    'path': filename,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'size': stat.st_size
                })
        
        # Сортируем по дате изменения (новые сверху)
        labels.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify({'success': True, 'labels': labels})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API для загрузки конкретной этикетки
@app.route('/api/labels/<path:filename>', methods=['GET'])
def get_label(filename):
    try:
        # Защита от path traversal
        filename = os.path.basename(filename)
        filepath = os.path.join(SAVED_FOLDER, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'Файл не найден'}), 404
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# API для удаления этикетки
@app.route('/api/labels/<path:filename>', methods=['DELETE'])
def delete_label(filename):
    try:
        filename = os.path.basename(filename)
        filepath = os.path.join(SAVED_FOLDER, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'success': True, 'message': 'Файл удален'})
        else:
            return jsonify({'success': False, 'error': 'Файл не найден'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Статические файлы
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Сервер запущен!")
    print(f"📁 Рабочая папка: {os.getcwd()}")
    print(f"📄 HTML файл: {DEFAULT_HTML}")
    print(f"📂 Папка для сохранений: {SAVED_FOLDER}")
    print("=" * 50)
    print("🌐 Откройте в браузере: http://localhost:8001")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=8001)