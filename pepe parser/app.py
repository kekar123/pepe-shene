# -*- coding: utf-8 -*-
import sys
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

from sqlalchemy import func, or_, text

import sqlite3

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

            'errors': []

        }

        

        # Р В�РЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµР С� Р С•РЎРѓР Р…Р С•Р Р†Р Р…РЎС“РЎР‹ Р вЂ�Р вЂќ Р Т‘Р В»РЎРЏ Р С–Р ВµР Р…Р ВµРЎР‚Р В°РЎвЂ Р С‘Р С‘ Р С–РЎР‚Р В°РЎвЂћР С‘Р С”Р С•Р Р†

        if DB_AVAILABLE and CHARTS_AVAILABLE:

            try:

                session = db.get_session()

                generator = ChartGenerator(session, analysis_db=analysis_db, analysis_data=analysis_data)

                charts = generator.generate_all_charts()

                session.close()

                

                if charts:

                    charts_info = {

                        'generated': True,

                        'count': len(charts),

                        'charts': charts

                    }


                    

                    # Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎРЏР ВµР С� Р С–РЎР‚Р В°РЎвЂћР С‘Р С”Р С‘ Р Р† Р вЂ�Р вЂќ Р В°Р Р…Р В°Р В»Р С‘Р В·Р В°

                    if ANALYSIS_DB_AVAILABLE and db_info['loaded']:

                        analysis_db.save_charts(

                            db_info['analysis_id'], 

                            charts_info['charts']

                        )


                        

            except Exception as chart_error:


                charts_info['errors'] = [str(chart_error)]

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

