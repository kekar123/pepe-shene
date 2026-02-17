# -*- coding: utf-8 -*-
import sys
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

import os

import json

from datetime import datetime
from werkzeug.utils import secure_filename
import re
import math

from pathlib import Path

from excel_parser import xls_to_json_single

from analyzer import perform_abc_xyz_analysis
from combined_report import generate_combined_report

import pandas as pd

from sqlalchemy import func, or_, text

import sqlite3
try:
    from services.chat_assistant import WarehouseChatAssistant
    CHAT_ASSISTANT_AVAILABLE = True
except Exception:
    WarehouseChatAssistant = None
    CHAT_ASSISTANT_AVAILABLE = False

# Ensure UTF-8 output in console (Windows)
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


# =============== Р вЂќР С›Р СџР С›Р вЂєР СњР вЂўР СњР В�Р Р‡ Р вЂќР вЂєР Р‡ Р вЂ�Р С’Р вЂ”Р В« Р вЂќР С’Р СњР СњР В«Р Тђ ===============

import sys



# Р вЂќР С•Р В±Р В°Р Р†Р В»РЎРЏР ВµР С� Р С—РЎС“РЎвЂљРЎРЉ Р С” Р С”Р С•РЎР‚Р Р…РЎР‹ Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР В° Р Т‘Р В»РЎРЏ Р С‘Р С�Р С—Р С•РЎР‚РЎвЂљР В° Р С�Р С•Р Т‘РЎС“Р В»Р ВµР в„–

BASE_DIR = Path(__file__).resolve().parent

PARENT_DIR = BASE_DIR.parent

sys.path.insert(0, str(BASE_DIR))

sys.path.insert(0, str(PARENT_DIR))



ANALYSIS_RESULTS_DIR = BASE_DIR / "analysis_results"

ANALYSIS_RESULTS_DIR.mkdir(exist_ok=True, parents=True)



try:

    from db.database import db

    from services.data_loader import JSONToDBLoader

    DB_AVAILABLE = True

except ImportError as e:


    DB_AVAILABLE = False



# =============== Р СњР С›Р вЂ™Р В«Р в„ў Р вЂ”Р С’Р вЂњР В Р Р€Р вЂ”Р В§Р В�Р С™ Р вЂќР вЂєР Р‡ Р С’Р СњР С’Р вЂєР В�Р вЂ”Р С’ ===============

try:

    from analysis_db_loader import AnalysisDBLoader

    ANALYSIS_DB_AVAILABLE = True

    print("INFO: AnalysisDBLoader loaded")
except ImportError as e:

    print(f"WARNING: AnalysisDBLoader not found: {e}")
    ANALYSIS_DB_AVAILABLE = False

    AnalysisDBLoader = None

analysis_db = None



# =============== Р вЂќР С›Р СџР С›Р вЂєР СњР вЂўР СњР В�Р Р‡ Р вЂќР вЂєР Р‡ Р вЂњР В Р С’Р В¤Р В�Р С™Р С›Р вЂ™ ===============

try:

    from chart_generator import ChartGenerator

    CHARTS_AVAILABLE = True

    print("INFO: ChartGenerator loaded")
except ImportError as e:

    print(f"WARNING: ChartGenerator not found: {e}")

    ChartGenerator = None

    CHARTS_AVAILABLE = False

# ========================================================



app = Flask(__name__)

CORS(app)



@app.after_request

def force_utf8(response):

    content_type = response.headers.get('Content-Type', '')

    if 'text/html' in content_type or 'application/json' in content_type:

        response.headers['Content-Type'] = content_type.split(';')[0] + '; charset=utf-8'

    return response



def try_load_latest_analysis_into_db():

    if not ANALYSIS_DB_AVAILABLE or analysis_db is None:

        return {'loaded': False, 'error': 'analysis_db_not_available'}



    analysis_files = sorted(

        ANALYSIS_RESULTS_DIR.glob('*_analysis.json'),

        key=lambda p: p.stat().st_mtime,

        reverse=True

    )



    if not analysis_files:

        return {'loaded': False, 'error': 'no_analysis_files'}



    latest_file = analysis_files[0]

    try:

        result = analysis_db.load_analysis_from_json(

            analysis_file_path=str(latest_file),

            analysis_type="abc_xyz"

        )

        return {

            'loaded': bool(result.get('success')),

            'file': str(latest_file),

            'result': result

        }

    except Exception as e:

        return {'loaded': False, 'error': str(e)}



# =============== Р В�Р СњР В�Р В¦Р В�Р С’Р вЂєР В�Р вЂ”Р С’Р В¦Р В�Р Р‡ Р вЂ�Р С’Р вЂ” Р вЂќР С’Р СњР СњР В«Р Тђ ===============

if DB_AVAILABLE:

    try:

        db.connect()


    except Exception as e:
        pass




if ANALYSIS_DB_AVAILABLE:

    try:

        analysis_db = AnalysisDBLoader(str(ANALYSIS_RESULTS_DIR / "analysis_visualization.db"))


    except Exception as e:
        pass


        ANALYSIS_DB_AVAILABLE = False

# ========================================================

chat_assistant = None
if CHAT_ASSISTANT_AVAILABLE:
    try:
        main_db_path = (BASE_DIR.parent / "pepe_database.db").resolve()
        secondary_db_path = (BASE_DIR.parent / "analysis_visualization.db").resolve()
        analysis_results_db_path = (BASE_DIR / "analysis_results" / "analysis_visualization.db").resolve()
        chat_assistant = WarehouseChatAssistant(
            main_db_path,
            extra_db_paths=[secondary_db_path, analysis_results_db_path],
        )
    except Exception:
        chat_assistant = None



# Р С™Р С•Р Р…РЎвЂћР С‘Р С–РЎС“РЎР‚Р В°РЎвЂ Р С‘РЎРЏ

UPLOAD_FOLDER = 'uploads'

OUTPUT_JSON_FOLDER = 'output_json'

ANALYSIS_RESULTS_FOLDER = 'analysis_results'

ALLOWED_EXTENSIONS = {'xls', 'xlsx'}



UPLOAD_DIR = BASE_DIR / UPLOAD_FOLDER

OUTPUT_JSON_DIR = BASE_DIR / OUTPUT_JSON_FOLDER

ANALYSIS_RESULTS_DIR = BASE_DIR / ANALYSIS_RESULTS_FOLDER



for folder in [UPLOAD_DIR, OUTPUT_JSON_DIR, ANALYSIS_RESULTS_DIR]:

    folder.mkdir(exist_ok=True, parents=True)



app.config['UPLOAD_FOLDER'] = str(UPLOAD_DIR)

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 Р СљР вЂ�



def allowed_file(filename):

    """Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р В° РЎР‚Р В°РЎРѓРЎв‚¬Р С‘РЎР‚Р ВµР Р…Р С‘РЎРЏ РЎвЂћР В°Р в„–Р В»Р В°"""

    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@app.route('/')

def index():

    """Р вЂњР В»Р В°Р Р†Р Р…Р В°РЎРЏ РЎРѓРЎвЂљРЎР‚Р В°Р Р…Р С‘РЎвЂ Р В° РЎРѓ РЎвЂћР С•РЎР‚Р С�Р С•Р в„–"""

    return render_template('form4.html')

@app.route('/combined')
def combined_page():
    return render_template('combined.html')



@app.route('/remove')

def remove_page():

    return render_template('remove.html')



@app.route('/upload', methods=['POST'])

def upload_file():

    """Р С›Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р В° Р В·Р В°Р С–РЎР‚РЎС“Р В·Р С”Р С‘ РЎвЂћР В°Р в„–Р В»Р В° РЎРѓ Р В°Р Р†РЎвЂљР С•Р С�Р В°РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С•Р в„– Р С–Р ВµР Р…Р ВµРЎР‚Р В°РЎвЂ Р С‘Р ВµР в„– Р С–РЎР‚Р В°РЎвЂћР С‘Р С”Р С•Р Р† Р С‘ РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…Р ВµР Р…Р С‘Р ВµР С� Р Р† Р вЂ�Р вЂќ"""

    try:

        if 'file' not in request.files:

            return jsonify({'error': 'Р В¤Р В°Р в„–Р В» Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р… Р Р† Р В·Р В°Р С—РЎР‚Р С•РЎРѓР Вµ'}), 400

        

        file = request.files['file']

        

        if file.filename == '':

            return jsonify({'error': 'Р В¤Р В°Р в„–Р В» Р Р…Р Вµ Р Р†РЎвЂ№Р В±РЎР‚Р В°Р Р…'}), 400

        

        if not allowed_file(file.filename):

            return jsonify({'error': 'Р В Р В°Р В·РЎР‚Р ВµРЎв‚¬Р ВµР Р…РЎвЂ№ РЎвЂљР С•Р В»РЎРЉР С”Р С• РЎвЂћР В°Р в„–Р В»РЎвЂ№ Excel (.xls, .xlsx)'}), 400

        

        # Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎРЏР ВµР С� РЎвЂћР В°Р в„–Р В»

        filename = secure_filename(file.filename)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        file.save(filepath)

        

        # Р СџР В°РЎР‚РЎРѓР С‘Р С� Excel Р Р† JSON

        json_result = xls_to_json_single(

            input_file=filepath,

            output_folder=str(OUTPUT_JSON_DIR)

        )

        

        if not json_result:

            return jsonify({'error': 'Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—РЎР‚Р С‘ Р С—Р В°РЎР‚РЎРѓР С‘Р Р…Р С–Р Вµ РЎвЂћР В°Р в„–Р В»Р В°'}), 500

        

        # Р вЂ™РЎвЂ№Р С—Р С•Р В»Р Р…РЎРЏР ВµР С� ABC-XYZ Р В°Р Р…Р В°Р В»Р С‘Р В·

        analysis_data = perform_abc_xyz_analysis(

            json_file_path=json_result['output'],

            output_file_name=f"{Path(filename).stem}_analysis.json"

        )

        

        if not analysis_data:

            return jsonify({'error': 'Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—РЎР‚Р С‘ Р Р†РЎвЂ№Р С—Р С•Р В»Р Р…Р ВµР Р…Р С‘Р С‘ Р В°Р Р…Р В°Р В»Р С‘Р В·Р В°'}), 500

        

        # =============== Р РЋР С›Р ТђР В Р С’Р СњР вЂўР СњР В�Р вЂў Р С’Р СњР С’Р вЂєР В�Р вЂ”Р С’ Р вЂ™ Р вЂ�Р вЂќ Р вЂќР вЂєР Р‡ Р вЂњР В Р С’Р В¤Р В�Р С™Р С›Р вЂ™ ===============

        db_info = {

            'loaded': False,

            'analysis_id': None,

            'products_count': 0,

            'errors': []

        }

        

        if ANALYSIS_DB_AVAILABLE:

            try:

                # Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎРЏР ВµР С� Р Р†РЎР‚Р ВµР С�Р ВµР Р…Р Р…РЎвЂ№Р в„– JSON РЎвЂћР В°Р в„–Р В» РЎРѓ РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљР В°Р С�Р С‘ Р В°Р Р…Р В°Р В»Р С‘Р В·Р В°

                import tempfile

                import json

                

                # Р РЋР С•Р В·Р Т‘Р В°Р ВµР С� Р Р†РЎР‚Р ВµР С�Р ВµР Р…Р Р…РЎвЂ№Р в„– РЎвЂћР В°Р в„–Р В» РЎРѓ РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљР В°Р С�Р С‘ Р В°Р Р…Р В°Р В»Р С‘Р В·Р В°

                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:

                    json.dump(analysis_data, temp_file, ensure_ascii=False, indent=2)

                    temp_file_path = temp_file.name

                

                # Р вЂ”Р В°Р С–РЎР‚РЎС“Р В¶Р В°Р ВµР С� Р В°Р Р…Р В°Р В»Р С‘Р В· Р Р† Р вЂ�Р вЂќ

                db_result = analysis_db.load_analysis_from_json(

                    analysis_file_path=temp_file_path,

                    analysis_type="abc_xyz"

                )

                

                # Р Р€Р Т‘Р В°Р В»РЎРЏР ВµР С� Р Р†РЎР‚Р ВµР С�Р ВµР Р…Р Р…РЎвЂ№Р в„– РЎвЂћР В°Р в„–Р В»

                os.unlink(temp_file_path)

                

                if db_result['success']:

                    db_info = {

                        'loaded': True,

                        'analysis_id': db_result['analysis_file_id'],

                        'products_count': db_result.get('products_loaded', 0),

                        'analysis_data_count': db_result.get('analysis_data_loaded', 0),

                        'errors': db_result.get('errors', [])

                    }

                    


                else:

                    db_info['errors'] = db_result.get('errors', ['Р СњР ВµР С‘Р В·Р Р†Р ВµРЎРѓРЎвЂљР Р…Р В°РЎРЏ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°'])

                    

            except Exception as db_error:


                import traceback

                traceback.print_exc()

                db_info['errors'] = [str(db_error)]

        # ======================================================================

        

        # =============== Р вЂ”Р С’Р вЂњР В Р Р€Р вЂ”Р С™Р С’ Р вЂ™ Р С›Р РЋР СњР С›Р вЂ™Р СњР Р€Р В® Р вЂ�Р С’Р вЂ”Р Р€ Р вЂќР С’Р СњР СњР В«Р Тђ ===============

        main_db_info = {

            'loaded': False,

            'store_items': 0,

            'analysis_items': 0,

            'errors': []

        }

        

        if DB_AVAILABLE:

            try:

                # Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎРЏР ВµР С� РЎвЂљР В°Р С”Р В¶Р Вµ Р Р† Р С•РЎРѓР Р…Р С•Р Р†Р Р…РЎС“РЎР‹ Р вЂ�Р вЂќ

                temp_file_path = None

                try:

                    # Р РЋР С•Р В·Р Т‘Р В°Р ВµР С� Р Р†РЎР‚Р ВµР С�Р ВµР Р…Р Р…РЎвЂ№Р в„– РЎвЂћР В°Р в„–Р В» Р Т‘Р В»РЎРЏ Р С•РЎРѓР Р…Р С•Р Р†Р Р…Р С•Р в„– Р вЂ�Р вЂќ

                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:

                        json.dump(analysis_data, temp_file, ensure_ascii=False, indent=2)

                        temp_file_path = temp_file.name

                    

                    loader = JSONToDBLoader()

                    main_db_result = loader.load_from_json(temp_file_path)

                    main_db_info = {

                        'loaded': True,

                        'store_items': main_db_result.get('store_inserted', 0),

                        'analysis_items': main_db_result.get('analysis_inserted', 0),

                        'errors': main_db_result.get('errors', [])

                    }

                finally:

                    # Р Р€Р Т‘Р В°Р В»РЎРЏР ВµР С� Р Р†РЎР‚Р ВµР С�Р ВµР Р…Р Р…РЎвЂ№Р в„– РЎвЂћР В°Р в„–Р В»

                    if temp_file_path and os.path.exists(temp_file_path):

                        os.unlink(temp_file_path)

                        

            except Exception as main_db_error:


                main_db_info['errors'] = [str(main_db_error)]

        # =================================================================


        

        # =============== Р вЂњР вЂўР СњР вЂўР В Р С’Р В¦Р В�Р Р‡ Р вЂњР В Р С’Р В¤Р В�Р С™Р С›Р вЂ™ ===============
        charts_info = {
            'generated': False,
            'count': 0,
            'errors': [],
            'status': 'pending'
        }
        # Charts are generated via /api/charts to avoid blocking /upload.
        # =================================================

        

        # Р СџР С•Р Т‘РЎРѓРЎвЂЎР С‘РЎвЂљРЎвЂ№Р Р†Р В°Р ВµР С� РЎРѓРЎвЂљР В°РЎвЂљР С‘РЎРѓРЎвЂљР С‘Р С”РЎС“ Р Т‘Р В»РЎРЏ Р С•РЎвЂљР Р†Р ВµРЎвЂљР В°

        abc_stats = {}

        xyz_stats = {}

        abc_xyz_stats = {}

        

        for item in analysis_data:

            if isinstance(item, dict):

                abc = item.get('ABC') or item.get('abc_category')

                xyz = item.get('XYZ') or item.get('xyz_category')

                abc_xyz = item.get('ABC_XYZ') or item.get('abc_xyz_category')

                

                if abc:

                    abc_stats[abc] = abc_stats.get(abc, 0) + 1

                if xyz:

                    xyz_stats[xyz] = xyz_stats.get(xyz, 0) + 1

                if abc_xyz:

                    abc_xyz_stats[abc_xyz] = abc_xyz_stats.get(abc_xyz, 0) + 1

        

        # Р С›Р С—РЎР‚Р ВµР Т‘Р ВµР В»РЎРЏР ВµР С� Р С‘Р С�Р ВµР Р…Р В° РЎвЂћР В°Р в„–Р В»Р С•Р Р† Р Т‘Р В»РЎРЏ РЎРѓР С”Р В°РЎвЂЎР С‘Р Р†Р В°Р Р…Р С‘РЎРЏ

        analysis_filename = f"{Path(filename).stem}_analysis.json"

        

        response_data = {

            'success': True,

            'message': f'Р В¤Р В°Р в„–Р В» "{filename}" РЎС“РЎРѓР С—Р ВµРЎв‚¬Р Р…Р С• Р С•Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР В°Р Р…',

            'original_file': filename,

            'json_file': json_result['file_name'],

            'analysis_file': analysis_filename,

            'db_info': db_info,

            'main_db_info': main_db_info,

            'charts_info': charts_info,

            'stats': {

                'total_items': len(analysis_data),

                'abc_distribution': abc_stats,

                'xyz_distribution': xyz_stats,

                'abc_xyz_matrix': abc_xyz_stats

            },
            'analysis_data': analysis_data[:1000],

            'download_links': {

                'json': f'/download/{OUTPUT_JSON_FOLDER}/{json_result["file_name"]}',

                'analysis': f'/download/{ANALYSIS_RESULTS_FOLDER}/{analysis_filename}'

            }

        }

        

        return jsonify(response_data)

        

    except Exception as e:


        import traceback

        traceback.print_exc()

        return jsonify({'error': str(e)}), 500



@app.route('/upload-combined', methods=['POST'])
def upload_combined():
    """Загрузка нескольких Excel файлов и формирование общего отчета."""
    try:
        files = request.files.getlist('files')
        if not files:
            return jsonify({'success': False, 'error': 'Файлы не найдены в запросе'}), 400

        saved_files = []
        for file in files:
            if file and allowed_file(file.filename):
                original_name = file.filename
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                saved_files.append({
                    'path': filepath,
                    'original_name': original_name,
                    'saved_name': filename
                })

        if not saved_files:
            return jsonify({'success': False, 'error': 'Нет валидных Excel файлов (.xls, .xlsx)'}), 400

        def normalize_name(value: str) -> str:
            return re.sub(r"[^0-9a-z\u0430-\u044f]+", "", value.lower())

        # Определяем файлы по названию (используем оригинальные имена, а не secure_filename)
        file_map = {}
        for entry in saved_files:
            name = normalize_name(entry['original_name'])
            if 'articlemasterdata' in name or 'основныеданные' in name:
                file_map['master'] = entry['path']
            elif 'движениястока' in name:
                file_map['movements'] = entry['path']
            elif 'линиипикинга' in name:
                file_map['lines'] = entry['path']
            elif 'abc' in name and 'анализ' in name:
                file_map['abc'] = entry['path']
            elif 'проверказаказано' in name:
                file_map['order_picked'] = entry['path']
            elif 'pud' in name or ('отч' in name and 'стоку' in name):
                file_map['stock'] = entry['path']

        required_keys = ['master', 'movements', 'lines', 'abc', 'order_picked', 'stock']
        missing = [key for key in required_keys if key not in file_map]
        if missing:
            return jsonify({
                'success': False,
                'error': 'Не все обязательные файлы загружены',
                'missing': missing
            }), 400

        result = generate_combined_report(
            master_file=Path(file_map['master']),
            stock_report_file=Path(file_map['stock']),
            order_picked_file=Path(file_map['order_picked']),
            stock_movements_file=Path(file_map['movements']),
            picking_lines_file=Path(file_map['lines']),
            abc_analysis_file=Path(file_map['abc']),
            output_dir=ANALYSIS_RESULTS_DIR
        )

        def sanitize(value):
            if value is None:
                return None
            if isinstance(value, float) and math.isnan(value):
                return None
            if isinstance(value, dict):
                return {k: sanitize(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [sanitize(v) for v in value]
            return value

        return jsonify({
            'success': True,
            'report_file': result.file_path.name,
            'rows': sanitize(result.rows)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download-report/<path:filename>')
def download_report(filename):
    """Скачивание сформированного общего отчета."""
    try:
        return send_from_directory(ANALYSIS_RESULTS_DIR, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 404


@app.route('/api/analysis-data', methods=['GET'])
def get_analysis_data():
    """API для получения данных анализа из основной БД"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных недоступна'}), 500

    try:
        limit = request.args.get('limit', 1000, type=int)
        session = db.get_session()
        from db.models import Analysis

        rows = (
            session.query(Analysis)
            .order_by(Analysis.revenue.desc(), Analysis.id.asc())
            .limit(limit)
            .all()
        )

        data = []
        for row in rows:
            data.append({
                'id': row.id,
                'product_name': row.product_name,
                'revenue': float(row.revenue) if row.revenue else 0,
                'abc_category': row.abc_category,
                'xyz_category': row.xyz_category,
                'abc_xyz_category': row.abc_xyz_category,
                'rank': row.id
            })
        session.close()

        return jsonify({
            'success': True,
            'count': len(data),
            'data': data,
            'analysis_id': 'main_db'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/check-data')
def check_data():
    """Проверка наличия данных в основной БД"""
    if not DB_AVAILABLE:
        return jsonify({'has_data': False, 'error': 'База данных недоступна'}), 500

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


@app.route('/api/check-analysis-data')
def check_analysis_data():
    """Проверка наличия данных анализа в основной БД"""
    if not DB_AVAILABLE:
        return jsonify({'has_data': False, 'error': 'База данных недоступна'}), 500

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


@app.route('/api/charts', methods=['GET'])
def get_charts():
    """API для получения или генерации графиков"""
    if not CHARTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'chart_generator_not_available'}), 500

    # Сначала пробуем получить сохраненные графики
    if ANALYSIS_DB_AVAILABLE and analysis_db is not None:
        try:
            charts = analysis_db.get_charts()
            if charts:
                return jsonify({'success': True, 'charts': charts})
        except Exception:
            pass

    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'database_not_available'}), 500

    session = None
    try:
        session = db.get_session()
        generator = ChartGenerator(session, analysis_db=analysis_db)
        charts = generator.generate_all_charts()

        if charts:
            # Пытаемся сохранить графики в БД анализа
            if ANALYSIS_DB_AVAILABLE and analysis_db is not None:
                try:
                    latest = analysis_db.get_latest_analysis()
                    analysis_id = latest.get('analysis_id') or latest.get('id')
                    if analysis_id:
                        analysis_db.save_charts(analysis_id, charts)
                except Exception:
                    pass

            return jsonify({'success': True, 'charts': charts})

        return jsonify({'success': False, 'error': 'charts_not_generated'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """API для получения статистики анализа"""
    # Основной вариант: статистика из основной БД
    if DB_AVAILABLE:
        session = None
        try:
            session = db.get_session()
            from db.models import Analysis

            total_items = session.query(func.count(Analysis.id)).scalar() or 0
            total_revenue = session.query(func.sum(Analysis.revenue)).scalar() or 0
            average_revenue = session.query(func.avg(Analysis.revenue)).scalar() or 0
            last_update = session.query(func.max(Analysis.analysis_date)).scalar()

            abc_rows = (
                session.query(Analysis.abc_category, func.count(Analysis.id))
                .group_by(Analysis.abc_category)
                .all()
            )
            xyz_rows = (
                session.query(Analysis.xyz_category, func.count(Analysis.id))
                .group_by(Analysis.xyz_category)
                .all()
            )

            abc_distribution = {}
            for category, count in abc_rows:
                if not category:
                    continue
                abc_distribution[category] = {
                    'count': int(count),
                    'percentage': (float(count) / total_items * 100) if total_items else 0
                }

            xyz_distribution = {}
            for category, count in xyz_rows:
                if not category:
                    continue
                xyz_distribution[category] = {
                    'count': int(count),
                    'percentage': (float(count) / total_items * 100) if total_items else 0
                }

            top_rows = (
                session.query(Analysis.product_name, Analysis.revenue, Analysis.abc_xyz_category)
                .order_by(Analysis.revenue.desc())
                .limit(3)
                .all()
            )
            top_products = [
                {
                    'name': row[0],
                    'revenue': float(row[1]) if row[1] else 0,
                    'category': row[2] or ''
                }
                for row in top_rows
            ]

            return jsonify({
                'success': True,
                'stats': {
                    'total_items': int(total_items),
                    'total_revenue': float(total_revenue),
                    'average_revenue': float(average_revenue),
                    'abc_distribution': abc_distribution,
                    'xyz_distribution': xyz_distribution,
                    'last_update': last_update.isoformat() if last_update else datetime.now().isoformat(),
                    'top_products': top_products
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass

    # Резервный вариант: статистика из БД анализа
    if ANALYSIS_DB_AVAILABLE and analysis_db is not None:
        try:
            stats = analysis_db.get_analysis_stats()
            matrix = analysis_db.get_matrix_data()

            abc_distribution = {}
            xyz_distribution = {}
            total_items = 0

            for row in matrix:
                count = row.get('products_count', 0) or 0
                total_items += count
                abc = row.get('abc_category')
                xyz = row.get('xyz_category')
                if abc:
                    abc_distribution[abc] = abc_distribution.get(abc, 0) + count
                if xyz:
                    xyz_distribution[xyz] = xyz_distribution.get(xyz, 0) + count

            abc_distribution = {
                k: {
                    'count': int(v),
                    'percentage': (float(v) / total_items * 100) if total_items else 0
                }
                for k, v in abc_distribution.items()
            }
            xyz_distribution = {
                k: {
                    'count': int(v),
                    'percentage': (float(v) / total_items * 100) if total_items else 0
                }
                for k, v in xyz_distribution.items()
            }

            top_products = []
            if stats.get('top_product_name'):
                top_products.append({
                    'name': stats.get('top_product_name'),
                    'revenue': float(stats.get('top_product_revenue') or 0),
                    'category': ''
                })

            return jsonify({
                'success': True,
                'stats': {
                    'total_items': int(stats.get('total_products') or total_items or 0),
                    'total_revenue': float(stats.get('total_revenue') or 0),
                    'average_revenue': float(stats.get('avg_revenue') or 0),
                    'abc_distribution': abc_distribution,
                    'xyz_distribution': xyz_distribution,
                    'last_update': stats.get('analysis_date') or datetime.now().isoformat(),
                    'top_products': top_products
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    return jsonify({'success': False, 'error': 'no_data_source'}), 500


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """API чат-ассистента по складской логистике"""
    if chat_assistant is None:
        return jsonify({
            'success': False,
            'error': 'chat_assistant_not_available',
            'answer': 'В базе данных нет информации для ответа на этот вопрос.'
        }), 500

    try:
        payload = request.get_json(silent=True) or {}
        message = (payload.get('message') or '').strip()
        history = payload.get('history') or []

        if not message:
            return jsonify({
                'success': True,
                'answer': 'В базе данных нет информации для ответа на этот вопрос.',
                'meta': {'source': 'guard'}
            })

        result = chat_assistant.answer(message, history=history)
        return jsonify({
            'success': True,
            'answer': result.get('answer') or 'В базе данных нет информации для ответа на этот вопрос.',
            'meta': {
                'source': result.get('source'),
                'model_loaded': bool(result.get('model_loaded')),
                'model_backend': result.get('model_backend') or 'none'
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'answer': 'В базе данных нет информации для ответа на этот вопрос.'
        }), 500


@app.route('/api/delete-by-file', methods=['POST'])
def delete_by_file():
    """Удаление данных из БД по Excel файлу"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'База данных недоступна'}), 500

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Файл не найден в запросе'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'success': False, 'error': 'Файл не выбран'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Разрешены только файлы Excel (.xls, .xlsx)'}), 400

    import tempfile
    temp_path = None
    try:
        suffix = Path(file.filename).suffix or '.xlsx'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            file.save(temp_path)

        df = pd.read_excel(temp_path)
    except Exception as e:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        return jsonify({'success': False, 'error': f'Ошибка чтения Excel: {str(e)}'}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

    if df is None or df.empty:
        return jsonify({'success': False, 'error': 'Файл пустой или не содержит данных'}), 400

    def normalize_name(value):
        if pd.isna(value):
            return None
        name = str(value).strip()
        return name if name else None

    def parse_id(value):
        if pd.isna(value):
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    columns = [str(col) for col in df.columns]

    def normalize_col(value: str) -> str:
        value = value.strip().lower()
        value = value.replace('ё', 'е')
        for ch in [' ', '\t', '\n', '\r', '.', ',', '-', '_', '/', '\\', '(', ')', '[', ']', '{', '}', '"', "'"]:
            value = value.replace(ch, '')
        return value

    normalized_columns = [normalize_col(col) for col in columns]

    name_patterns = [
        'наимен', 'наименован', 'товар', 'номенклатур', 'product', 'productname',
        'позиция', 'item', 'title'
    ]
    id_patterns = [
        'id', 'артикул', 'sku', 'article', 'код', 'productid', 'штрихкод', 'barcode', 'ean'
    ]

    name_columns = [columns[i] for i, col in enumerate(normalized_columns) if any(p in col for p in name_patterns)]
    id_columns = [columns[i] for i, col in enumerate(normalized_columns) if any(p in col for p in id_patterns)]

    if not name_columns and not id_columns:
        numeric_scores = []
        text_scores = []
        for col in columns:
            series = df[col].dropna()
            if series.empty:
                numeric_scores.append((0, col))
                text_scores.append((0, col))
                continue
            numeric_count = 0
            text_count = 0
            for value in series.head(200).tolist():
                try:
                    float(value)
                    numeric_count += 1
                except Exception:
                    text_count += 1
            numeric_scores.append((numeric_count, col))
            text_scores.append((text_count, col))

        numeric_scores.sort(reverse=True)
        text_scores.sort(reverse=True)

        if numeric_scores and numeric_scores[0][0] > 0:
            id_columns = [numeric_scores[0][1]]
        if text_scores and text_scores[0][0] > 0:
            name_columns = [text_scores[0][1]]

    names = set()
    ids = set()

    for col in id_columns:
        for value in df[col].tolist():
            parsed = parse_id(value)
            if parsed is not None:
                ids.add(parsed)

    for col in name_columns:
        for value in df[col].tolist():
            normalized = normalize_name(value)
            if normalized:
                names.add(normalized)

    if not names and not ids:
        return jsonify({
            'success': False,
            'error': 'Не удалось определить столбцы с ID или наименованием товара',
            'columns': columns
        }), 400

    session = db.get_session()
    try:
        from db.models import Store, Analysis

        existing_store_ids = set()
        existing_analysis_ids = set()
        analysis_store_ids = set()
        existing_store_names = set()
        existing_analysis_names = set()

        if ids:
            existing_store_ids = {row[0] for row in session.query(Store.id).filter(Store.id.in_(ids)).all()}
            existing_analysis_ids = {row[0] for row in session.query(Analysis.id).filter(Analysis.id.in_(ids)).all()}
            analysis_store_ids = {
                row[0] for row in session.query(Analysis.store_id)
                .filter(Analysis.id.in_(ids), Analysis.store_id.isnot(None))
                .all()
            }

        if names:
            existing_store_names = {row[0] for row in session.query(Store.product_name).filter(Store.product_name.in_(names)).all()}
            existing_analysis_names = {row[0] for row in session.query(Analysis.product_name).filter(Analysis.product_name.in_(names)).all()}

        missing_ids = sorted(ids - (existing_store_ids | existing_analysis_ids))
        missing_names = sorted(names - (existing_store_names | existing_analysis_names))

        deleted_analysis = 0
        deleted_store = 0

        def chunked(iterable, size=500):
            items = list(iterable)
            for i in range(0, len(items), size):
                yield items[i:i + size]

        for chunk in chunked(existing_store_ids):
            deleted_analysis += session.query(Analysis).filter(Analysis.store_id.in_(chunk)).delete(synchronize_session=False)
        for chunk in chunked(existing_analysis_ids):
            deleted_analysis += session.query(Analysis).filter(Analysis.id.in_(chunk)).delete(synchronize_session=False)
        for chunk in chunked(existing_store_names):
            deleted_analysis += session.query(Analysis).filter(Analysis.product_name.in_(chunk)).delete(synchronize_session=False)
        for chunk in chunked(existing_analysis_names):
            deleted_analysis += session.query(Analysis).filter(Analysis.product_name.in_(chunk)).delete(synchronize_session=False)

        for chunk in chunked(existing_store_ids):
            deleted_store += session.query(Store).filter(Store.id.in_(chunk)).delete(synchronize_session=False)
        for chunk in chunked(analysis_store_ids):
            deleted_store += session.query(Store).filter(Store.id.in_(chunk)).delete(synchronize_session=False)
        for chunk in chunked(existing_store_names):
            deleted_store += session.query(Store).filter(Store.product_name.in_(chunk)).delete(synchronize_session=False)
        for chunk in chunked(existing_analysis_names):
            deleted_store += session.query(Store).filter(Store.product_name.in_(chunk)).delete(synchronize_session=False)

        session.commit()

        # Если все удалено, сбрасываем счетчики ID
        try:
            if session.query(Store).count() == 0:
                try:
                    session.execute(text("DELETE FROM sqlite_sequence WHERE name='store'"))
                except Exception:
                    pass
            if session.query(Analysis).count() == 0:
                try:
                    session.execute(text("DELETE FROM sqlite_sequence WHERE name='analysis'"))
                except Exception:
                    pass
            session.commit()
        except Exception:
            session.rollback()

        return jsonify({
            'success': True,
            'deleted': {
                'analysis': deleted_analysis,
                'store': deleted_store
            },
            'requested': {
                'ids': len(ids),
                'names': len(names)
            },
            'missing': {
                'ids': missing_ids,
                'names': missing_names
            }
        })
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
