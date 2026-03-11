# -*- coding: utf-8 -*-
import sys
import traceback
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

import os
import threading
import uuid

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


# =============== Р В РІР‚СњР В РЎвЂєР В РЎСџР В РЎвЂєР В РІР‚С”Р В РЎСљР В РІР‚СћР В РЎСљР В Р’пїЅР В Р вЂЎ Р В РІР‚СњР В РІР‚С”Р В Р вЂЎ Р В РІР‚пїЅР В РЎвЂ™Р В РІР‚вЂќР В Р’В« Р В РІР‚СњР В РЎвЂ™Р В РЎСљР В РЎСљР В Р’В«Р В РўС’ ===============

import sys



# Р В РІР‚СњР В РЎвЂўР В Р’В±Р В Р’В°Р В Р вЂ Р В Р’В»Р РЋР РЏР В Р’ВµР В РЎпїЅ Р В РЎвЂ”Р РЋРЎвЂњР РЋРІР‚С™Р РЋР Р‰ Р В РЎвЂќ Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В Р вЂ¦Р РЋР вЂ№ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В Р’ВµР В РЎвЂќР РЋРІР‚С™Р В Р’В° Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎвЂР В РЎпїЅР В РЎвЂ”Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™Р В Р’В° Р В РЎпїЅР В РЎвЂўР В РўвЂР РЋРЎвЂњР В Р’В»Р В Р’ВµР В РІвЂћвЂ“

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



# =============== Р В РЎСљР В РЎвЂєР В РІР‚в„ўР В Р’В«Р В РІвЂћСћ Р В РІР‚вЂќР В РЎвЂ™Р В РІР‚СљР В Р’В Р В Р в‚¬Р В РІР‚вЂќР В Р’В§Р В Р’пїЅР В РЎв„ў Р В РІР‚СњР В РІР‚С”Р В Р вЂЎ Р В РЎвЂ™Р В РЎСљР В РЎвЂ™Р В РІР‚С”Р В Р’пїЅР В РІР‚вЂќР В РЎвЂ™ ===============

try:

    from analysis_db_loader import AnalysisDBLoader

    ANALYSIS_DB_AVAILABLE = True

    print("INFO: AnalysisDBLoader loaded")
except ImportError as e:

    print(f"WARNING: AnalysisDBLoader not found: {e}")
    ANALYSIS_DB_AVAILABLE = False

    AnalysisDBLoader = None

analysis_db = None



# =============== Р В РІР‚СњР В РЎвЂєР В РЎСџР В РЎвЂєР В РІР‚С”Р В РЎСљР В РІР‚СћР В РЎСљР В Р’пїЅР В Р вЂЎ Р В РІР‚СњР В РІР‚С”Р В Р вЂЎ Р В РІР‚СљР В Р’В Р В РЎвЂ™Р В Р’В¤Р В Р’пїЅР В РЎв„ўР В РЎвЂєР В РІР‚в„ў ===============

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



# =============== Р В Р’пїЅР В РЎСљР В Р’пїЅР В Р’В¦Р В Р’пїЅР В РЎвЂ™Р В РІР‚С”Р В Р’пїЅР В РІР‚вЂќР В РЎвЂ™Р В Р’В¦Р В Р’пїЅР В Р вЂЎ Р В РІР‚пїЅР В РЎвЂ™Р В РІР‚вЂќ Р В РІР‚СњР В РЎвЂ™Р В РЎСљР В РЎСљР В Р’В«Р В РўС’ ===============

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



# Р В РЎв„ўР В РЎвЂўР В Р вЂ¦Р РЋРІР‚С›Р В РЎвЂР В РЎвЂ“Р РЋРЎвЂњР РЋР вЂљР В Р’В°Р РЋРІР‚В Р В РЎвЂР РЋР РЏ

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

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 Р В РЎС™Р В РІР‚пїЅ



def allowed_file(filename):

    """Р В РЎСџР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР В РЎвЂќР В Р’В° Р РЋР вЂљР В Р’В°Р РЋР С“Р РЋРІвЂљВ¬Р В РЎвЂР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В РЎвЂР РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р В Р’В°"""

    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_pick_location(raw_value):
    """Parse location code like E-743-0025-10 into structured parts."""
    if raw_value is None:
        return None

    value = str(raw_value).strip().upper()
    if not value:
        return None

    match = re.match(r'^([A-ZА-Я])-(\d{3})-(\d{4})-(\d{2})$', value)
    if not match:
        return None

    zone, aisle, place, level = match.groups()
    return {
        'code': value,
        'zone': zone,
        'aisle': int(aisle),
        'place': int(place),
        'level': int(level),
    }


def extract_locations_from_json_file(json_file: Path):
    try:
        with json_file.open('r', encoding='utf-8') as f:
            payload = json.load(f)
    except Exception:
        return []

    if not isinstance(payload, list):
        return []

    location_keys = [
        'МЕСТО_ОТБОРА',
        'Место отбора',
        'Место пикинг',
        'place',
        'location',
        'Location',
    ]

    seen = set()
    locations = []
    for row in payload:
        if not isinstance(row, dict):
            continue

        parsed = None
        for key in location_keys:
            if key in row:
                parsed = parse_pick_location(row.get(key))
                if parsed:
                    break

        if not parsed:
            continue

        code = parsed['code']
        if code in seen:
            continue
        seen.add(code)
        locations.append(parsed)

    return locations


def parse_int_value(raw_value):
    if raw_value is None:
        return None
    try:
        if isinstance(raw_value, float) and math.isnan(raw_value):
            return None
    except Exception:
        pass

    text = str(raw_value).strip()
    if not text:
        return None

    match = re.search(r'\d+', text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except Exception:
        return None


def parse_aisle_from_value(raw_value):
    if raw_value is None:
        return None
    text = str(raw_value).strip().upper()
    if not text:
        return None

    code_match = re.search(r'[A-ZА-Я]-(\d{3})-(\d{4})-(\d{2})', text)
    if code_match:
        return int(code_match.group(1))
    return parse_int_value(text)


def parse_place_from_value(raw_value):
    if raw_value is None:
        return None
    text = str(raw_value).strip().upper()
    if not text:
        return None

    code_match = re.search(r'[A-ZА-Я]-(\d{3})-(\d{4})-(\d{2})', text)
    if code_match:
        return int(code_match.group(2))
    return parse_int_value(text)


def normalize_stock_color(raw_value):
    if raw_value is None:
        return None
    value = str(raw_value).strip().lower()
    if not value:
        return None
    if 'крас' in value or value == 'red':
        return 'red'
    if 'желт' in value or 'жёлт' in value or value == 'yellow':
        return 'yellow'
    if 'зелен' in value or 'зелён' in value or value == 'green':
        return 'green'
    return None


def find_dataframe_column(columns, candidates):
    normalized = {str(col).strip().lower(): col for col in columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]

    for col in columns:
        current = str(col).strip().lower()
        for candidate in candidates:
            if candidate.strip().lower() in current:
                return col
    return None



@app.route('/')

def index():

    """Р В РІР‚СљР В Р’В»Р В Р’В°Р В Р вЂ Р В Р вЂ¦Р В Р’В°Р РЋР РЏ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В Р В Р’В° Р РЋР С“ Р РЋРІР‚С›Р В РЎвЂўР РЋР вЂљР В РЎпїЅР В РЎвЂўР В РІвЂћвЂ“"""

    return render_template('form4.html')

@app.route('/combined')
def combined_page():
    return render_template('combined.html')


@app.route('/warehouse')
def warehouse_page():
    return render_template('warehouse.html')



@app.route('/remove')

def remove_page():

    return render_template('remove.html')



@app.route('/upload', methods=['POST'])

def upload_file():

    """Р В РЎвЂєР В Р’В±Р РЋР вЂљР В Р’В°Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂќР В Р’В° Р В Р’В·Р В Р’В°Р В РЎвЂ“Р РЋР вЂљР РЋРЎвЂњР В Р’В·Р В РЎвЂќР В РЎвЂ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р В Р’В° Р РЋР С“ Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР В РЎпїЅР В Р’В°Р РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р’ВµР РЋР С“Р В РЎвЂќР В РЎвЂўР В РІвЂћвЂ“ Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚В Р В РЎвЂР В Р’ВµР В РІвЂћвЂ“ Р В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚С›Р В РЎвЂР В РЎвЂќР В РЎвЂўР В Р вЂ  Р В РЎвЂ Р РЋР С“Р В РЎвЂўР РЋРІР‚В¦Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂР В Р’ВµР В РЎпїЅ Р В Р вЂ  Р В РІР‚пїЅР В РІР‚Сњ"""

    try:

        if 'file' not in request.files:

            return jsonify({'error': 'Р В Р’В¤Р В Р’В°Р В РІвЂћвЂ“Р В Р’В» Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ¦Р В Р’В°Р В РІвЂћвЂ“Р В РўвЂР В Р’ВµР В Р вЂ¦ Р В Р вЂ  Р В Р’В·Р В Р’В°Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р В Р’Вµ'}), 400

        

        file = request.files['file']

        

        if file.filename == '':

            return jsonify({'error': 'Р В Р’В¤Р В Р’В°Р В РІвЂћвЂ“Р В Р’В» Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р РЋРІР‚в„–Р В Р’В±Р РЋР вЂљР В Р’В°Р В Р вЂ¦'}), 400

        

        if not allowed_file(file.filename):

            return jsonify({'error': 'Р В Р’В Р В Р’В°Р В Р’В·Р РЋР вЂљР В Р’ВµР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р РЋРІР‚в„– Р РЋРІР‚С™Р В РЎвЂўР В Р’В»Р РЋР Р‰Р В РЎвЂќР В РЎвЂў Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р РЋРІР‚в„– Excel (.xls, .xlsx)'}), 400

        

        # Р В Р Р‹Р В РЎвЂўР РЋРІР‚В¦Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р РЋР РЏР В Р’ВµР В РЎпїЅ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»

        filename = secure_filename(file.filename)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        file.save(filepath)

        

        # Р В РЎСџР В Р’В°Р РЋР вЂљР РЋР С“Р В РЎвЂР В РЎпїЅ Excel Р В Р вЂ  JSON

        json_result = xls_to_json_single(

            input_file=filepath,

            output_folder=str(OUTPUT_JSON_DIR)

        )

        

        if not json_result:

            return jsonify({'error': 'Р В РЎвЂєР РЋРІвЂљВ¬Р В РЎвЂР В Р’В±Р В РЎвЂќР В Р’В° Р В РЎвЂ”Р РЋР вЂљР В РЎвЂ Р В РЎвЂ”Р В Р’В°Р РЋР вЂљР РЋР С“Р В РЎвЂР В Р вЂ¦Р В РЎвЂ“Р В Р’Вµ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р В Р’В°'}), 500

        

        # Р В РІР‚в„ўР РЋРІР‚в„–Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р В Р вЂ¦Р РЋР РЏР В Р’ВµР В РЎпїЅ ABC-XYZ Р В Р’В°Р В Р вЂ¦Р В Р’В°Р В Р’В»Р В РЎвЂР В Р’В·

        analysis_data = perform_abc_xyz_analysis(

            json_file_path=json_result['output'],

            output_file_name=f"{Path(filename).stem}_analysis.json"

        )

        

        if not analysis_data:

            return jsonify({'error': 'Р В РЎвЂєР РЋРІвЂљВ¬Р В РЎвЂР В Р’В±Р В РЎвЂќР В Р’В° Р В РЎвЂ”Р РЋР вЂљР В РЎвЂ Р В Р вЂ Р РЋРІР‚в„–Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂР В РЎвЂ Р В Р’В°Р В Р вЂ¦Р В Р’В°Р В Р’В»Р В РЎвЂР В Р’В·Р В Р’В°'}), 500

        

        # =============== Р В Р Р‹Р В РЎвЂєР В РўС’Р В Р’В Р В РЎвЂ™Р В РЎСљР В РІР‚СћР В РЎСљР В Р’пїЅР В РІР‚Сћ Р В РЎвЂ™Р В РЎСљР В РЎвЂ™Р В РІР‚С”Р В Р’пїЅР В РІР‚вЂќР В РЎвЂ™ Р В РІР‚в„ў Р В РІР‚пїЅР В РІР‚Сњ Р В РІР‚СњР В РІР‚С”Р В Р вЂЎ Р В РІР‚СљР В Р’В Р В РЎвЂ™Р В Р’В¤Р В Р’пїЅР В РЎв„ўР В РЎвЂєР В РІР‚в„ў ===============

        db_info = {

            'loaded': False,

            'analysis_id': None,

            'products_count': 0,

            'errors': []

        }

        

        if ANALYSIS_DB_AVAILABLE:

            try:

                # Р В Р Р‹Р В РЎвЂўР РЋРІР‚В¦Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р РЋР РЏР В Р’ВµР В РЎпїЅ Р В Р вЂ Р РЋР вЂљР В Р’ВµР В РЎпїЅР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋРІР‚в„–Р В РІвЂћвЂ“ JSON Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В» Р РЋР С“ Р РЋР вЂљР В Р’ВµР В Р’В·Р РЋРЎвЂњР В Р’В»Р РЋР Р‰Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р В Р’В°Р В РЎпїЅР В РЎвЂ Р В Р’В°Р В Р вЂ¦Р В Р’В°Р В Р’В»Р В РЎвЂР В Р’В·Р В Р’В°

                import tempfile

                import json

                

                # Р В Р Р‹Р В РЎвЂўР В Р’В·Р В РўвЂР В Р’В°Р В Р’ВµР В РЎпїЅ Р В Р вЂ Р РЋР вЂљР В Р’ВµР В РЎпїЅР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋРІР‚в„–Р В РІвЂћвЂ“ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В» Р РЋР С“ Р РЋР вЂљР В Р’ВµР В Р’В·Р РЋРЎвЂњР В Р’В»Р РЋР Р‰Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р В Р’В°Р В РЎпїЅР В РЎвЂ Р В Р’В°Р В Р вЂ¦Р В Р’В°Р В Р’В»Р В РЎвЂР В Р’В·Р В Р’В°

                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:

                    json.dump(analysis_data, temp_file, ensure_ascii=False, indent=2)

                    temp_file_path = temp_file.name

                

                # Р В РІР‚вЂќР В Р’В°Р В РЎвЂ“Р РЋР вЂљР РЋРЎвЂњР В Р’В¶Р В Р’В°Р В Р’ВµР В РЎпїЅ Р В Р’В°Р В Р вЂ¦Р В Р’В°Р В Р’В»Р В РЎвЂР В Р’В· Р В Р вЂ  Р В РІР‚пїЅР В РІР‚Сњ

                db_result = analysis_db.load_analysis_from_json(

                    analysis_file_path=temp_file_path,

                    analysis_type="abc_xyz"

                )

                

                # Р В Р в‚¬Р В РўвЂР В Р’В°Р В Р’В»Р РЋР РЏР В Р’ВµР В РЎпїЅ Р В Р вЂ Р РЋР вЂљР В Р’ВµР В РЎпїЅР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋРІР‚в„–Р В РІвЂћвЂ“ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»

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

                    db_info['errors'] = db_result.get('errors', ['Р В РЎСљР В Р’ВµР В РЎвЂР В Р’В·Р В Р вЂ Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В Р вЂ¦Р В Р’В°Р РЋР РЏ Р В РЎвЂўР РЋРІвЂљВ¬Р В РЎвЂР В Р’В±Р В РЎвЂќР В Р’В°'])

                    

            except Exception as db_error:


                import traceback

                traceback.print_exc()

                db_info['errors'] = [str(db_error)]

        # ======================================================================

        

        # =============== Р В РІР‚вЂќР В РЎвЂ™Р В РІР‚СљР В Р’В Р В Р в‚¬Р В РІР‚вЂќР В РЎв„ўР В РЎвЂ™ Р В РІР‚в„ў Р В РЎвЂєР В Р Р‹Р В РЎСљР В РЎвЂєР В РІР‚в„ўР В РЎСљР В Р в‚¬Р В Р’В® Р В РІР‚пїЅР В РЎвЂ™Р В РІР‚вЂќР В Р в‚¬ Р В РІР‚СњР В РЎвЂ™Р В РЎСљР В РЎСљР В Р’В«Р В РўС’ ===============

        main_db_info = {

            'loaded': False,

            'store_items': 0,

            'analysis_items': 0,

            'errors': []

        }

        

        if DB_AVAILABLE:

            try:

                # Р В Р Р‹Р В РЎвЂўР РЋРІР‚В¦Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р РЋР РЏР В Р’ВµР В РЎпїЅ Р РЋРІР‚С™Р В Р’В°Р В РЎвЂќР В Р’В¶Р В Р’Вµ Р В Р вЂ  Р В РЎвЂўР РЋР С“Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р РЋРЎвЂњР РЋР вЂ№ Р В РІР‚пїЅР В РІР‚Сњ

                temp_file_path = None

                try:

                    # Р В Р Р‹Р В РЎвЂўР В Р’В·Р В РўвЂР В Р’В°Р В Р’ВµР В РЎпїЅ Р В Р вЂ Р РЋР вЂљР В Р’ВµР В РЎпїЅР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋРІР‚в„–Р В РІвЂћвЂ“ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В» Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎвЂўР РЋР С“Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂўР В РІвЂћвЂ“ Р В РІР‚пїЅР В РІР‚Сњ

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

                    # Р В Р в‚¬Р В РўвЂР В Р’В°Р В Р’В»Р РЋР РЏР В Р’ВµР В РЎпїЅ Р В Р вЂ Р РЋР вЂљР В Р’ВµР В РЎпїЅР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋРІР‚в„–Р В РІвЂћвЂ“ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»

                    if temp_file_path and os.path.exists(temp_file_path):

                        os.unlink(temp_file_path)

                        

            except Exception as main_db_error:


                main_db_info['errors'] = [str(main_db_error)]

        # =================================================================


        

        # =============== Р В РІР‚СљР В РІР‚СћР В РЎСљР В РІР‚СћР В Р’В Р В РЎвЂ™Р В Р’В¦Р В Р’пїЅР В Р вЂЎ Р В РІР‚СљР В Р’В Р В РЎвЂ™Р В Р’В¤Р В Р’пїЅР В РЎв„ўР В РЎвЂєР В РІР‚в„ў ===============
        charts_info = {
            'generated': False,
            'count': 0,
            'errors': [],
            'status': 'pending'
        }
        # Charts are generated via /api/charts to avoid blocking /upload.
        # =================================================

        

        # Р В РЎСџР В РЎвЂўР В РўвЂР РЋР С“Р РЋРІР‚РЋР В РЎвЂР РЋРІР‚С™Р РЋРІР‚в„–Р В Р вЂ Р В Р’В°Р В Р’ВµР В РЎпїЅ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂР В РЎвЂќР РЋРЎвЂњ Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎвЂўР РЋРІР‚С™Р В Р вЂ Р В Р’ВµР РЋРІР‚С™Р В Р’В°

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

        

        # Р В РЎвЂєР В РЎвЂ”Р РЋР вЂљР В Р’ВµР В РўвЂР В Р’ВµР В Р’В»Р РЋР РЏР В Р’ВµР В РЎпїЅ Р В РЎвЂР В РЎпїЅР В Р’ВµР В Р вЂ¦Р В Р’В° Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р В РЎвЂўР В Р вЂ  Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋР С“Р В РЎвЂќР В Р’В°Р РЋРІР‚РЋР В РЎвЂР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР РЋР РЏ

        analysis_filename = f"{Path(filename).stem}_analysis.json"

        

        response_data = {

            'success': True,

            'message': f'Р В Р’В¤Р В Р’В°Р В РІвЂћвЂ“Р В Р’В» "{filename}" Р РЋРЎвЂњР РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІвЂљВ¬Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂўР В Р’В±Р РЋР вЂљР В Р’В°Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р В Р’В°Р В Р вЂ¦',

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



def _sanitize_combined_value(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _sanitize_combined_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_combined_value(v) for v in value]
    return value


# Фоновая генерация общего отчёта: статус храним в файлах, чтобы работало при нескольких воркерах/релоаде
COMBINED_JOBS_DIR = ANALYSIS_RESULTS_DIR / "combined_jobs"


def _combined_job_path(job_id):
    safe_id = re.sub(r"[^a-zA-Z0-9\-]", "", job_id)
    if not safe_id:
        safe_id = "unknown"
    return COMBINED_JOBS_DIR / f"{safe_id}.json"


def _read_combined_job(job_id):
    path = _combined_job_path(job_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_combined_job(job_id, data):
    COMBINED_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = _combined_job_path(job_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=None)
    except Exception:
        pass


def _run_combined_report_job(job_id, file_map):
    print(f"[Combined report] Job {job_id} started.", flush=True)
    try:
        result = generate_combined_report(
            master_file=Path(file_map['master']),
            stock_report_file=Path(file_map['stock']),
            order_picked_file=Path(file_map['order_picked']),
            stock_movements_file=Path(file_map['movements']),
            picking_lines_file=Path(file_map['lines']),
            abc_analysis_file=Path(file_map['abc']),
            output_dir=ANALYSIS_RESULTS_DIR
        )
        _write_combined_job(job_id, {
            'status': 'ready',
            'report_file': result.file_path.name,
            'rows': _sanitize_combined_value(result.rows)
        })
        print(f"[Combined report] Job {job_id} finished successfully.", flush=True)
    except Exception as e:
        err_msg = str(e)
        traceback.print_exc()
        print(f"[Combined report] Job {job_id} ERROR: {err_msg}", flush=True)
        try:
            _write_combined_job(job_id, {
                'status': 'error',
                'error': err_msg
            })
        except Exception as write_err:
            print(f"[Combined report] Failed to write job error state: {write_err}", flush=True)


@app.route('/upload-combined', methods=['POST'])
def upload_combined():
    """Загрузка Excel файлов, запуск формирования отчёта в фоне, немедленный ответ с job_id."""
    try:
        def save_uploaded(file_obj):
            filename = secure_filename(file_obj.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file_obj.save(filepath)
            return filepath

        file_map = {}

        named_files = {
            'master': request.files.get('master_file'),
            'movements': request.files.get('movements_file'),
            'lines': request.files.get('lines_file'),
            'abc': request.files.get('abc_file'),
            'order_picked': request.files.get('order_picked_file'),
            'stock': request.files.get('stock_file'),
        }

        if any(f and f.filename for f in named_files.values()):
            missing_named = [key for key, f in named_files.items() if not f or not f.filename]
            if missing_named:
                return jsonify({
                    'success': False,
                    'error': 'Не все обязательные файлы загружены',
                    'missing': missing_named
                }), 400

            for key, file_obj in named_files.items():
                if not allowed_file(file_obj.filename):
                    return jsonify({
                        'success': False,
                        'error': f'Недопустимый формат файла для {key}. Разрешены только .xls/.xlsx'
                    }), 400
                file_map[key] = save_uploaded(file_obj)

        if not file_map:
            files = request.files.getlist('files')
            if not files:
                return jsonify({'success': False, 'error': 'Файлы не найдены в запросе'}), 400

            saved_files = []
            for file_obj in files:
                if file_obj and allowed_file(file_obj.filename):
                    saved_files.append({
                        'path': save_uploaded(file_obj),
                        'original_name': file_obj.filename,
                    })

            if not saved_files:
                return jsonify({'success': False, 'error': 'Нет валидных Excel файлов (.xls, .xlsx)'}), 400

            def normalize_name(value: str) -> str:
                return re.sub(r"[^0-9a-z\u0430-\u044f]+", "", value.lower())

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

        job_id = str(uuid.uuid4())
        _write_combined_job(job_id, {'status': 'processing'})

        thread = threading.Thread(
            target=_run_combined_report_job,
            args=(job_id, file_map),
            daemon=True
        )
        thread.start()

        return jsonify({
            'success': True,
            'job_id': job_id
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload-combined-status/<job_id>')
def upload_combined_status(job_id):
    """Статус фоновой генерации общего отчёта: processing | ready | error."""
    data = _read_combined_job(job_id)
    if not data:
        return jsonify({'status': 'processing'})
    return jsonify(data)


@app.route('/download-report/<path:filename>')
def download_report(filename):
    """РЎРєР°С‡РёРІР°РЅРёРµ СЃС„РѕСЂРјРёСЂРѕРІР°РЅРЅРѕРіРѕ РѕР±С‰РµРіРѕ РѕС‚С‡РµС‚Р°."""
    try:
        return send_from_directory(ANALYSIS_RESULTS_DIR, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 404


@app.route('/api/warehouse-map', methods=['GET'])
def get_warehouse_map():
    """Return warehouse layout data extracted from the latest JSON source file."""
    try:
        source_dirs = [
            OUTPUT_JSON_DIR,
            PARENT_DIR / OUTPUT_JSON_FOLDER,
        ]

        json_files = []
        for directory in source_dirs:
            if directory.exists():
                json_files.extend(directory.glob('*.json'))

        json_files = sorted(
            set(json_files),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        if not json_files:
            return jsonify({
                'success': False,
                'error': 'Файлы данных не найдены'
            }), 404

        chosen_file = None
        locations = []
        for candidate in json_files[:10]:
            extracted = extract_locations_from_json_file(candidate)
            if extracted:
                chosen_file = candidate
                locations = extracted
                break

        if not locations or chosen_file is None:
            return jsonify({
                'success': False,
                'error': 'В данных нет валидных локаций склада'
            }), 404

        aisles = sorted({item['aisle'] for item in locations})
        places = sorted({item['place'] for item in locations})
        levels = sorted({item['level'] for item in locations})

        return jsonify({
            'success': True,
            'meta': {
                'source_file': chosen_file.name,
                'updated_at': datetime.fromtimestamp(chosen_file.stat().st_mtime).isoformat(),
                'locations_count': len(locations),
                'aisles_count': len(aisles),
                'places_count': len(places),
                'levels_count': len(levels),
            },
            'locations': locations
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/warehouse-stock-colors', methods=['GET'])
def get_warehouse_stock_colors():
    """Return stock colors by aisle/place from the latest combined report."""
    try:
        report_files = sorted(
            ANALYSIS_RESULTS_DIR.glob('combined_report_*.xlsx'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        if not report_files:
            return jsonify({'success': False, 'error': 'Файл общего отчета не найден'}), 404

        latest_file = report_files[0]
        df = pd.read_excel(latest_file, sheet_name=0)

        if df is None or df.empty:
            return jsonify({'success': False, 'error': 'Последний общий отчет пустой'}), 404

        aisle_col = 'Аллея пикинг'
        place_col = 'Место пикинг'
        stock_col = 'Мертвый сток'

        if aisle_col not in df.columns or place_col not in df.columns or stock_col not in df.columns:
            return jsonify({
                'success': False,
                'error': 'В отчете отсутствуют нужные колонки для схемы'
            }), 400

        color_rank = {'green': 1, 'yellow': 2, 'red': 3}
        colors = {}

        for _, row in df.iterrows():
            aisle = parse_aisle_from_value(row.get(aisle_col))
            place = parse_place_from_value(row.get(place_col))
            color = normalize_stock_color(row.get(stock_col))

            if aisle is None or place is None or color is None:
                continue
            if aisle < 742 or aisle > 748:
                continue
            if place < 1 or place > 63:
                continue

            key = f'{aisle}-{place}'
            existing = colors.get(key)
            if existing is None or color_rank[color] > color_rank.get(existing, 0):
                colors[key] = color

        return jsonify({
            'success': True,
            'report_file': latest_file.name,
            'updated_at': datetime.fromtimestamp(latest_file.stat().st_mtime).isoformat(),
            'colors': colors
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/warehouse-layout-from-report', methods=['POST'])
def warehouse_layout_from_report():
    """Build warehouse aisle/place layout and stock colors from uploaded combined report."""
    try:
        if 'report_file' not in request.files:
            return jsonify({'success': False, 'error': 'Файл отчета не найден в запросе'}), 400

        report_file = request.files['report_file']
        if not report_file or not report_file.filename:
            return jsonify({'success': False, 'error': 'Файл отчета не выбран'}), 400

        if not allowed_file(report_file.filename):
            return jsonify({'success': False, 'error': 'Разрешены только файлы Excel (.xls, .xlsx)'}), 400

        temp_name = f"warehouse_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(report_file.filename)}"
        temp_path = UPLOAD_DIR / temp_name
        report_file.save(str(temp_path))

        try:
            df = pd.read_excel(temp_path, sheet_name=0)
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass

        if df is None or df.empty:
            return jsonify({'success': False, 'error': 'Загруженный отчет пустой'}), 400

        aisle_col = find_dataframe_column(df.columns, ['Аллея пикинг', 'Аллея', 'aisle'])
        place_col = find_dataframe_column(df.columns, ['Место пикинг', 'Место', 'place'])
        stock_col = find_dataframe_column(df.columns, ['Мертвый сток', 'Мёртвый сток', 'dead stock'])

        if aisle_col is None or place_col is None:
            return jsonify({
                'success': False,
                'error': 'В отчете нет колонок аллеи/места пикинга'
            }), 400

        colors = {}
        by_aisle_places = {}

        for _, row in df.iterrows():
            aisle = parse_aisle_from_value(row.get(aisle_col))
            place = parse_place_from_value(row.get(place_col))
            if aisle is None or place is None:
                continue
            if place < 1:
                continue

            if aisle not in by_aisle_places:
                by_aisle_places[aisle] = set()
            by_aisle_places[aisle].add(place)

            if stock_col is None:
                continue

            color = normalize_stock_color(row.get(stock_col))
            if color is None:
                continue

            key = f'{aisle}-{place}'
            if key not in colors:
                colors[key] = color

        if not by_aisle_places:
            return jsonify({'success': False, 'error': 'В отчете не найдено валидных ячеек пикинга'}), 400

        aisles = sorted(by_aisle_places.keys(), reverse=True)
        layout = []
        global_max_place = 1
        for aisle in aisles:
            max_place = max(by_aisle_places[aisle]) if by_aisle_places[aisle] else 1
            layout.append({'aisle': int(aisle), 'max_place': int(max_place)})
            if max_place > global_max_place:
                global_max_place = max_place

        return jsonify({
            'success': True,
            'layout': layout,
            'global_max_place': int(global_max_place),
            'colors': colors
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis-data', methods=['GET'])
def get_analysis_data():
    """API РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РґР°РЅРЅС‹С… Р°РЅР°Р»РёР·Р° РёР· РѕСЃРЅРѕРІРЅРѕР№ Р‘Р”"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'Р‘Р°Р·Р° РґР°РЅРЅС‹С… РЅРµРґРѕСЃС‚СѓРїРЅР°'}), 500

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
    """РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ РґР°РЅРЅС‹С… РІ РѕСЃРЅРѕРІРЅРѕР№ Р‘Р”"""
    if not DB_AVAILABLE:
        return jsonify({'has_data': False, 'error': 'Р‘Р°Р·Р° РґР°РЅРЅС‹С… РЅРµРґРѕСЃС‚СѓРїРЅР°'}), 500

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
    """РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ РґР°РЅРЅС‹С… Р°РЅР°Р»РёР·Р° РІ РѕСЃРЅРѕРІРЅРѕР№ Р‘Р”"""
    if not DB_AVAILABLE:
        return jsonify({'has_data': False, 'error': 'Р‘Р°Р·Р° РґР°РЅРЅС‹С… РЅРµРґРѕСЃС‚СѓРїРЅР°'}), 500

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
    """API РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РёР»Рё РіРµРЅРµСЂР°С†РёРё РіСЂР°С„РёРєРѕРІ"""
    if not CHARTS_AVAILABLE:
        return jsonify({'success': False, 'error': 'chart_generator_not_available'}), 500

    # РЎРЅР°С‡Р°Р»Р° РїСЂРѕР±СѓРµРј РїРѕР»СѓС‡РёС‚СЊ СЃРѕС…СЂР°РЅРµРЅРЅС‹Рµ РіСЂР°С„РёРєРё
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
            # РџС‹С‚Р°РµРјСЃСЏ СЃРѕС…СЂР°РЅРёС‚СЊ РіСЂР°С„РёРєРё РІ Р‘Р” Р°РЅР°Р»РёР·Р°
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
    """API РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ СЃС‚Р°С‚РёСЃС‚РёРєРё Р°РЅР°Р»РёР·Р°"""
    # РћСЃРЅРѕРІРЅРѕР№ РІР°СЂРёР°РЅС‚: СЃС‚Р°С‚РёСЃС‚РёРєР° РёР· РѕСЃРЅРѕРІРЅРѕР№ Р‘Р”
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

    # Р РµР·РµСЂРІРЅС‹Р№ РІР°СЂРёР°РЅС‚: СЃС‚Р°С‚РёСЃС‚РёРєР° РёР· Р‘Р” Р°РЅР°Р»РёР·Р°
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
    """API С‡Р°С‚-Р°СЃСЃРёСЃС‚РµРЅС‚Р° РїРѕ СЃРєР»Р°РґСЃРєРѕР№ Р»РѕРіРёСЃС‚РёРєРµ"""
    if chat_assistant is None:
        return jsonify({
            'success': False,
            'error': 'chat_assistant_not_available',
            'answer': 'Р’ Р±Р°Р·Рµ РґР°РЅРЅС‹С… РЅРµС‚ РёРЅС„РѕСЂРјР°С†РёРё РґР»СЏ РѕС‚РІРµС‚Р° РЅР° СЌС‚РѕС‚ РІРѕРїСЂРѕСЃ.'
        }), 500

    try:
        payload = request.get_json(silent=True) or {}
        message = (payload.get('message') or '').strip()
        history = payload.get('history') or []

        if not message:
            return jsonify({
                'success': True,
                'answer': 'Р’ Р±Р°Р·Рµ РґР°РЅРЅС‹С… РЅРµС‚ РёРЅС„РѕСЂРјР°С†РёРё РґР»СЏ РѕС‚РІРµС‚Р° РЅР° СЌС‚РѕС‚ РІРѕРїСЂРѕСЃ.',
                'meta': {'source': 'guard'}
            })

        result = chat_assistant.answer(message, history=history)
        return jsonify({
            'success': True,
            'answer': result.get('answer') or 'Р’ Р±Р°Р·Рµ РґР°РЅРЅС‹С… РЅРµС‚ РёРЅС„РѕСЂРјР°С†РёРё РґР»СЏ РѕС‚РІРµС‚Р° РЅР° СЌС‚РѕС‚ РІРѕРїСЂРѕСЃ.',
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
            'answer': 'Р’ Р±Р°Р·Рµ РґР°РЅРЅС‹С… РЅРµС‚ РёРЅС„РѕСЂРјР°С†РёРё РґР»СЏ РѕС‚РІРµС‚Р° РЅР° СЌС‚РѕС‚ РІРѕРїСЂРѕСЃ.'
        }), 500


@app.route('/api/delete-by-file', methods=['POST'])
def delete_by_file():
    """РЈРґР°Р»РµРЅРёРµ РґР°РЅРЅС‹С… РёР· Р‘Р” РїРѕ Excel С„Р°Р№Р»Сѓ"""
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'Р‘Р°Р·Р° РґР°РЅРЅС‹С… РЅРµРґРѕСЃС‚СѓРїРЅР°'}), 500

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Р¤Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ РІ Р·Р°РїСЂРѕСЃРµ'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'success': False, 'error': 'Р¤Р°Р№Р» РЅРµ РІС‹Р±СЂР°РЅ'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Р Р°Р·СЂРµС€РµРЅС‹ С‚РѕР»СЊРєРѕ С„Р°Р№Р»С‹ Excel (.xls, .xlsx)'}), 400

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
        return jsonify({'success': False, 'error': f'РћС€РёР±РєР° С‡С‚РµРЅРёСЏ Excel: {str(e)}'}), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

    if df is None or df.empty:
        return jsonify({'success': False, 'error': 'Р¤Р°Р№Р» РїСѓСЃС‚РѕР№ РёР»Рё РЅРµ СЃРѕРґРµСЂР¶РёС‚ РґР°РЅРЅС‹С…'}), 400

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
        value = value.replace('С‘', 'Рµ')
        for ch in [' ', '\t', '\n', '\r', '.', ',', '-', '_', '/', '\\', '(', ')', '[', ']', '{', '}', '"', "'"]:
            value = value.replace(ch, '')
        return value

    normalized_columns = [normalize_col(col) for col in columns]

    name_patterns = [
        'РЅР°РёРјРµРЅ', 'РЅР°РёРјРµРЅРѕРІР°РЅ', 'С‚РѕРІР°СЂ', 'РЅРѕРјРµРЅРєР»Р°С‚СѓСЂ', 'product', 'productname',
        'РїРѕР·РёС†РёСЏ', 'item', 'title'
    ]
    id_patterns = [
        'id', 'Р°СЂС‚РёРєСѓР»', 'sku', 'article', 'РєРѕРґ', 'productid', 'С€С‚СЂРёС…РєРѕРґ', 'barcode', 'ean'
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
            'error': 'РќРµ СѓРґР°Р»РѕСЃСЊ РѕРїСЂРµРґРµР»РёС‚СЊ СЃС‚РѕР»Р±С†С‹ СЃ ID РёР»Рё РЅР°РёРјРµРЅРѕРІР°РЅРёРµРј С‚РѕРІР°СЂР°',
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

        # Р•СЃР»Рё РІСЃРµ СѓРґР°Р»РµРЅРѕ, СЃР±СЂР°СЃС‹РІР°РµРј СЃС‡РµС‚С‡РёРєРё ID
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
    app.run(host='0.0.0.0', port=8002, debug=True)

