# services/db_manager.py

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnalysisDBManager:
    def __init__(self, db_path: str = None):
        """
        Менеджер базы данных для хранения результатов анализа
        
        Args:
            db_path: Путь к файлу БД (по умолчанию: analysis_results/analysis_visualization.db)
        """
        if db_path is None:
            # Путь по умолчанию - в папке analysis_results
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(current_dir, "analysis_results", "analysis_visualization.db")
        else:
            self.db_path = db_path
        
        # Создаем папку для БД если не существует
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        try:
            # Создаем таблицы
            self._create_tables()
            logger.info(f"База данных инициализирована: {self.db_path}")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
            raise
    
    def _create_tables(self):
        """Создание таблиц базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            # Таблица для отслеживания загруженных анализов
            conn.execute('''
            CREATE TABLE IF NOT EXISTS analysis_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                excel_filename TEXT NOT NULL,
                json_filename TEXT,
                analysis_filename TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_products INTEGER DEFAULT 0,
                total_revenue REAL DEFAULT 0,
                status TEXT DEFAULT 'completed',
                session_data TEXT  -- JSON с дополнительными данными
            )
            ''')
            
            # Основная таблица для данных продуктов
            conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_session_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                product_code TEXT,
                quantity REAL DEFAULT 0,
                revenue REAL DEFAULT 0,
                abc_category TEXT,
                xyz_category TEXT,
                abc_xyz_category TEXT,
                revenue_share REAL,
                cumulative_share REAL,
                rank INTEGER,
                category TEXT,
                FOREIGN KEY (analysis_session_id) REFERENCES analysis_sessions(id) ON DELETE CASCADE
            )
            ''')
            
            # Таблица для статистики по категориям
            conn.execute('''
            CREATE TABLE IF NOT EXISTS category_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_session_id INTEGER NOT NULL,
                category_type TEXT NOT NULL,  -- 'abc' или 'xyz'
                category_name TEXT NOT NULL,   -- 'A', 'B', 'C' или 'X', 'Y', 'Z'
                products_count INTEGER DEFAULT 0,
                total_revenue REAL DEFAULT 0,
                revenue_percentage REAL DEFAULT 0,
                FOREIGN KEY (analysis_session_id) REFERENCES analysis_sessions(id) ON DELETE CASCADE,
                UNIQUE(analysis_session_id, category_type, category_name)
            )
            ''')
            
            # Таблица для матрицы ABC-XYZ
            conn.execute('''
            CREATE TABLE IF NOT EXISTS matrix_cells (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_session_id INTEGER NOT NULL,
                abc_category TEXT NOT NULL,
                xyz_category TEXT NOT NULL,
                products_count INTEGER DEFAULT 0,
                total_revenue REAL DEFAULT 0,
                avg_revenue REAL DEFAULT 0,
                min_revenue REAL DEFAULT 0,
                max_revenue REAL DEFAULT 0,
                recommendation TEXT,
                FOREIGN KEY (analysis_session_id) REFERENCES analysis_sessions(id) ON DELETE CASCADE,
                UNIQUE(analysis_session_id, abc_category, xyz_category)
            )
            ''')
            
            # Таблица для хранения графиков (base64)
            conn.execute('''
            CREATE TABLE IF NOT EXISTS charts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_session_id INTEGER NOT NULL,
                chart_type TEXT NOT NULL,  -- 'abc_pie', 'xyz_bar', 'matrix', 'top_products'
                chart_data TEXT NOT NULL,  -- base64 изображение
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_session_id) REFERENCES analysis_sessions(id) ON DELETE CASCADE,
                UNIQUE(analysis_session_id, chart_type)
            )
            ''')
            
            # Создаем индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_products_session ON products(analysis_session_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_products_abc ON products(abc_category)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_products_xyz ON products(xyz_category)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_date ON analysis_sessions(upload_date)')
            
            conn.commit()
            logger.info("Таблицы БД созданы успешно")
    
    def save_analysis_session(self, excel_filename: str, json_filename: str = None, 
                            analysis_filename: str = None) -> int:
        """Создает новую сессию анализа и возвращает её ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                INSERT INTO analysis_sessions 
                (excel_filename, json_filename, analysis_filename)
                VALUES (?, ?, ?)
                ''', (excel_filename, json_filename, analysis_filename))
                
                session_id = cursor.lastrowid
                conn.commit()
                logger.info(f"Создана сессия анализа. ID: {session_id}")
                return session_id
                
        except Exception as e:
            logger.error(f"Ошибка создания сессии: {e}")
            raise
    
    def save_analysis_results(self, session_id: int, analysis_data: List[Dict]) -> Dict:
        """
        Сохраняет результаты анализа в БД
        
        Args:
            session_id: ID сессии анализа
            analysis_data: Данные анализа из analyzer.py
            
        Returns:
            Словарь с результатами сохранения
        """
        results = {
            "success": False,
            "products_saved": 0,
            "category_stats_saved": 0,
            "matrix_cells_saved": 0,
            "errors": []
        }
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Собираем статистику
                abc_stats = {}
                xyz_stats = {}
                matrix_stats = {}
                total_revenue = 0
                total_products = len(analysis_data)
                
                # Сохраняем продукты
                for idx, item in enumerate(analysis_data):
                    try:
                        product_name = item.get('name') or item.get('product_name') or f"Товар_{idx+1}"
                        product_code = item.get('product_code') or item.get('article') or None
                        revenue = float(item.get('revenue', 0))
                        quantity = float(item.get('quantity', 0))
                        
                        # Получаем категории
                        abc_category = item.get('ABC') or item.get('abc_category') or 'C'
                        xyz_category = item.get('XYZ') or item.get('xyz_category') or 'Z'
                        abc_xyz_category = item.get('ABC_XYZ') or f"{abc_category}{xyz_category}"
                        
                        # Обновляем статистику ABC
                        if abc_category not in abc_stats:
                            abc_stats[abc_category] = {'count': 0, 'revenue': 0}
                        abc_stats[abc_category]['count'] += 1
                        abc_stats[abc_category]['revenue'] += revenue
                        
                        # Обновляем статистику XYZ
                        if xyz_category not in xyz_stats:
                            xyz_stats[xyz_category] = {'count': 0, 'revenue': 0}
                        xyz_stats[xyz_category]['count'] += 1
                        xyz_stats[xyz_category]['revenue'] += revenue
                        
                        # Обновляем матрицу
                        matrix_key = f"{abc_category}-{xyz_category}"
                        if matrix_key not in matrix_stats:
                            matrix_stats[matrix_key] = {
                                'count': 0,
                                'total_revenue': 0,
                                'revenues': []
                            }
                        matrix_stats[matrix_key]['count'] += 1
                        matrix_stats[matrix_key]['total_revenue'] += revenue
                        matrix_stats[matrix_key]['revenues'].append(revenue)
                        
                        total_revenue += revenue
                        
                        # Сохраняем продукт
                        cursor.execute('''
                        INSERT INTO products 
                        (analysis_session_id, product_name, product_code, quantity, revenue,
                         abc_category, xyz_category, abc_xyz_category, rank)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            session_id,
                            product_name,
                            product_code,
                            quantity,
                            revenue,
                            abc_category,
                            xyz_category,
                            abc_xyz_category,
                            idx + 1
                        ))
                        
                        results["products_saved"] += 1
                        
                    except Exception as e:
                        error_msg = f"Ошибка сохранения товара {idx+1}: {str(e)}"
                        results["errors"].append(error_msg)
                        logger.warning(error_msg)
                
                # Сохраняем статистику ABC
                for category, stats in abc_stats.items():
                    percentage = (stats['revenue'] / total_revenue * 100) if total_revenue > 0 else 0
                    
                    cursor.execute('''
                    INSERT OR REPLACE INTO category_stats 
                    (analysis_session_id, category_type, category_name, 
                     products_count, total_revenue, revenue_percentage)
                    VALUES (?, 'abc', ?, ?, ?, ?)
                    ''', (
                        session_id,
                        category,
                        stats['count'],
                        stats['revenue'],
                        percentage
                    ))
                    
                    results["category_stats_saved"] += 1
                
                # Сохраняем статистику XYZ
                for category, stats in xyz_stats.items():
                    percentage = (stats['revenue'] / total_revenue * 100) if total_revenue > 0 else 0
                    
                    cursor.execute('''
                    INSERT OR REPLACE INTO category_stats 
                    (analysis_session_id, category_type, category_name, 
                     products_count, total_revenue, revenue_percentage)
                    VALUES (?, 'xyz', ?, ?, ?, ?)
                    ''', (
                        session_id,
                        category,
                        stats['count'],
                        stats['revenue'],
                        percentage
                    ))
                    
                    results["category_stats_saved"] += 1
                
                # Сохраняем матрицу
                for matrix_key, stats in matrix_stats.items():
                    abc_cat, xyz_cat = matrix_key.split('-')
                    avg_rev = stats['total_revenue'] / stats['count'] if stats['count'] > 0 else 0
                    min_rev = min(stats['revenues']) if stats['revenues'] else 0
                    max_rev = max(stats['revenues']) if stats['revenues'] else 0
                    
                    # Генерируем рекомендацию
                    recommendation = self._get_matrix_recommendation(abc_cat, xyz_cat)
                    
                    cursor.execute('''
                    INSERT OR REPLACE INTO matrix_cells 
                    (analysis_session_id, abc_category, xyz_category,
                     products_count, total_revenue, avg_revenue,
                     min_revenue, max_revenue, recommendation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id,
                        abc_cat,
                        xyz_cat,
                        stats['count'],
                        stats['total_revenue'],
                        avg_rev,
                        min_rev,
                        max_rev,
                        recommendation
                    ))
                    
                    results["matrix_cells_saved"] += 1
                
                # Обновляем статистику сессии
                cursor.execute('''
                UPDATE analysis_sessions 
                SET total_products = ?, total_revenue = ?
                WHERE id = ?
                ''', (total_products, total_revenue, session_id))
                
                conn.commit()
                results["success"] = True
                
                logger.info(f"Сохранено: {results['products_saved']} товаров, "
                          f"{results['category_stats_saved']} категорий, "
                          f"{results['matrix_cells_saved']} ячеек матрицы")
                
                return results
                
        except Exception as e:
            logger.error(f"Критическая ошибка сохранения анализа: {e}")
            results["errors"].append(str(e))
            return results
    
    def _get_matrix_recommendation(self, abc_category: str, xyz_category: str) -> str:
        """Генерирует рекомендацию для ячейки матрицы"""
        recommendations = {
            'AX': 'Приоритет 1: Максимальные запасы, золотая зона, ежедневный контроль',
            'AY': 'Приоритет 2: Сезонное планирование, увеличение запасов в пик сезона',
            'AZ': 'Приоритет 3: Работа под заказ, минимальные запасы',
            'BX': 'Приоритет 4: Оптимальные запасы, средняя зона склада',
            'BY': 'Приоритет 5: Планирование по сезонам, умеренные запасы',
            'BZ': 'Приоритет 6: Минимальные запасы, мониторинг спроса',
            'CX': 'Приоритет 7: Базовая страховка, удаленная зона',
            'CY': 'Приоритет 8: Закупка по необходимости, низкие запасы',
            'CZ': 'Приоритет 9: Рассмотреть исключение, работа только под заказ'
        }
        
        key = f"{abc_category}{xyz_category}"
        return recommendations.get(key, 'Стандартные рекомендации по управлению запасами')
    
    def save_charts(self, session_id: int, charts_data: Dict[str, str]) -> bool:
        """
        Сохраняет графики в БД
        
        Args:
            session_id: ID сессии анализа
            charts_data: Словарь с графиками {тип: base64_data}
            
        Returns:
            True если сохранение успешно
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for chart_type, chart_data in charts_data.items():
                    cursor.execute('''
                    INSERT OR REPLACE INTO charts 
                    (analysis_session_id, chart_type, chart_data)
                    VALUES (?, ?, ?)
                    ''', (session_id, chart_type, chart_data))
                
                conn.commit()
                logger.info(f"Сохранено {len(charts_data)} графиков для сессии {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка сохранения графиков: {e}")
            return False
    
    def get_latest_session_id(self) -> Optional[int]:
        """Получает ID последней сессии анализа"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT MAX(id) FROM analysis_sessions')
                result = cursor.fetchone()
                return result[0] if result and result[0] else None
                
        except Exception as e:
            logger.error(f"Ошибка получения последней сессии: {e}")
            return None
    
    def get_session_info(self, session_id: int = None) -> Dict:
        """Получает информацию о сессии анализа"""
        try:
            if session_id is None:
                session_id = self.get_latest_session_id()
                if not session_id:
                    return {}
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT * FROM analysis_sessions 
                WHERE id = ?
                ''', (session_id,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                
                return {}
                
        except Exception as e:
            logger.error(f"Ошибка получения информации о сессии: {e}")
            return {}
    
    def get_products_data(self, session_id: int = None, limit: int = 100) -> List[Dict]:
        """Получает данные продуктов для отображения в таблице"""
        try:
            if session_id is None:
                session_id = self.get_latest_session_id()
                if not session_id:
                    return []
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT 
                    product_name,
                    product_code,
                    quantity,
                    revenue,
                    abc_category,
                    xyz_category,
                    abc_xyz_category,
                    rank
                FROM products 
                WHERE analysis_session_id = ?
                ORDER BY revenue DESC, rank ASC
                LIMIT ?
                ''', (session_id, limit))
                
                results = []
                for row in cursor.fetchall():
                    results.append(dict(row))
                
                return results
                
        except Exception as e:
            logger.error(f"Ошибка получения данных продуктов: {e}")
            return []
    
    def get_category_stats(self, session_id: int = None) -> Dict:
        """Получает статистику по категориям"""
        try:
            if session_id is None:
                session_id = self.get_latest_session_id()
                if not session_id:
                    return {}
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT 
                    category_type,
                    category_name,
                    products_count,
                    total_revenue,
                    revenue_percentage
                FROM category_stats 
                WHERE analysis_session_id = ?
                ORDER BY category_type, category_name
                ''', (session_id,))
                
                stats = {'abc': {}, 'xyz': {}}
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    cat_type = row_dict['category_type']
                    cat_name = row_dict['category_name']
                    
                    if cat_type == 'abc':
                        stats['abc'][cat_name] = row_dict
                    else:
                        stats['xyz'][cat_name] = row_dict
                
                return stats
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики категорий: {e}")
            return {}
    
    def get_matrix_data(self, session_id: int = None) -> List[Dict]:
        """Получает данные матрицы ABC-XYZ"""
        try:
            if session_id is None:
                session_id = self.get_latest_session_id()
                if not session_id:
                    return []
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT 
                    abc_category,
                    xyz_category,
                    products_count,
                    total_revenue,
                    avg_revenue,
                    min_revenue,
                    max_revenue,
                    recommendation
                FROM matrix_cells 
                WHERE analysis_session_id = ?
                ORDER BY abc_category, xyz_category
                ''', (session_id,))
                
                results = []
                for row in cursor.fetchall():
                    results.append(dict(row))
                
                return results
                
        except Exception as e:
            logger.error(f"Ошибка получения данных матрицы: {e}")
            return []
    
    def get_charts(self, session_id: int = None) -> Dict[str, str]:
        """Получает сохраненные графики"""
        try:
            if session_id is None:
                session_id = self.get_latest_session_id()
                if not session_id:
                    return {}
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT chart_type, chart_data 
                FROM charts 
                WHERE analysis_session_id = ?
                ''', (session_id,))
                
                charts = {}
                for row in cursor.fetchall():
                    row_dict = dict(row)
                    charts[row_dict['chart_type']] = row_dict['chart_data']
                
                return charts
                
        except Exception as e:
            logger.error(f"Ошибка получения графиков: {e}")
            return {}
    
    def get_all_sessions(self) -> List[Dict]:
        """Получает список всех сессий анализа"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT 
                    id,
                    excel_filename,
                    upload_date,
                    total_products,
                    total_revenue,
                    status
                FROM analysis_sessions 
                ORDER BY upload_date DESC
                LIMIT 50
                ''')
                
                results = []
                for row in cursor.fetchall():
                    results.append(dict(row))
                
                return results
                
        except Exception as e:
            logger.error(f"Ошибка получения списка сессий: {e}")
            return []

# Создаем глобальный экземпляр для использования во всем приложении
db_manager = AnalysisDBManager()