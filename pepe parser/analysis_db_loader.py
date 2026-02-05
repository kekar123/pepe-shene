# analysis_db_loader.py

import sqlite3
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalysisDBLoader:
    def __init__(self, db_path: str = "analysis_visualization.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ Р±Р°Р·С‹ РґР°РЅРЅС‹С…"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # РЎРѕР·РґР°РµРј С‚Р°Р±Р»РёС†С‹ РЅР°РїСЂСЏРјСѓСЋ
                self.create_tables_directly(conn)
                
                logger.info(f"вњ… Р‘Р°Р·Р° РґР°РЅРЅС‹С… Р°РЅР°Р»РёР·Р° РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅР°: {self.db_path}")
                
        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° РёРЅРёС†РёР°Р»РёР·Р°С†РёРё Р‘Р” Р°РЅР°Р»РёР·Р°: {e}")
            raise
    
    def create_tables_directly(self, conn: sqlite3.Connection):
        """РЎРѕР·РґР°РЅРёРµ С‚Р°Р±Р»РёС† РЅР°РїСЂСЏРјСѓСЋ"""
        # РўР°Р±Р»РёС†Р° РґР»СЏ С„Р°Р№Р»РѕРІ Р°РЅР°Р»РёР·Р°
        conn.execute('''
        CREATE TABLE IF NOT EXISTS analysis_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename VARCHAR(255) NOT NULL,
            file_path TEXT,
            analysis_type VARCHAR(50) NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            rows_count INTEGER DEFAULT 0
        )
        ''')
        
        # РћСЃРЅРѕРІРЅР°СЏ С‚Р°Р±Р»РёС†Р° РґР»СЏ РїСЂРѕРґСѓРєС‚РѕРІ
        conn.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code VARCHAR(200),
            product_name TEXT NOT NULL,
            category VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_code, product_name)
        )
        ''')
        
        # РўР°Р±Р»РёС†Р° РґР»СЏ РґР°РЅРЅС‹С… Р°РЅР°Р»РёР·Р°
        conn.execute('''
        CREATE TABLE IF NOT EXISTS analysis_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_file_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity DECIMAL(15, 3) DEFAULT 0,
            revenue DECIMAL(15, 2) DEFAULT 0,
            abc_category CHAR(1),
            xyz_category CHAR(1),
            abc_xyz_category CHAR(3),
            rank INTEGER,
            analysis_date DATE NOT NULL,
            FOREIGN KEY (analysis_file_id) REFERENCES analysis_files(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            UNIQUE(analysis_file_id, product_id)
        )
        ''')
        
        # РўР°Р±Р»РёС†Р° РґР»СЏ РјР°С‚СЂРёС†С‹ ABC-XYZ
        conn.execute('''
        CREATE TABLE IF NOT EXISTS matrix_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_file_id INTEGER NOT NULL,
            abc_category CHAR(1),
            xyz_category CHAR(1),
            abc_xyz_category CHAR(3),
            products_count INTEGER DEFAULT 0,
            total_revenue DECIMAL(15, 2) DEFAULT 0,
            avg_revenue DECIMAL(15, 2) DEFAULT 0,
            recommendation TEXT,
            FOREIGN KEY (analysis_file_id) REFERENCES analysis_files(id) ON DELETE CASCADE,
            UNIQUE(analysis_file_id, abc_xyz_category)
        )
        ''')
        
        # РўР°Р±Р»РёС†Р° РґР»СЏ РѕР±С‰РµР№ СЃС‚Р°С‚РёСЃС‚РёРєРё
        conn.execute('''
        CREATE TABLE IF NOT EXISTS analysis_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_file_id INTEGER NOT NULL,
            total_products INTEGER DEFAULT 0,
            total_revenue DECIMAL(15, 2) DEFAULT 0,
            avg_revenue DECIMAL(15, 2) DEFAULT 0,
            a_count INTEGER DEFAULT 0,
            b_count INTEGER DEFAULT 0,
            c_count INTEGER DEFAULT 0,
            x_count INTEGER DEFAULT 0,
            y_count INTEGER DEFAULT 0,
            z_count INTEGER DEFAULT 0,
            top_product_name TEXT,
            top_product_revenue DECIMAL(15, 2) DEFAULT 0,
            analysis_date DATE NOT NULL,
            FOREIGN KEY (analysis_file_id) REFERENCES analysis_files(id) ON DELETE CASCADE,
            UNIQUE(analysis_file_id)
        )
        ''')
        
        # РўР°Р±Р»РёС†Р° РґР»СЏ РіСЂР°С„РёРєРѕРІ
        conn.execute('''
        CREATE TABLE IF NOT EXISTS charts_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_file_id INTEGER NOT NULL,
            chart_type VARCHAR(50) NOT NULL,
            chart_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_file_id) REFERENCES analysis_files(id) ON DELETE CASCADE,
            UNIQUE(analysis_file_id, chart_type)
        )
        ''')
        
        # РРЅРґРµРєСЃС‹
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_analysis_data_file ON analysis_data(analysis_file_id)",
            "CREATE INDEX IF NOT EXISTS idx_analysis_data_product ON analysis_data(product_id)",
            "CREATE INDEX IF NOT EXISTS idx_analysis_data_abc ON analysis_data(abc_category)",
            "CREATE INDEX IF NOT EXISTS idx_analysis_data_xyz ON analysis_data(xyz_category)",
            "CREATE INDEX IF NOT EXISTS idx_matrix_stats_category ON matrix_stats(abc_xyz_category)",
            "CREATE INDEX IF NOT EXISTS idx_products_name ON products(product_name)"
        ]
        
        for index_sql in indexes:
            conn.execute(index_sql)
        
        conn.commit()
        logger.info("вњ… Р’СЃРµ С‚Р°Р±Р»РёС†С‹ Р‘Р” Р°РЅР°Р»РёР·Р° СЃРѕР·РґР°РЅС‹")
    
    def load_analysis_from_json(self, analysis_file_path: str, analysis_type: str = "abc_xyz") -> Dict:
        """
        Р—Р°РіСЂСѓР¶Р°РµС‚ РґР°РЅРЅС‹Рµ Р°РЅР°Р»РёР·Р° РёР· JSON С„Р°Р№Р»Р° РІ Р‘Р”
        
        Args:
            analysis_file_path: РџСѓС‚СЊ Рє JSON С„Р°Р№Р»Сѓ СЃ Р°РЅР°Р»РёР·РѕРј
            analysis_type: РўРёРї Р°РЅР°Р»РёР·Р° (abc, xyz, abc_xyz)
            
        Returns:
            РЎР»РѕРІР°СЂСЊ СЃ СЂРµР·СѓР»СЊС‚Р°С‚Р°РјРё Р·Р°РіСЂСѓР·РєРё
        """
        results = {
            "success": False,
            "analysis_file_id": None,
            "products_loaded": 0,
            "analysis_data_loaded": 0,
            "errors": [],
            "stats": {}
        }
        
        try:
            # Р§РёС‚Р°РµРј JSON С„Р°Р№Р»
            analysis_data = None
            read_error = None
            for encoding in ("utf-8", "utf-8-sig", "cp1251"):
                try:
                    with open(analysis_file_path, 'r', encoding=encoding) as f:
                        analysis_data = json.load(f)
                    read_error = None
                    break
                except UnicodeDecodeError as e:
                    read_error = e
                    continue
                except json.JSONDecodeError:
                    break

            if analysis_data is None:
                raise read_error if read_error else ValueError("Не удалось прочитать JSON файл")
            
            logger.info(f"рџ“Ґ Р—Р°РіСЂСѓР·РєР° Р°РЅР°Р»РёР·Р° РёР· {analysis_file_path}")
            
            # РџСЂРѕРІРµСЂСЏРµРј С„РѕСЂРјР°С‚ РґР°РЅРЅС‹С…
            if isinstance(analysis_data, dict):
                if "results" in analysis_data and isinstance(analysis_data["results"], list):
                    analysis_data = analysis_data["results"]
                elif "data" in analysis_data and isinstance(analysis_data["data"], list):
                    analysis_data = analysis_data["data"]

            if not isinstance(analysis_data, list):
                results["errors"].append("РќРµРїСЂР°РІРёР»СЊРЅС‹Р№ С„РѕСЂРјР°С‚ РґР°РЅРЅС‹С…. РћР¶РёРґР°РµС‚СЃСЏ СЃРїРёСЃРѕРє.")
                return results
            
            # РЎРѕР·РґР°РµРј Р·Р°РїРёСЃСЊ Рѕ С„Р°Р№Р»Рµ
            filename = os.path.basename(analysis_file_path)
            analysis_id = self._create_analysis_file(filename, analysis_file_path, analysis_type, len(analysis_data))
            
            if not analysis_id:
                results["errors"].append("РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ Р·Р°РїРёСЃСЊ Рѕ С„Р°Р№Р»Рµ Р°РЅР°Р»РёР·Р°")
                return results
            
            results["analysis_file_id"] = analysis_id
            
            # РћР±СЂР°Р±Р°С‚С‹РІР°РµРј РґР°РЅРЅС‹Рµ
            return self._process_analysis_data(analysis_id, analysis_data, results)
                
        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё Р°РЅР°Р»РёР·Р°: {e}")
            import traceback
            traceback.print_exc()
            results["errors"].append(str(e))
            return results
    
    def _create_analysis_file(self, filename: str, file_path: str, analysis_type: str, rows_count: int) -> Optional[int]:
        """РЎРѕР·РґР°РµС‚ Р·Р°РїРёСЃСЊ Рѕ С„Р°Р№Р»Рµ Р°РЅР°Р»РёР·Р°"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO analysis_files 
                (filename, file_path, analysis_type, rows_count)
                VALUES (?, ?, ?, ?)
                ''', (filename, file_path, analysis_type, rows_count))
                
                file_id = cursor.lastrowid
                conn.commit()
                return file_id
                
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ Р·Р°РїРёСЃРё Рѕ С„Р°Р№Р»Рµ: {e}")
            return None
    
    def _process_analysis_data(self, analysis_id: int, data: List[Dict], results: Dict) -> Dict:
        """РћР±СЂР°Р±Р°С‚С‹РІР°РµС‚ РґР°РЅРЅС‹Рµ Р°РЅР°Р»РёР·Р°"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # РЎРѕР±РёСЂР°РµРј СЃС‚Р°С‚РёСЃС‚РёРєСѓ
                abc_counts = {'A': 0, 'B': 0, 'C': 0}
                xyz_counts = {'X': 0, 'Y': 0, 'Z': 0}
                total_revenue = 0
                top_product = None
                top_revenue = 0
                
                # РњР°С‚СЂРёС†Р° РґР»СЏ СЃС‚Р°С‚РёСЃС‚РёРєРё
                matrix_data = {}
                
                for idx, item in enumerate(data):
                    try:
                        if not isinstance(item, dict):
                            continue
                            
                        # РР·РІР»РµРєР°РµРј РґР°РЅРЅС‹Рµ
                        product_name = item.get('name') or item.get('product_name') or f"РўРѕРІР°СЂ_{idx+1}"
                        product_code = item.get('product_code') or item.get('article') or f"CODE_{idx+1}"
                        revenue = float(item.get('revenue', 0))
                        quantity = float(item.get('quantity', 0))
                        abc_category = item.get('ABC') or item.get('abc_category') or 'C'
                        xyz_category = item.get('XYZ') or item.get('xyz_category') or 'Z'
                        abc_xyz_category = item.get('ABC_XYZ') or f"{abc_category}{xyz_category}"
                        
                        # РќРѕСЂРјР°Р»РёР·СѓРµРј РєР°С‚РµРіРѕСЂРёРё
                        abc_category = abc_category.upper()[:1]
                        xyz_category = xyz_category.upper()[:1]
                        abc_xyz_category = abc_xyz_category.upper()[:2]
                        
                        # РџРѕР»СѓС‡Р°РµРј РёР»Рё СЃРѕР·РґР°РµРј РїСЂРѕРґСѓРєС‚
                        product_id = self._get_or_create_product(cursor, product_code, product_name)
                        
                        if product_id:
                            results["products_loaded"] += 1
                            
                            # РЎРѕС…СЂР°РЅСЏРµРј РґР°РЅРЅС‹Рµ Р°РЅР°Р»РёР·Р°
                            cursor.execute('''
                            INSERT OR REPLACE INTO analysis_data 
                            (analysis_file_id, product_id, quantity, revenue, 
                             abc_category, xyz_category, abc_xyz_category,
                             rank, analysis_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                analysis_id,
                                product_id,
                                quantity,
                                revenue,
                                abc_category,
                                xyz_category,
                                abc_xyz_category,
                                idx + 1,
                                datetime.now().strftime("%Y-%m-%d")
                            ))
                            
                            results["analysis_data_loaded"] += 1
                            
                            # РћР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚РёСЃС‚РёРєСѓ
                            if abc_category in abc_counts:
                                abc_counts[abc_category] += 1
                            if xyz_category in xyz_counts:
                                xyz_counts[xyz_category] += 1
                                
                            total_revenue += revenue
                            
                            # РћРїСЂРµРґРµР»СЏРµРј С‚РѕРї РїСЂРѕРґСѓРєС‚
                            if revenue > top_revenue:
                                top_revenue = revenue
                                top_product = product_name
                            
                            # РћР±РЅРѕРІР»СЏРµРј РјР°С‚СЂРёС†Сѓ
                            matrix_key = abc_xyz_category
                            if matrix_key not in matrix_data:
                                matrix_data[matrix_key] = {
                                    'count': 0,
                                    'total_revenue': 0
                                }
                            
                            matrix_data[matrix_key]['count'] += 1
                            matrix_data[matrix_key]['total_revenue'] += revenue
                    
                    except Exception as e:
                        error_msg = f"РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё С‚РѕРІР°СЂР° {idx+1}: {str(e)}"
                        results["errors"].append(error_msg)
                        logger.warning(error_msg)
                
                # РЎРѕС…СЂР°РЅСЏРµРј СЃС‚Р°С‚РёСЃС‚РёРєСѓ РјР°С‚СЂРёС†С‹
                for matrix_key, data in matrix_data.items():
                    abc_cat = matrix_key[0] if len(matrix_key) > 0 else 'C'
                    xyz_cat = matrix_key[1] if len(matrix_key) > 1 else 'Z'
                    
                    cursor.execute('''
                    INSERT OR REPLACE INTO matrix_stats 
                    (analysis_file_id, abc_category, xyz_category, abc_xyz_category,
                     products_count, total_revenue, avg_revenue, recommendation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        analysis_id,
                        abc_cat,
                        xyz_cat,
                        matrix_key,
                        data['count'],
                        data['total_revenue'],
                        data['total_revenue'] / data['count'] if data['count'] > 0 else 0,
                        self._get_recommendation(matrix_key)
                    ))
                
                # РЎРѕС…СЂР°РЅСЏРµРј РѕР±С‰СѓСЋ СЃС‚Р°С‚РёСЃС‚РёРєСѓ
                avg_revenue = total_revenue / len(data) if data else 0
                
                cursor.execute('''
                INSERT OR REPLACE INTO analysis_stats 
                (analysis_file_id, total_products, total_revenue, avg_revenue,
                 a_count, b_count, c_count, x_count, y_count, z_count,
                 top_product_name, top_product_revenue, analysis_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    analysis_id,
                    len(data),
                    total_revenue,
                    avg_revenue,
                    abc_counts.get('A', 0),
                    abc_counts.get('B', 0),
                    abc_counts.get('C', 0),
                    xyz_counts.get('X', 0),
                    xyz_counts.get('Y', 0),
                    xyz_counts.get('Z', 0),
                    top_product,
                    top_revenue,
                    datetime.now().strftime("%Y-%m-%d")
                ))
                
                conn.commit()
                
                results["success"] = True
                results["stats"] = {
                    "total_products": len(data),
                    "total_revenue": total_revenue,
                    "abc_counts": abc_counts,
                    "xyz_counts": xyz_counts
                }
                
                logger.info(f"вњ… Р—Р°РіСЂСѓР¶РµРЅРѕ: {results['products_loaded']} С‚РѕРІР°СЂРѕРІ, {results['analysis_data_loaded']} Р·Р°РїРёСЃРµР№")
                return results
                
        except Exception as e:
            logger.error(f"вќЊ РљСЂРёС‚РёС‡РµСЃРєР°СЏ РѕС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё: {e}")
            results["errors"].append(str(e))
            return results
    
    def _get_or_create_product(self, cursor, product_code: str, product_name: str) -> Optional[int]:
        """РџРѕР»СѓС‡Р°РµС‚ РёР»Рё СЃРѕР·РґР°РµС‚ РїСЂРѕРґСѓРєС‚"""
        try:
            # РџСЂРѕР±СѓРµРј РЅР°Р№С‚Рё РїРѕ РёРјРµРЅРё
            cursor.execute(
                "SELECT id FROM products WHERE product_name = ?", 
                (product_name,)
            )
            result = cursor.fetchone()
            if result:
                return result[0]
            
            # РЎРѕР·РґР°РµРј РЅРѕРІС‹Р№ РїСЂРѕРґСѓРєС‚
            cursor.execute('''
            INSERT INTO products 
            (product_code, product_name)
            VALUES (?, ?)
            ''', (product_code, product_name))
            
            return cursor.lastrowid
            
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ РїСЂРѕРґСѓРєС‚Р° {product_name}: {e}")
            return None
    
    def _get_recommendation(self, category: str) -> str:
        """Р“РµРЅРµСЂРёСЂСѓРµС‚ СЂРµРєРѕРјРµРЅРґР°С†РёСЋ РґР»СЏ РєР°С‚РµРіРѕСЂРёРё"""
        recommendations = {
            'AX': 'Р’С‹СЃРѕРєРёР№ РїСЂРёРѕСЂРёС‚РµС‚, СЃС‚Р°Р±РёР»СЊРЅС‹Р№ СЃРїСЂРѕСЃ. РњР°РєСЃРёРјР°Р»СЊРЅС‹Рµ Р·Р°РїР°СЃС‹, Р·РѕР»РѕС‚Р°СЏ Р·РѕРЅР° СЃРєР»Р°РґР°.',
            'AY': 'Р’С‹СЃРѕРєРёР№ РїСЂРёРѕСЂРёС‚РµС‚, СЃРµР·РѕРЅРЅС‹Р№ СЃРїСЂРѕСЃ. РџР»Р°РЅРёСЂРѕРІР°РЅРёРµ Р·Р°РїР°СЃРѕРІ РїРѕ СЃРµР·РѕРЅР°Рј.',
            'AZ': 'Р’С‹СЃРѕРєРёР№ РїСЂРёРѕСЂРёС‚РµС‚, РЅРµСЂРµРіСѓР»СЏСЂРЅС‹Р№ СЃРїСЂРѕСЃ. Р Р°Р±РѕС‚Р° РїРѕРґ Р·Р°РєР°Р·, РјРёРЅРёРјР°Р»СЊРЅС‹Рµ Р·Р°РїР°СЃС‹.',
            'BX': 'РЎСЂРµРґРЅРёР№ РїСЂРёРѕСЂРёС‚РµС‚, СЃС‚Р°Р±РёР»СЊРЅС‹Р№ СЃРїСЂРѕСЃ. РћРїС‚РёРјР°Р»СЊРЅС‹Рµ Р·Р°РїР°СЃС‹, СЃСЂРµРґРЅСЏСЏ Р·РѕРЅР°.',
            'BY': 'РЎСЂРµРґРЅРёР№ РїСЂРёРѕСЂРёС‚РµС‚, СЃРµР·РѕРЅРЅС‹Р№ СЃРїСЂРѕСЃ. Р—Р°РїР°СЃС‹ РЅР° 1-2 СЃРµР·РѕРЅР° РІРїРµСЂРµРґ.',
            'BZ': 'РЎСЂРµРґРЅРёР№ РїСЂРёРѕСЂРёС‚РµС‚, РЅРµСЂРµРіСѓР»СЏСЂРЅС‹Р№ СЃРїСЂРѕСЃ. РњРёРЅРёРјР°Р»СЊРЅС‹Рµ Р·Р°РїР°СЃС‹.',
            'CX': 'РќРёР·РєРёР№ РїСЂРёРѕСЂРёС‚РµС‚, СЃС‚Р°Р±РёР»СЊРЅС‹Р№ СЃРїСЂРѕСЃ. Р‘Р°Р·РѕРІР°СЏ СЃС‚СЂР°С…РѕРІРєР°, СѓРґР°Р»РµРЅРЅР°СЏ Р·РѕРЅР°.',
            'CY': 'РќРёР·РєРёР№ РїСЂРёРѕСЂРёС‚РµС‚, СЃРµР·РѕРЅРЅС‹Р№ СЃРїСЂРѕСЃ. Р—Р°РєСѓРїРєР° РїРѕ РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё.',
            'CZ': 'РќРёР·РєРёР№ РїСЂРёРѕСЂРёС‚РµС‚, РЅРµСЂРµРіСѓР»СЏСЂРЅС‹Р№ СЃРїСЂРѕСЃ. Р Р°СЃСЃРјРѕС‚СЂРµС‚СЊ РёСЃРєР»СЋС‡РµРЅРёРµ РёР· Р°СЃСЃРѕСЂС‚РёРјРµРЅС‚Р°.'
        }
        return recommendations.get(category.upper(), 'РћР±С‰РёРµ СЂРµРєРѕРјРµРЅРґР°С†РёРё РїРѕ СѓРїСЂР°РІР»РµРЅРёСЋ Р·Р°РїР°СЃР°РјРё.')
    
    def save_charts(self, analysis_file_id: int, charts: Dict) -> bool:
        """РЎРѕС…СЂР°РЅСЏРµС‚ РЅРµСЃРєРѕР»СЊРєРѕ РіСЂР°С„РёРєРѕРІ РІ Р‘Р”"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                saved_count = 0
                for chart_type, chart_data in charts.items():
                    cursor.execute('''
                    INSERT OR REPLACE INTO charts_data 
                    (analysis_file_id, chart_type, chart_data)
                    VALUES (?, ?, ?)
                    ''', (analysis_file_id, chart_type, chart_data))
                    saved_count += 1
                
                conn.commit()
                logger.info(f"вњ… РЎРѕС…СЂР°РЅРµРЅРѕ {saved_count} РіСЂР°С„РёРєРѕРІ РґР»СЏ Р°РЅР°Р»РёР·Р° {analysis_file_id}")
                return True
                
        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ РіСЂР°С„РёРєРѕРІ: {e}")
            return False
    
    def save_chart(self, analysis_file_id: int, chart_type: str, chart_data: str) -> bool:
        """РЎРѕС…СЂР°РЅСЏРµС‚ РѕРґРёРЅ РіСЂР°С„РёРє РІ Р‘Р”"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT OR REPLACE INTO charts_data 
                (analysis_file_id, chart_type, chart_data)
                VALUES (?, ?, ?)
                ''', (analysis_file_id, chart_type, chart_data))
                
                conn.commit()
                logger.info(f"вњ… Р“СЂР°С„РёРє {chart_type} СЃРѕС…СЂР°РЅРµРЅ РґР»СЏ Р°РЅР°Р»РёР·Р° {analysis_file_id}")
                return True
                
        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° СЃРѕС…СЂР°РЅРµРЅРёСЏ РіСЂР°С„РёРєР°: {e}")
            return False
    
    def get_charts(self, analysis_file_id: int = None) -> Dict:
        """РџРѕР»СѓС‡Р°РµС‚ СЃРѕС…СЂР°РЅРµРЅРЅС‹Рµ РіСЂР°С„РёРєРё"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if analysis_file_id:
                    cursor.execute('''
                    SELECT chart_type, chart_data 
                    FROM charts_data 
                    WHERE analysis_file_id = ?
                    ''', (analysis_file_id,))
                else:
                    # РџРѕР»СѓС‡Р°РµРј РїРѕСЃР»РµРґРЅРёР№ Р°РЅР°Р»РёР·
                    cursor.execute('''
                    SELECT cd.chart_type, cd.chart_data 
                    FROM charts_data cd
                    WHERE cd.analysis_file_id = (
                        SELECT MAX(id) FROM analysis_files
                    )
                    ''')
                
                charts = {}
                for row in cursor.fetchall():
                    chart_dict = dict(row)
                    charts[chart_dict['chart_type']] = chart_dict['chart_data']
                
                return charts
                
        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ РіСЂР°С„РёРєРѕРІ: {e}")
            return {}
    
    def get_analysis_data(self, analysis_file_id: int = None, limit: int = 100) -> List[Dict]:
        """РџРѕР»СѓС‡Р°РµС‚ РґР°РЅРЅС‹Рµ Р°РЅР°Р»РёР·Р° РґР»СЏ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ РІ С‚Р°Р±Р»РёС†Рµ"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if analysis_file_id:
                    cursor.execute('''
                    SELECT 
                        ad.id,
                        p.product_name,
                        p.product_code,
                        ad.quantity,
                        ad.revenue,
                        ad.abc_category,
                        ad.xyz_category,
                        ad.abc_xyz_category,
                        ad.rank
                    FROM analysis_data ad
                    JOIN products p ON ad.product_id = p.id
                    WHERE ad.analysis_file_id = ?
                    ORDER BY ad.revenue DESC, ad.rank ASC
                    LIMIT ?
                    ''', (analysis_file_id, limit))
                else:
                    # РџРѕР»СѓС‡Р°РµРј РїРѕСЃР»РµРґРЅРёР№ Р°РЅР°Р»РёР·
                    cursor.execute('''
                    SELECT 
                        ad.id,
                        p.product_name,
                        p.product_code,
                        ad.quantity,
                        ad.revenue,
                        ad.abc_category,
                        ad.xyz_category,
                        ad.abc_xyz_category,
                        ad.rank
                    FROM analysis_data ad
                    JOIN products p ON ad.product_id = p.id
                    WHERE ad.analysis_file_id = (
                        SELECT MAX(id) FROM analysis_files
                    )
                    ORDER BY ad.revenue DESC, ad.rank ASC
                    LIMIT ?
                    ''', (limit,))
                
                results = []
                for row in cursor.fetchall():
                    results.append(dict(row))
                
                return results
                
        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ РґР°РЅРЅС‹С… Р°РЅР°Р»РёР·Р°: {e}")
            return []
    
    def get_analysis_stats(self, analysis_file_id: int = None) -> Dict:
        """РџРѕР»СѓС‡Р°РµС‚ СЃС‚Р°С‚РёСЃС‚РёРєСѓ Р°РЅР°Р»РёР·Р°"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if analysis_file_id:
                    cursor.execute('''
                    SELECT * FROM analysis_stats 
                    WHERE analysis_file_id = ?
                    ''', (analysis_file_id,))
                else:
                    cursor.execute('''
                    SELECT * FROM analysis_stats 
                    ORDER BY analysis_date DESC 
                    LIMIT 1
                    ''')
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                
                return {}
                
        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ СЃС‚Р°С‚РёСЃС‚РёРєРё: {e}")
            return {}
    
    def get_matrix_data(self, analysis_file_id: int = None) -> List[Dict]:
        """РџРѕР»СѓС‡Р°РµС‚ РґР°РЅРЅС‹Рµ РјР°С‚СЂРёС†С‹ ABC-XYZ"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if analysis_file_id:
                    cursor.execute('''
                    SELECT * FROM matrix_stats 
                    WHERE analysis_file_id = ?
                    ORDER BY abc_xyz_category
                    ''', (analysis_file_id,))
                else:
                    cursor.execute('''
                    SELECT * FROM matrix_stats 
                    WHERE analysis_file_id = (
                        SELECT MAX(id) FROM analysis_files
                    )
                    ORDER BY abc_xyz_category
                    ''')
                
                results = []
                for row in cursor.fetchall():
                    results.append(dict(row))
                
                return results
                
        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ РґР°РЅРЅС‹С… РјР°С‚СЂРёС†С‹: {e}")
            return []
    
    def get_latest_analysis(self) -> Dict:
        """РџРѕР»СѓС‡Р°РµС‚ РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ РїРѕСЃР»РµРґРЅРµРј Р°РЅР°Р»РёР·Рµ"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT 
                    id as analysis_id,
                    filename,
                    analysis_type,
                    upload_date,
                    rows_count
                FROM analysis_files
                ORDER BY upload_date DESC
                LIMIT 1
                ''')
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                
                return {}
                
        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ РїРѕСЃР»РµРґРЅРµРіРѕ Р°РЅР°Р»РёР·Р°: {e}")
            return {}


# РџСЂРёРјРµСЂ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ
if __name__ == "__main__":
    # РўРµСЃС‚РёСЂРѕРІР°РЅРёРµ
    db = AnalysisDBLoader()
    print("вњ… Р‘Р°Р·Р° РґР°РЅРЅС‹С… Р°РЅР°Р»РёР·Р° РіРѕС‚РѕРІР° Рє СЂР°Р±РѕС‚Рµ")
    
    # РџСЂРѕРІРµСЂСЏРµРј РґРѕСЃС‚СѓРїРЅРѕСЃС‚СЊ
    latest = db.get_latest_analysis()
    if latest:
        print(f"рџ“Љ РџРѕСЃР»РµРґРЅРёР№ Р°РЅР°Р»РёР·: {latest.get('filename')}")
        print(f"рџ“€ РЎС‚Р°С‚РёСЃС‚РёРєР°: {db.get_analysis_stats()}")
    else:
        print("в„№пёЏ Р’ Р±Р°Р·Рµ РґР°РЅРЅС‹С… РїРѕРєР° РЅРµС‚ Р°РЅР°Р»РёР·РѕРІ")
