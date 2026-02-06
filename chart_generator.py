import matplotlib.pyplot as plt
import io
import base64
import numpy as np
import sqlite3
import json
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.models import Analysis
from matplotlib import cm
from matplotlib.patches import Patch
from matplotlib import colors

class ChartGenerator:
    def __init__(self, session: Session, analysis_db=None, analysis_data=None):
        self.session = session
        self.analysis_db = analysis_db
        self.analysis_db_path = getattr(analysis_db, "db_path", None) if analysis_db else None
        self.analysis_data = analysis_data
        # Устанавливаем стиль для лучшей читаемости
        plt.style.use('default')
        plt.rcParams['figure.facecolor'] = 'white'
        plt.rcParams['axes.facecolor'] = 'white'
        plt.rcParams['font.size'] = 10

    def _normalize_analysis_data(self):
        data = self.analysis_data
        if isinstance(data, dict):
            if "results" in data and isinstance(data["results"], list):
                return data["results"]
            if "data" in data and isinstance(data["data"], list):
                return data["data"]
            return []
        if isinstance(data, list):
            return data
        return []

    def _load_latest_analysis_results(self):
        try:
            base_dir = Path(__file__).resolve().parent
            results_dir = base_dir / "pepe parser" / "analysis_results"
            if not results_dir.exists():
                return []
            candidates = list(results_dir.glob("*_analysis.json"))
            if not candidates:
                return []
            latest_file = max(candidates, key=lambda p: p.stat().st_mtime)
            with latest_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if "results" in data and isinstance(data["results"], list):
                    return data["results"]
                if "data" in data and isinstance(data["data"], list):
                    return data["data"]
            if isinstance(data, list):
                return data
        except Exception as e:
            print(f"⚠️ Не удалось прочитать последний analysis_results JSON: {e}")
        return []
    
    def create_abc_pie_chart(self):
        """Круговая диаграмма ABC анализа с отладкой"""
        try:
            print("🔍 Создаю ABC круговую диаграмму...")
            
            # Получаем данные по ABC категориям (предпочтительно по количеству)
            results = []
            use_quantity_data = False

            if self.analysis_db_path:
                try:
                    with sqlite3.connect(self.analysis_db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT MAX(id) FROM analysis_files")
                        row = cursor.fetchone()
                        analysis_id = row[0] if row else None

                        if analysis_id:
                            cursor.execute("SELECT COUNT(*) FROM analysis_data WHERE analysis_file_id = ?", (analysis_id,))
                            count_rows = cursor.fetchone()[0]
                            print(f"ℹ️ analysis_db: analysis_id={analysis_id}, rows={count_rows}")
                            cursor.execute('''
                                SELECT abc_category,
                                       SUM(quantity) AS total_quantity,
                                       COUNT(*) AS products_count
                                FROM analysis_data
                                WHERE analysis_file_id = ?
                                  AND abc_category IS NOT NULL
                                GROUP BY abc_category
                            ''', (analysis_id,))
                            results = cursor.fetchall()
                            if results:
                                use_quantity_data = True
                        else:
                            print("⚠️ analysis_db: analysis_files пустая, нет analysis_id")
                except Exception as e:
                    print(f"⚠️ Не удалось получить данные по количеству: {e}")
            else:
                print("⚠️ analysis_db_path не задан, использую выручку")

            # Если данных по количеству нет, пробуем из переданных analysis_data
            normalized_data = self._normalize_analysis_data()
            if not results and normalized_data:
                try:
                    totals = {}
                    counts_map = {}
                    for item in normalized_data:
                        if not isinstance(item, dict):
                            continue
                        cat = item.get('ABC') or item.get('abc_category')
                        qty = item.get('quantity', 0)
                        if not cat:
                            continue
                        try:
                            qty_val = float(qty)
                        except (ValueError, TypeError):
                            continue
                        if not np.isfinite(qty_val) or qty_val < 0:
                            continue
                        totals[cat] = totals.get(cat, 0) + qty_val
                        counts_map[cat] = counts_map.get(cat, 0) + 1
                    if totals:
                        results = [(cat, totals[cat], counts_map.get(cat, 0)) for cat in totals.keys()]
                        use_quantity_data = True
                        print("ℹ️ Использую quantity из analysis_data")
                    else:
                        print("⚠️ analysis_data есть, но quantity не найден")
                except Exception as e:
                    print(f"⚠️ Не удалось получить quantity из analysis_data: {e}")

            # Если и это не помогло, пробуем загрузить последний JSON из analysis_results
            if not results:
                latest_data = self._load_latest_analysis_results()
                if latest_data:
                    try:
                        totals = {}
                        counts_map = {}
                        for item in latest_data:
                            if not isinstance(item, dict):
                                continue
                            cat = item.get('ABC') or item.get('abc_category')
                            qty = item.get('quantity', 0)
                            if not cat:
                                continue
                            try:
                                qty_val = float(qty)
                            except (ValueError, TypeError):
                                continue
                            if not np.isfinite(qty_val) or qty_val < 0:
                                continue
                            totals[cat] = totals.get(cat, 0) + qty_val
                            counts_map[cat] = counts_map.get(cat, 0) + 1
                        if totals:
                            results = [(cat, totals[cat], counts_map.get(cat, 0)) for cat in totals.keys()]
                            use_quantity_data = True
                            print("ℹ️ Использую quantity из последнего analysis_results JSON")
                    except Exception as e:
                        print(f"⚠️ Не удалось получить quantity из analysis_results JSON: {e}")

            if not results:
                # Fallback: данные по выручке из основной БД
                query = self.session.query(
                    Analysis.abc_category,
                    func.sum(Analysis.revenue).label('total_revenue'),
                    func.count(Analysis.id).label('count')
                ).filter(Analysis.abc_category.isnot(None)).group_by(Analysis.abc_category)
                results = query.all()
            
            print(f"📊 Найдено ABC категорий: {len(results)}")
            for cat, value, count in results:
                unit = "шт." if use_quantity_data else "у.е."
                print(f"   • {cat}: {count} товаров, {value:,.0f} {unit}")
            
            if not results:
                print("⚠️ Нет данных для ABC диаграммы")
                return None
            
            # Подготавливаем данные
            categories = []
            values = []
            counts = []
            
            for cat, value, count in results:
                if not cat:
                    continue
                if value is None:
                    continue
                value = float(value)
                if not np.isfinite(value):
                    continue
                if value < 0:
                    continue
                categories.append(cat)
                values.append(value)
                counts.append(count)
            
            if not values:
                print("⚠️ Нет числовых данных для ABC диаграммы")
                return None
            
            if sum(values) <= 0:
                if use_quantity_data:
                    print("⚠️ Сумма количества равна 0, пробую построить по выручке")
                    # Fallback на выручку
                    query = self.session.query(
                        Analysis.abc_category,
                        func.sum(Analysis.revenue).label('total_revenue'),
                        func.count(Analysis.id).label('count')
                    ).filter(Analysis.abc_category.isnot(None)).group_by(Analysis.abc_category)
                    results = query.all()
                    categories = []
                    values = []
                    counts = []
                    for cat, value, count in results:
                        if not cat:
                            continue
                        if value is None:
                            continue
                        value = float(value)
                        if not np.isfinite(value) or value < 0:
                            continue
                        categories.append(cat)
                        values.append(value)
                        counts.append(count)
                    use_quantity_data = False

                if sum(values) <= 0:
                    print("⚠️ Сумма значений для ABC диаграммы равна 0")
                    return None
            
            # Улучшенные цвета
            colors_dict = {
                'A': '#2ecc71',  # зеленый
                'B': '#f39c12',  # оранжевый
                'C': '#e74c3c'   # красный
            }
            
            # Сортируем по порядку A, B, C
            order = ['A', 'B', 'C']
            sorted_data = []
            for cat in order:
                if cat in categories:
                    idx = categories.index(cat)
                    sorted_data.append((cat, values[idx], counts[idx]))
            
            if not sorted_data:
                print("⚠️ Нет данных в стандартных категориях A, B, C")
                return None
            
            sorted_categories, sorted_revenues, sorted_counts = zip(*sorted_data)
            
            # Создаем график
            fig, ax = plt.subplots(figsize=(10, 8))
            
            # Авто-проценты с улучшенным форматированием
            def autopct_format(pct):
                total = sum(sorted_revenues)
                value = pct * total / 100.0
                if use_quantity_data:
                    return f'{pct:.1f}%\n({value:,.0f} шт.)'
                return f'{pct:.1f}%\n({value:,.0f})'
            
            # Создаем диаграмму
            wedges, texts, autotexts = ax.pie(
                sorted_revenues,
                labels=[
                    f'{cat} ({value:,.0f} {"шт." if use_quantity_data else "у.е."})'
                    for cat, value in zip(sorted_categories, sorted_revenues)
                ],
                colors=[colors_dict[cat] for cat in sorted_categories],
                autopct=autopct_format,
                startangle=90,
                shadow=True,
                explode=[0.05 if cat == 'A' else 0 for cat in sorted_categories],
                textprops={'fontsize': 11}
            )
            
            # Улучшаем отображение текста
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(10)
            
            title_suffix = "количества (шт.)" if use_quantity_data else "выручки"
            ax.set_title(f'ABC Анализ: Распределение {title_suffix}', 
                        fontsize=14, fontweight='bold', pad=20)
            
            # Добавляем легенду
            legend_map = {
                'A': 'A - Высокий приоритет',
                'B': 'B - Средний приоритет',
                'C': 'C - Низкий приоритет'
            }
            legend_labels = [
                f"{legend_map.get(cat, cat)} ({rev:,.0f} {'шт.' if use_quantity_data else 'у.е.'})"
                for cat, rev in zip(sorted_categories, sorted_revenues)
            ]
            ax.legend(
                wedges,
                legend_labels,
                loc="center left",
                bbox_to_anchor=(1, 0, 0.5, 1),
                fontsize=10
            )
            
            plt.tight_layout()
            print("✅ ABC круговая диаграмма успешно создана")
            return self._fig_to_base64(fig)
            
        except Exception as e:
            print(f"❌ Ошибка создания ABC диаграммы: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_xyz_bar_chart(self):
        """Столбчатая диаграмма XYZ анализа с отладкой"""
        try:
            print("🔍 Создаю XYZ столбчатую диаграмму...")
            
            # Получаем данные по XYZ категориям
            query = self.session.query(
                Analysis.xyz_category,
                func.sum(Analysis.revenue).label('total_revenue'),
                func.count(Analysis.id).label('count')
            ).filter(Analysis.xyz_category.isnot(None)).group_by(Analysis.xyz_category)
            
            results = query.all()
            
            print(f"📊 Найдено XYZ категорий: {len(results)}")
            for cat, revenue, count in results:
                print(f"   • {cat}: {count} товаров, {revenue:,.0f} у.е.")
            
            if not results:
                print("⚠️ Нет данных для XYZ диаграммы")
                return None
            
            # Подготавливаем данные
            categories = []
            revenues = []
            counts = []
            
            for cat, revenue, count in results:
                if cat:
                    categories.append(cat)
                    revenues.append(float(revenue))
                    counts.append(count)
            
            if not revenues:
                print("⚠️ Нет числовых данных для XYZ диаграммы")
                return None
            
            # Сортируем по порядку X, Y, Z
            order = ['X', 'Y', 'Z']
            sorted_data = []
            for cat in order:
                if cat in categories:
                    idx = categories.index(cat)
                    sorted_data.append((cat, revenues[idx], counts[idx]))
            
            if not sorted_data:
                print("⚠️ Нет данных в стандартных категориях X, Y, Z")
                return None
            
            sorted_categories, sorted_revenues, sorted_counts = zip(*sorted_data)
            
            # Цвета для категорий XYZ
            colors_dict = {
                'X': '#3498db',  # синий
                'Y': '#9b59b6',  # фиолетовый
                'Z': '#e74c3c'   # красный
            }
            
            # Создаем график
            fig, ax = plt.subplots(figsize=(10, 6))
            
            x_pos = range(len(sorted_categories))
            bars = ax.bar(x_pos, sorted_revenues, 
                         color=[colors_dict[cat] for cat in sorted_categories],
                         alpha=0.8,
                         edgecolor='black',
                         linewidth=1)
            
            # Добавляем значения на столбцы
            for i, (bar, revenue, count) in enumerate(zip(bars, sorted_revenues, sorted_counts)):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + max(sorted_revenues)*0.01,
                       f'{revenue:,.0f}\n({count} шт.)',
                       ha='center', va='bottom', fontsize=10, fontweight='bold')
            
            ax.set_xticks(x_pos)
            ax.set_xticklabels([f'Категория {cat}' for cat in sorted_categories], fontsize=11, fontweight='bold')
            ax.set_title('XYZ Анализ: Стабильность спроса', 
                        fontsize=14, fontweight='bold', pad=15)
            ax.set_ylabel('Общая выручка (у.е.)', fontsize=11)
            ax.set_xlabel('Категория XYZ', fontsize=11)
            
            # Добавляем сетку
            ax.grid(True, alpha=0.3, axis='y', linestyle='--')
            
            # Легенда
            legend_elements = [
                Patch(facecolor='#3498db', label='X - Стабильный спрос'),
                Patch(facecolor='#9b59b6', label='Y - Сезонные колебания'),
                Patch(facecolor='#e74c3c', label='Z - Нерегулярный спрос')
            ]
            ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
            
            plt.tight_layout()
            print("✅ XYZ столбчатая диаграмма успешно создана")
            return self._fig_to_base64(fig)
            
        except Exception as e:
            print(f"❌ Ошибка создания XYZ диаграммы: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_abc_xyz_matrix(self):
        """Тепловая карта матрицы ABC-XYZ с отладкой"""
        try:
            print("🔍 Создаю матрицу ABC-XYZ...")
            
            # Получаем данные для матрицы с отладкой
            query = self.session.query(
                Analysis.abc_category,
                Analysis.xyz_category,
                func.count(Analysis.id).label('count'),
                func.sum(Analysis.revenue).label('total_revenue')
            ).filter(
                Analysis.abc_category.in_(['A', 'B', 'C']),
                Analysis.xyz_category.in_(['X', 'Y', 'Z']),
                Analysis.abc_category.isnot(None),
                Analysis.xyz_category.isnot(None)
            ).group_by(Analysis.abc_category, Analysis.xyz_category)
            
            results = query.all()
            
            print(f"📊 Данные для матрицы ABC-XYZ:")
            print(f"   • Найдено комбинаций: {len(results)}")
            
            if not results:
                print("⚠️ Нет данных для матрицы ABC-XYZ")
                # Создаем пустую матрицу с сообщением
                return self._create_empty_matrix()
            
            # Выводим все комбинации
            matrix_data = {}
            for abc, xyz, count, total_revenue in results:
                avg_revenue = float(total_revenue) / count if count > 0 else 0
                print(f"   • {abc}-{xyz}: количество={count}, выручка={total_revenue:.0f}, средняя={avg_revenue:.0f}")
                matrix_data[f"{abc}-{xyz}"] = {
                    'count': count,
                    'avg_revenue': avg_revenue
                }
            
            # Создаем матрицу 3x3
            abc_cats = ['A', 'B', 'C']
            xyz_cats = ['X', 'Y', 'Z']
            
            matrix = np.zeros((len(abc_cats), len(xyz_cats)))
            count_matrix = np.zeros((len(abc_cats), len(xyz_cats)))
            
            # Заполняем матрицу
            for i, abc in enumerate(abc_cats):
                for j, xyz in enumerate(xyz_cats):
                    key = f"{abc}-{xyz}"
                    if key in matrix_data:
                        matrix[i, j] = matrix_data[key]['avg_revenue']
                        count_matrix[i, j] = matrix_data[key]['count']
                    else:
                        matrix[i, j] = 0
                        count_matrix[i, j] = 0
            
            print(f"📊 Матрица значений:")
            for i, abc in enumerate(abc_cats):
                row_vals = []
                for j, xyz in enumerate(xyz_cats):
                    row_vals.append(f"{abc}-{xyz}: {matrix[i,j]:.0f} ({int(count_matrix[i,j])} шт.)")
                print(f"   {' | '.join(row_vals)}")
            
            # Проверяем, есть ли данные в матрице
            if np.sum(matrix) == 0 and np.sum(count_matrix) == 0:
                print("⚠️ Матрица пустая (все значения 0)")
                return self._create_empty_matrix()
            
            # Создаем график
            fig, ax = plt.subplots(figsize=(10, 8))
            
            # Используем улучшенную цветовую схему
            # Находим максимальное значение для цветовой шкалы
            max_val = np.max(matrix) if np.max(matrix) > 0 else 1
            im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto', 
                          interpolation='nearest', alpha=0.9,
                          vmin=0, vmax=max_val)
            
            # Устанавливаем метки
            ax.set_xticks(np.arange(len(xyz_cats)))
            ax.set_yticks(np.arange(len(abc_cats)))
            ax.set_xticklabels([f'XYZ-{cat}' for cat in xyz_cats], fontsize=12, fontweight='bold')
            ax.set_yticklabels([f'ABC-{cat}' for cat in abc_cats], fontsize=12, fontweight='bold')
            
            ax.set_xlabel('Категория XYZ (стабильность спроса)', fontsize=12, fontweight='bold')
            ax.set_ylabel('Категория ABC (важность товара)', fontsize=12, fontweight='bold')
            ax.set_title('Матрица ABC-XYZ (средняя выручка на товар)', 
                        fontsize=14, fontweight='bold', pad=20)
            
            # Добавляем значения в ячейки
            for i in range(len(abc_cats)):
                for j in range(len(xyz_cats)):
                    value = matrix[i, j]
                    count = count_matrix[i, j]
                    
                    # Определяем цвет текста в зависимости от фона
                    text_color = 'white' if value > max_val/2 else 'black'
                    
                    if count > 0:
                        text = f'{value:,.0f}\n({int(count)} шт.)'
                        
                        # Определяем цвет фона bbox
                        if text_color == 'white':
                            bbox_props = dict(boxstyle="round,pad=0.3",
                                             facecolor='black',
                                             alpha=0.3,
                                             edgecolor='none')
                        else:
                            bbox_props = dict(boxstyle="round,pad=0.3",
                                             facecolor='white',
                                             alpha=0.7,
                                             edgecolor='none')
                        
                        ax.text(j, i, text,
                               ha="center", va="center",
                               color=text_color, fontweight='bold',
                               fontsize=10,
                               bbox=bbox_props)
                    else:
                        ax.text(j, i, 'Нет данных',
                               ha="center", va="center",
                               color='gray', fontsize=9,
                               alpha=0.7)
            
            # Добавляем цветовую шкалу
            cbar = ax.figure.colorbar(im, ax=ax)
            cbar.ax.set_ylabel('Средняя выручка (у.е.)', rotation=-90, va="bottom", fontsize=11)
            
            # Добавляем сетку
            ax.set_xticks(np.arange(len(xyz_cats)+1)-0.5, minor=True)
            ax.set_yticks(np.arange(len(abc_cats)+1)-0.5, minor=True)
            ax.grid(which="minor", color="gray", linestyle='-', linewidth=0.5, alpha=0.3)
            ax.tick_params(which="minor", size=0)
            
            plt.tight_layout()
            print("✅ Матрица ABC-XYZ успешно создана")
            return self._fig_to_base64(fig)
            
        except Exception as e:
            print(f"❌ Ошибка создания матрицы ABC-XYZ: {e}")
            import traceback
            traceback.print_exc()
            return self._create_empty_matrix()
    
    def _create_empty_matrix(self):
        """Создает пустую матрицу с сообщением"""
        try:
            print("📊 Создаю пустую матрицу с сообщением")
            
            fig, ax = plt.subplots(figsize=(10, 8))
            
            abc_cats = ['A', 'B', 'C']
            xyz_cats = ['X', 'Y', 'Z']
            
            # Создаем пустую матрицу
            matrix = np.zeros((3, 3))
            
            im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto', alpha=0.9)
            
            ax.set_xticks(range(len(xyz_cats)))
            ax.set_yticks(range(len(abc_cats)))
            ax.set_xticklabels([f'XYZ-{cat}' for cat in xyz_cats], fontsize=12, fontweight='bold')
            ax.set_yticklabels([f'ABC-{cat}' for cat in abc_cats], fontsize=12, fontweight='bold')
            
            # Добавляем сообщение в каждую ячейку
            for i in range(3):
                for j in range(3):
                    ax.text(j, i, 'Нет данных', 
                           ha='center', va='center', 
                           color='gray', fontweight='bold', fontsize=10,
                           bbox=dict(boxstyle="round,pad=0.3",
                                    facecolor='lightgray',
                                    alpha=0.9,
                                    edgecolor='gray'))
            
            ax.set_xlabel('Категория XYZ', fontsize=12, fontweight='bold')
            ax.set_ylabel('Категория ABC', fontsize=12, fontweight='bold')
            ax.set_title('Матрица ABC-XYZ\nЗагрузите данные для анализа', 
                        fontsize=14, fontweight='bold', pad=20)
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            print(f"❌ Ошибка создания пустой матрицы: {e}")
            return None
    
    def _create_demo_matrix(self):
        """Создает демонстрационную матрицу, когда нет данных"""
        try:
            print("📊 Создаю демонстрационную матрицу ABC-XYZ")
            
            # Демонстрационные данные
            matrix = np.array([
                [15000, 8000, 3000],
                [9000, 5000, 1800],
                [4000, 2000, 800]
            ])
            
            abc_cats = ['A', 'B', 'C']
            xyz_cats = ['X', 'Y', 'Z']
            
            fig, ax = plt.subplots(figsize=(10, 8))
            im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto', alpha=0.9)
            
            ax.set_xticks(range(len(xyz_cats)))
            ax.set_yticks(range(len(abc_cats)))
            ax.set_xticklabels([f'XYZ-{cat}' for cat in xyz_cats], fontsize=12, fontweight='bold')
            ax.set_yticklabels([f'ABC-{cat}' for cat in abc_cats], fontsize=12, fontweight='bold')
            
            # Добавляем значения
            for i in range(3):
                for j in range(3):
                    text_color = 'white' if matrix[i,j] > np.max(matrix)/2 else 'black'
                    
                    if text_color == 'white':
                        facecolor = 'black'
                        alpha_val = 0.3
                    else:
                        facecolor = 'white'
                        alpha_val = 0.7
                    
                    ax.text(j, i, f'{matrix[i,j]:,.0f}\n(пример)', 
                           ha='center', va='center', 
                           color=text_color, fontweight='bold', fontsize=10,
                           bbox=dict(boxstyle="round,pad=0.3",
                                    facecolor=facecolor,
                                    alpha=alpha_val,
                                    edgecolor='none'))
            
            ax.set_xlabel('Категория XYZ', fontsize=12, fontweight='bold')
            ax.set_ylabel('Категория ABC', fontsize=12, fontweight='bold')
            ax.set_title('Матрица ABC-XYZ (демонстрация)\nЗагрузите данные для реального анализа', 
                        fontsize=14, fontweight='bold', pad=20)
            
            # Добавляем цветовую шкалу
            cbar = ax.figure.colorbar(im, ax=ax)
            cbar.ax.set_ylabel('Средняя выручка (у.е.)', rotation=-90, va="bottom", fontsize=11)
            
            # Добавляем сетку
            ax.set_xticks(np.arange(len(xyz_cats)+1)-0.5, minor=True)
            ax.set_yticks(np.arange(len(abc_cats)+1)-0.5, minor=True)
            ax.grid(which="minor", color="gray", linestyle='-', linewidth=0.5, alpha=0.3)
            ax.tick_params(which="minor", size=0)
            
            plt.tight_layout()
            return self._fig_to_base64(fig)
            
        except Exception as e:
            print(f"❌ Ошибка создания демо-матрицы: {e}")
            return None
    
    def create_top_products_chart(self, limit=15):
        """Горизонтальная столбчатая диаграмма топ товаров с отладкой"""
        try:
            print("🔍 Создаю график топ товаров...")
            
            # Получаем топ товаров
            query = self.session.query(
                Analysis.product_name,
                Analysis.revenue,
                Analysis.abc_category
            ).order_by(Analysis.revenue.desc()).limit(limit)
            
            results = query.all()
            
            print(f"📊 Найдено товаров для графика: {len(results)}")
            
            if not results:
                print("⚠️ Нет данных для графика топ товаров")
                return None
            
            # Подготавливаем данные
            products = []
            revenues = []
            categories = []
            
            for i, (name, revenue, cat) in enumerate(results):
                if name:
                    # Обрезаем длинные названия
                    display_name = name[:30] + '...' if len(name) > 30 else name
                    products.append(display_name)
                    revenues.append(float(revenue))
                    categories.append(cat or 'C')
                    if i < 5:  # Показываем только первые 5 для отладки
                        print(f"   • {display_name}: {revenue:,.0f} у.е., категория {cat}")
            
            if not revenues:
                print("⚠️ Нет числовых данных для графика топ товаров")
                return None
            
            # Цвета по категориям ABC
            colors_dict = {
                'A': '#2ecc71',  # зеленый
                'B': '#f39c12',  # оранжевый
                'C': '#e74c3c'   # красный
            }
            
            # Создаем график
            fig, ax = plt.subplots(figsize=(12, 8))
            
            y_pos = range(len(products))
            bars = ax.barh(y_pos, revenues, 
                          color=[colors_dict.get(cat[0] if cat else 'C', '#95a5a6') for cat in categories],
                          alpha=0.8,
                          edgecolor='black',
                          linewidth=1,
                          height=0.7)
            
            ax.invert_yaxis()  # Самый большой сверху
            
            # Добавляем значения справа от столбцов
            for i, (bar, revenue, cat) in enumerate(zip(bars, revenues, categories)):
                width = bar.get_width()
                full_name = results[i][0] if i < len(results) else ''
                
                ax.text(width + max(revenues)*0.005, 
                       bar.get_y() + bar.get_height()/2.,
                       f'{revenue:,.0f} у.е.\n({cat if cat else "?"})',
                       ha='left', va='center', 
                       fontsize=9, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.2", 
                                facecolor='white',
                                edgecolor='gray',
                                alpha=0.8))
            
            ax.set_yticks(y_pos)
            ax.set_yticklabels(products, fontsize=10)
            ax.set_title(f'Топ {len(products)} товаров по выручке', 
                        fontsize=14, fontweight='bold', pad=15)
            ax.set_xlabel('Выручка (у.е.)', fontsize=11)
            
            # Добавляем сетку
            ax.grid(True, alpha=0.3, axis='x', linestyle='--')
            
            # Легенда
            legend_elements = [
                Patch(facecolor='#2ecc71', label='A - Высокий приоритет'),
                Patch(facecolor='#f39c12', label='B - Средний приоритет'),
                Patch(facecolor='#e74c3c', label='C - Низкий приоритет')
            ]
            ax.legend(handles=legend_elements, loc='lower right', fontsize=10)
            
            plt.tight_layout()
            print("✅ График топ товаров успешно создан")
            return self._fig_to_base64(fig)
            
        except Exception as e:
            print(f"❌ Ошибка создания графика топ товаров: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _fig_to_base64(self, fig, dpi=150):
        """Конвертирует matplotlib figure в base64 строку"""
        try:
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close(fig)
            buf.seek(0)
            
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            return img_base64
        except Exception as e:
            print(f"❌ Ошибка конвертации графика в base64: {e}")
            return None
    
    def generate_all_charts(self):
        """Генерирует все 4 графика с подробной отладкой"""
        print("=" * 60)
        print("🔄 Начинаю генерацию всех графиков...")
        
        # Получаем общую статистику о данных
        total_count = self.session.query(Analysis).count()
        abc_count = self.session.query(Analysis).filter(Analysis.abc_category.isnot(None)).count()
        xyz_count = self.session.query(Analysis).filter(Analysis.xyz_category.isnot(None)).count()
        both_count = self.session.query(Analysis).filter(
            Analysis.abc_category.isnot(None),
            Analysis.xyz_category.isnot(None)
        ).count()
        
        print(f"📊 Статистика данных в БД:")
        print(f"   • Всего записей: {total_count}")
        print(f"   • С ABC категорией: {abc_count}")
        print(f"   • С XYZ категорией: {xyz_count}")
        print(f"   • С обеими категориями: {both_count}")
        
        if total_count == 0:
            print("⚠️ В базе данных нет записей!")
        
        # Дополнительная проверка для матрицы
        print(f"\n📊 Проверка данных для матрицы:")
        matrix_check = self.session.query(
            Analysis.abc_category,
            Analysis.xyz_category,
            func.count(Analysis.id).label('count')
        ).filter(
            Analysis.abc_category.in_(['A', 'B', 'C']),
            Analysis.xyz_category.in_(['X', 'Y', 'Z'])
        ).group_by(Analysis.abc_category, Analysis.xyz_category).all()
        
        print(f"   • Найдено комбинаций ABC-XYZ: {len(matrix_check)}")
        for abc, xyz, count in matrix_check:
            print(f"     - {abc}-{xyz}: {count} товаров")
        
        charts = {
            'abc_pie': self.create_abc_pie_chart(),
            'xyz_bar': self.create_xyz_bar_chart(),
            'abc_xyz_matrix': self.create_abc_xyz_matrix(),
            'top_products': self.create_top_products_chart()
        }
        
        # Проверяем какие графики создались
        created_charts = {}
        failed_charts = []
        
        for name, chart in charts.items():
            if chart is not None:
                created_charts[name] = chart
            else:
                failed_charts.append(name)
        
        if not created_charts:
            print("⚠️ Не удалось создать ни одного графика!")
        else:
            print(f"✅ Успешно создано {len(created_charts)} из 4 графиков")
            
            chart_names = {
                'abc_pie': 'ABC Анализ',
                'xyz_bar': 'XYZ Анализ',
                'abc_xyz_matrix': 'Матрица ABC-XYZ',
                'top_products': 'Топ товаров'
            }
            
            for chart_name in created_charts.keys():
                print(f"   ✓ {chart_names.get(chart_name, chart_name)}")
            
            if failed_charts:
                print(f"⚠️ Не созданы графики:")
                for chart_name in failed_charts:
                    print(f"   ✗ {chart_names.get(chart_name, chart_name)}")
        
        print("=" * 60)
        return created_charts
