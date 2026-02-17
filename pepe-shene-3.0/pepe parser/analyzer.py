import json
import math
from pathlib import Path
import pandas as pd
import numpy as np
from collections import defaultdict
from datetime import datetime, timedelta
import statistics

BASE_DIR = Path(__file__).resolve().parent

def perform_abc_analysis(json_file_path, output_file_name="abc_result.json", quantity_column="ШТУК_ЗАКАЗАНО"):
    """
    Выполняет ABC анализ на основе JSON файла с данными
    Анализ проводится по указанному столбцу количества (по умолчанию "ШТУК_ЗАКАЗАНО")
    
    Args:
        json_file_path (str): Путь к JSON файлу с данными
        output_file_name (str): Имя выходного файла с результатами анализа
        quantity_column (str): Название столбца с количеством для анализа
    
    Returns:
        tuple: (путь к файлу результатов, данные анализа) или (None, None) в случае ошибки
    """
    try:
        # Чтение данных из JSON файла
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n📁 Загружено {len(data)} записей из {Path(json_file_path).name}")
        
        if not data:
            print("⚠ Файл не содержит данных для анализа!")
            return None, None
        
        # Проверяем структуру данных
        if not isinstance(data, list):
            print("⚠ Неправильный формат данных. Ожидается список словарей.")
            return None, None
        
        # Определяем доступные столбцы
        sample_item = data[0] if data else {}
        available_columns = list(sample_item.keys())
        
        print(f"📋 Доступные столбцы: {', '.join(available_columns)}")
        
        # Ищем столбец с количеством
        quantity_key = None
        quantity_keys_variants = [
            quantity_column,
            'ШТУК_ЗАКАЗАНО',
            'ШТУК ЗАКАЗАНО',
            'QUANTITY',
            'КОЛИЧЕСТВО',
            'Количество',
            'Кол-во',
            'шт',
            'ШТ'
        ]
        
        for variant in quantity_keys_variants:
            if variant in sample_item:
                quantity_key = variant
                break
        
        if not quantity_key:
            # Пробуем найти частичное совпадение
            for key in sample_item.keys():
                key_lower = str(key).lower()
                if any(pattern in key_lower for pattern in ['шт', 'quantity', 'количеств', 'заказан']):
                    quantity_key = key
                    break
        
        if not quantity_key:
            print(f"⚠ Не найден столбец '{quantity_column}' или аналогичный для анализа!")
            print(f"   Доступные столбцы: {', '.join(available_columns)}")
            return None, None
        
        print(f"🔍 Используется столбец для анализа: '{quantity_key}'")
        
        # Ищем столбец с названием товара
        name_key = None
        name_keys_variants = [
            'НАИМЕНОВАНИЕ',
            'АРТИКУЛ',
            'Название',
            'Наименование',
            'NAME',
            'PRODUCT',
            'ТОВАР'
        ]
        
        for variant in name_keys_variants:
            if variant in sample_item:
                name_key = variant
                break
        
        if not name_key:
            # Пробуем найти частичное совпадение
            for key in sample_item.keys():
                key_lower = str(key).lower()
                if any(pattern in key_lower for pattern in ['наимен', 'артикул', 'name', 'product']):
                    name_key = key
                    break
        
        print(f"📝 Используется столбец для названия: '{name_key}'")
        
        # Группировка по товарам и суммирование количества
        product_stats = defaultdict(float)
        product_names = {}
        product_ids = {}
        
        for idx, item in enumerate(data):
            # Получаем идентификатор товара
            product_id = None
            
            if name_key and name_key in item:
                product_id = item[name_key]
            elif 'АРТИКУЛ' in item:
                product_id = item['АРТИКУЛ']
            elif 'НАИМЕНОВАНИЕ' in item:
                product_id = item['НАИМЕНОВАНИЕ']
            elif 'id' in item:
                product_id = str(item['id'])
            else:
                product_id = f"Товар_{idx + 1}"
            
            if not product_id:
                continue
            
            # Получаем количество
            quantity = 0
            if quantity_key in item:
                try:
                    quantity = float(item[quantity_key])
                except (ValueError, TypeError):
                    try:
                        # Пробуем преобразовать строку
                        quantity = float(str(item[quantity_key]).replace(',', '.'))
                    except:
                        quantity = 0
            
            if quantity > 0:
                product_stats[product_id] += quantity
                
                # Сохраняем название товара
                if name_key and name_key in item:
                    product_names[product_id] = str(item[name_key])
                elif 'НАИМЕНОВАНИЕ' in item:
                    product_names[product_id] = item['НАИМЕНОВАНИЕ']
                else:
                    product_names[product_id] = str(product_id)
                
                # Сохраняем артикул если есть
                if 'АРТИКУЛ' in item:
                    product_ids[product_id] = item['АРТИКУЛ']
                else:
                    product_ids[product_id] = product_id
        
        if not product_stats:
            print(f"⚠ Нет данных о количестве в столбце '{quantity_key}' для анализа")
            return None, None
        
        print(f"📊 Найдено {len(product_stats)} уникальных товаров")
        
        # Преобразуем в список для сортировки
        product_list = []
        total_quantity = sum(product_stats.values())
        
        for product_id, quantity in product_stats.items():
            product_list.append({
                'product_id': product_id,
                'article': product_ids.get(product_id, ''),
                'product_name': product_names.get(product_id, ''),
                'quantity': quantity,
                'share': (quantity / total_quantity) * 100 if total_quantity > 0 else 0
            })
        
        # Сортируем по убыванию количества
        product_list.sort(key=lambda x: x['quantity'], reverse=True)
        
        # ABC классификация
        cumulative_percentage = 0
        for item in product_list:
            cumulative_percentage += item['share']
            
            if cumulative_percentage <= 80:
                item['abc_category'] = 'A'
            elif cumulative_percentage <= 95:
                item['abc_category'] = 'B'
            else:
                item['abc_category'] = 'C'
            
            item['cumulative_share'] = cumulative_percentage
        
        # Группировка по категориям
        category_stats = defaultdict(list)
        for item in product_list:
            category = item['abc_category']
            category_stats[category].append({
                'product_id': item['product_id'],
                'article': item['article'],
                'product_name': item['product_name'],
                'quantity': item['quantity'],
                'share': item['share'],
                'cumulative_share': item['cumulative_share']
            })
        
        # Формируем результат
        result = {
            'general_info': {
                'records_count': len(data),
                'products_count': len(product_list),
                'total_quantity': total_quantity,
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source_file': Path(json_file_path).name,
                'quantity_column': quantity_key,
                'name_column': name_key
            },
            'abc_results': {
                'category_A': category_stats.get('A', []),
                'category_B': category_stats.get('B', []),
                'category_C': category_stats.get('C', [])
            },
            'category_statistics': {
                'A': {
                    'products_count': len(category_stats.get('A', [])),
                    'quantity_share': sum(item['share'] for item in category_stats.get('A', [])),
                    'products_share': (len(category_stats.get('A', [])) / len(product_list)) * 100
                },
                'B': {
                    'products_count': len(category_stats.get('B', [])),
                    'quantity_share': sum(item['share'] for item in category_stats.get('B', [])),
                    'products_share': (len(category_stats.get('B', [])) / len(product_list)) * 100
                },
                'C': {
                    'products_count': len(category_stats.get('C', [])),
                    'quantity_share': sum(item['share'] for item in category_stats.get('C', [])),
                    'products_share': (len(category_stats.get('C', [])) / len(product_list)) * 100
                }
            },
            'top_10_products': product_list[:10]
        }
        
        # Определяем путь для сохранения результатов
        results_path = BASE_DIR / "analysis_results"
        results_path.mkdir(exist_ok=True, parents=True)
        
        output_path = results_path / output_file_name
        
        # Сохраняем результат
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        # Создаем CSV файл для удобства просмотра
        csv_path = results_path / output_file_name.replace('.json', '_abc.csv')
        df_data = []
        for item in product_list:
            df_data.append({
                'Артикул': item['article'],
                'Наименование': item['product_name'][:100] if item['product_name'] else '',
                'Количество_шт': int(item['quantity']),
                'Доля_%': round(item['share'], 2),
                'Кумулятивная_доля_%': round(item['cumulative_share'], 2),
                'ABC_Категория': item['abc_category']
            })
        
        df = pd.DataFrame(df_data)
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        # Вывод результатов в консоль
        print(f"\n{'='*60}")
        print("📊 РЕЗУЛЬТАТЫ ABC-АНАЛИЗА ПО КОЛИЧЕСТВУ")
        print('='*60)
        print(f"Общее количество: {total_quantity:,.0f} шт.")
        print(f"Количество уникальных товаров: {len(product_list)}")
        print(f"Дата анализа: {result['general_info']['analysis_date']}")
        
        print(f"\n{'='*60}")
        print("📈 РАСПРЕДЕЛЕНИЕ ПО КАТЕГОРИЯМ:")
        print('='*60)
        for category in ['A', 'B', 'C']:
            stats = result['category_statistics'][category]
            print(f"\nКатегория {category}:")
            print(f"  • Количество товаров: {stats['products_count']} ({stats['products_share']:.1f}% всех товаров)")
            print(f"  • Доля от общего количества: {stats['quantity_share']:.1f}%")
        
        print(f"\n{'='*60}")
        print("🏆 ТОП-10 ТОВАРОВ ПО КОЛИЧЕСТВУ:")
        print('='*60)
        for i, item in enumerate(result['top_10_products'], 1):
            name = item['product_name'] if item['product_name'] else item['article']
            name_display = name[:50] + '...' if len(name) > 50 else name
            print(f"{i}. {name_display}")
            print(f"   Количество: {item['quantity']:,.0f} шт. ({item['share']:.1f}%) - Категория: {item['abc_category']}")
        
        print(f"\n✅ Анализ завершен. Результаты сохранены:")
        print(f"  📄 JSON: {output_path}")
        print(f"  📊 CSV:  {csv_path}")
        
        # Возвращаем данные для дальнейшего использования
        abc_data = []
        for idx, item in enumerate(product_list):
            abc_data.append({
                'id': idx + 1,
                'name': item['product_name'] if item['product_name'] else item['article'],
                'quantity': item['quantity'],
                'revenue': 0,  # Для совместимости с другими функциями
                'ABC': item['abc_category']
            })
        
        return str(output_path), abc_data
        
    except FileNotFoundError:
        print(f"❌ Файл {json_file_path} не найден!")
        return None, None
    except json.JSONDecodeError:
        print(f"❌ Ошибка чтения JSON файла {json_file_path}")
        return None, None
    except Exception as e:
        print(f"❌ Ошибка при выполнении анализа: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def perform_xyz_analysis(json_file_path, output_file_name="xyz_result.json"):
    """
    Выполняет XYZ анализ на основе исторических данных о продажах
    Требует данных по периодам времени
    
    Args:
        json_file_path (str): Путь к JSON файлу с данными
        output_file_name (str): Имя выходного файла с результатами анализа
    
    Returns:
        tuple: (путь к файлу результатов, данные анализа) или (None, None) в случае ошибки
    """
    try:
        # Чтение данных из JSON файла
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n📈 XYZ анализ: загружено {len(data)} записей")
        
        if not data:
            print("⚠ Нет данных для XYZ анализа")
            return None, None
        
        # Проверяем наличие временных данных
        sample_item = data[0] if data else {}
        
        # Ищем временные метки
        date_keys = []
        for key in sample_item.keys():
            key_lower = str(key).lower()
            if any(pattern in key_lower for pattern in ['date', 'дата', 'time', 'время', 'period', 'период', 'quarter', 'квартал', 'month', 'месяц']):
                date_keys.append(key)
        
        # Ищем данные по кварталам/месяцам
        period_data_found = False
        period_keys = []
        
        for key in sample_item.keys():
            key_lower = str(key).lower()
            if any(pattern in key_lower for pattern in ['q1', 'q2', 'q3', 'q4', 'quarter', 'квартал', 'month', 'месяц']):
                period_keys.append(key)
                period_data_found = True
        
        if not period_data_found and len(date_keys) < 1:
            print("⚠ Для XYZ анализа нужны данные по периодам или временные метки")
            print("   В предоставленных данных нет информации о периодах")
            print("   Всем товарам будет назначена категория Z (нерегулярный спрос)")
            
            # Создаем простой XYZ анализ с категорией Z для всех товаров
            return _xyz_simple(data, output_file_name)
        
        # Анализируем данные
        if period_data_found:
            print(f"🔍 Найдены данные по периодам: {period_keys}")
            return _xyz_from_periods(data, period_keys, output_file_name)
        elif date_keys:
            print(f"🔍 Найдены временные метки: {date_keys}")
            return _xyz_from_dates(data, date_keys, output_file_name)
        else:
            print("⚠ Не удалось определить структуру данных для XYZ анализа")
            return None, None
        
    except Exception as e:
        print(f"❌ Ошибка при выполнении XYZ анализа: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def _xyz_simple(data, output_file_name):
    """Создает простой XYZ анализ с категорией Z для всех товаров"""
    try:
        # Находим столбец с названием товара
        name_key = None
        for key in data[0].keys() if data else []:
            key_lower = str(key).lower()
            if any(pattern in key_lower for pattern in ['наимен', 'артикул', 'name', 'product']):
                name_key = key
                break
        
        xyz_results = []
        
        for idx, item in enumerate(data):
            product_id = None
            
            if name_key and name_key in item:
                product_id = item[name_key]
            elif 'АРТИКУЛ' in item:
                product_id = item['АРТИКУЛ']
            elif 'НАИМЕНОВАНИЕ' in item:
                product_id = item['НАИМЕНОВАНИЕ']
            elif 'id' in item:
                product_id = str(item['id'])
            else:
                product_id = f"Товар_{idx + 1}"
            
            xyz_results.append({
                'product_id': product_id,
                'product_name': str(product_id),
                'xyz_category': 'Z',  # Нерегулярный спрос по умолчанию
                'mean': 0,
                'std_dev': 0,
                'cv_percent': 100,
                'period_values': []
            })
        
        # Сохраняем результаты
        result = {
            'general_info': {
                'total_products': len(xyz_results),
                'periods_count': 0,
                'periods_names': [],
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'note': 'XYZ анализ выполнен в упрощенном режиме (все товары категории Z)'
            },
            'xyz_distribution': {
                'X': 0,
                'Y': 0,
                'Z': len(xyz_results)
            },
            'xyz_results': xyz_results
        }
        
        # Сохраняем в файл
        results_path = BASE_DIR / "analysis_results"
        results_path.mkdir(exist_ok=True, parents=True)
        
        output_path = results_path / output_file_name
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n✅ XYZ анализ завершен (упрощенный режим):")
        print(f"   Все товары отнесены к категории Z (нерегулярный спрос)")
        print(f"   Причина: отсутствие данных по периодам для анализа стабильности")
        
        return str(output_path), xyz_results
        
    except Exception as e:
        print(f"❌ Ошибка при упрощенном XYZ анализе: {e}")
        return None, None

def _xyz_from_periods(data, period_keys, output_file_name):
    """XYZ анализ на основе данных по периодам"""
    try:
        # Группируем данные по товарам
        product_periods = defaultdict(list)
        product_names = {}
        
        # Определяем ключ названия товара
        name_key = None
        for key in data[0].keys():
            key_lower = str(key).lower()
            if any(pattern in key_lower for pattern in ['name', 'наимен', 'product', 'товар', 'артикул']):
                name_key = key
                break
        
        for item in data:
            product_id = None
            if name_key and name_key in item:
                product_id = item[name_key]
            elif 'АРТИКУЛ' in item:
                product_id = item['АРТИКУЛ']
            elif 'НАИМЕНОВАНИЕ' in item:
                product_id = item['НАИМЕНОВАНИЕ']
            elif 'id' in item:
                product_id = str(item['id'])
            
            if not product_id:
                continue
            
            # Собираем данные по периодам
            period_values = []
            for period_key in period_keys:
                if period_key in item:
                    try:
                        value = float(item[period_key])
                        period_values.append(value)
                    except (ValueError, TypeError):
                        period_values.append(0)
            
            if period_values and any(v > 0 for v in period_values):
                product_periods[product_id].append(period_values)
                if product_id not in product_names:
                    product_names[product_id] = str(product_id)
        
        if not product_periods:
            print("⚠ Нет числовых данных по периодам")
            return None, None
        
        # Анализируем вариативность для каждого товара
        xyz_results = []
        
        for product_id, periods_list in product_periods.items():
            # Берем последний набор периодов
            if periods_list:
                values = periods_list[-1]
                
                if len(values) >= 3:  # Нужно минимум 3 периода для анализа
                    # Рассчитываем коэффициент вариации
                    mean_val = statistics.mean(values) if values else 0
                    std_dev = statistics.stdev(values) if len(values) > 1 else 0
                    
                    cv = (std_dev / mean_val * 100) if mean_val > 0 else 0
                    
                    # Определяем XYZ категорию
                    if cv <= 10:
                        xyz_category = 'X'  # Стабильный спрос
                    elif cv <= 25:
                        xyz_category = 'Y'  # Сезонные колебания
                    else:
                        xyz_category = 'Z'  # Нерегулярный спрос
                    
                    xyz_results.append({
                        'product_id': product_id,
                        'product_name': product_names.get(product_id, ''),
                        'period_values': values,
                        'mean': mean_val,
                        'std_dev': std_dev,
                        'cv_percent': cv,
                        'xyz_category': xyz_category
                    })
        
        if not xyz_results:
            print("⚠ Недостаточно данных для XYZ анализа (нужно минимум 3 периода)")
            return _xyz_simple(data, output_file_name)
        
        # Сохраняем результаты
        result = {
            'general_info': {
                'total_products': len(xyz_results),
                'periods_count': len(period_keys),
                'periods_names': period_keys,
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            'xyz_distribution': {
                'X': len([x for x in xyz_results if x['xyz_category'] == 'X']),
                'Y': len([x for x in xyz_results if x['xyz_category'] == 'Y']),
                'Z': len([x for x in xyz_results if x['xyz_category'] == 'Z'])
            },
            'xyz_results': xyz_results
        }
        
        # Сохраняем в файл
        results_path = BASE_DIR / "analysis_results"
        results_path.mkdir(exist_ok=True, parents=True)
        
        output_path = results_path / output_file_name
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        # CSV файл
        csv_path = results_path / output_file_name.replace('.json', '_xyz.csv')
        df_data = []
        for item in xyz_results:
            df_data.append({
                'Product_ID': item['product_id'],
                'Product_Name': item['product_name'][:100] if item['product_name'] else '',
                'Mean_Value': item['mean'],
                'Std_Deviation': item['std_dev'],
                'CV_%': round(item['cv_percent'], 2),
                'XYZ_Category': item['xyz_category']
            })
        
        df = pd.DataFrame(df_data)
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        print(f"\n✅ XYZ анализ завершен:")
        print(f"   X (стабильные): {result['xyz_distribution']['X']} товаров")
        print(f"   Y (сезонные): {result['xyz_distribution']['Y']} товаров")
        print(f"   Z (нерегулярные): {result['xyz_distribution']['Z']} товаров")
        print(f"📁 Результаты сохранены в: {output_path}")
        
        return str(output_path), xyz_results
        
    except Exception as e:
        print(f"❌ Ошибка при анализе периодов: {e}")
        return None, None

def _xyz_from_dates(data, date_keys, output_file_name):
    """XYZ анализ на основе временных меток"""
    print("ℹ️ XYZ анализ по датам требует агрегации данных по периодам")
    print("   Рекомендуется предоставить данные уже сгруппированные по кварталам/месяцам")
    
    # Возвращаем упрощенный анализ
    return _xyz_simple(data, output_file_name)

def perform_abc_xyz_analysis(json_file_path, output_file_name="abc_xyz_result.json", quantity_column="ШТУК_ЗАКАЗАНО"):
    """
    Выполняет комбинированный ABC-XYZ анализ
    
    Args:
        json_file_path (str): Путь к JSON файлу с данными
        output_file_name (str): Имя выходного файла с результатами анализа
        quantity_column (str): Название столбца с количеством для ABC анализа
    
    Returns:
        list: Список результатов для загрузки в БД
    """
    try:
        print(f"\n{'='*60}")
        print("🎯 КОМБИНИРОВАННЫЙ ABC-XYZ АНАЛИЗ")
        print('='*60)
        
        # Сначала выполняем ABC анализ по количеству
        abc_result_path, abc_data = perform_abc_analysis(
            json_file_path, 
            "abc_analysis.json",
            quantity_column
        )
        
        if not abc_data:
            print("❌ ABC анализ не удался, прерываем комбинированный анализ")
            return []
        
        # Пытаемся выполнить XYZ анализ
        xyz_result_path, xyz_data = perform_xyz_analysis(json_file_path, "xyz_analysis.json")
        
        # Если XYZ анализ не удался, назначаем всем товарам категорию Z
        if not xyz_data:
            print("⚠ XYZ анализ не удался, назначаем всем товарам категорию Z (нерегулярный спрос)")
            xyz_data = []
            for item in abc_data:
                xyz_data.append({
                    'product_id': item['name'],
                    'product_name': item['name'],
                    'xyz_category': 'Z'
                })
        
        # Объединяем результаты
        combined_results = []
        
        # Создаем словарь XYZ категорий
        xyz_dict = {}
        for item in xyz_data:
            if isinstance(item, dict):
                product_id = item.get('product_id') or item.get('product_name') or item.get('name')
                if product_id:
                    xyz_dict[str(product_id)] = item.get('xyz_category', 'Z')
        
        # Объединяем ABC и XYZ
        for item in abc_data:
            product_id = item['name']
            xyz_category = xyz_dict.get(str(product_id), 'Z')
            abc_category = item['ABC']
            
            combined_results.append({
                'id': item['id'],
                'name': item['name'],
                'quantity': item['quantity'],
                'revenue': item.get('revenue', 0),
                'ABC': abc_category,
                'XYZ': xyz_category,
                'ABC_XYZ': f"{abc_category}{xyz_category}"
            })
        
        # Сохраняем комбинированные результаты
        result = {
            'general_info': {
                'total_products': len(combined_results),
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source_file': Path(json_file_path).name,
                'quantity_column': quantity_column
            },
            'distribution': {
                'abc': {
                    'A': len([x for x in combined_results if x['ABC'] == 'A']),
                    'B': len([x for x in combined_results if x['ABC'] == 'B']),
                    'C': len([x for x in combined_results if x['ABC'] == 'C'])
                },
                'xyz': {
                    'X': len([x for x in combined_results if x['XYZ'] == 'X']),
                    'Y': len([x for x in combined_results if x['XYZ'] == 'Y']),
                    'Z': len([x for x in combined_results if x['XYZ'] == 'Z'])
                },
                'abc_xyz': defaultdict(int)
            },
            'matrix': defaultdict(list),
            'results': combined_results
        }
        
        # Заполняем матрицу ABC-XYZ
        for item in combined_results:
            key = f"{item['ABC']}{item['XYZ']}"
            result['distribution']['abc_xyz'][key] += 1
            result['matrix'][key].append(item)
        
        # Сохраняем в файл
        results_path = BASE_DIR / "analysis_results"
        results_path.mkdir(exist_ok=True, parents=True)
        
        output_path = results_path / output_file_name
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        # CSV файл
        csv_path = results_path / output_file_name.replace('.json', '.csv')
        df_data = []
        for item in combined_results:
            df_data.append({
                'ID': item['id'],
                'Product_Name': item['name'],
                'Quantity': item['quantity'],
                'Revenue': item['revenue'],
                'ABC_Category': item['ABC'],
                'XYZ_Category': item['XYZ'],
                'ABC_XYZ_Matrix': item['ABC_XYZ']
            })
        
        df = pd.DataFrame(df_data)
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        # Вывод статистики
        print(f"\n📊 СТАТИСТИКА КОМБИНИРОВАННОГО АНАЛИЗА:")
        print(f"   Всего товаров: {len(combined_results)}")
        
        print(f"\n📈 ABC распределение (по количеству):")
        abc_stats = result['distribution']['abc']
        for cat in ['A', 'B', 'C']:
            count = abc_stats[cat]
            percentage = (count / len(combined_results)) * 100
            print(f"   • {cat}: {count} товаров ({percentage:.1f}%)")
        
        print(f"\n📊 XYZ распределение:")
        xyz_stats = result['distribution']['xyz']
        for cat in ['X', 'Y', 'Z']:
            count = xyz_stats[cat]
            percentage = (count / len(combined_results)) * 100
            print(f"   • {cat}: {count} товаров ({percentage:.1f}%)")
        
        print(f"\n🎯 МАТРИЦА ABC-XYZ:")
        matrix_stats = result['distribution']['abc_xyz']
        abc_cats = ['A', 'B', 'C']
        xyz_cats = ['X', 'Y', 'Z']
        
        print("       X     Y     Z")
        print("   " + "-"*20)
        
        for abc in abc_cats:
            row = f"{abc} | "
            for xyz in xyz_cats:
                key = f"{abc}{xyz}"
                count = matrix_stats.get(key, 0)
                row += f"{count:^5} "
            print(row)
        
        print(f"\n✅ Комбинированный анализ завершен:")
        print(f"   📄 JSON: {output_path}")
        print(f"   📊 CSV:  {csv_path}")
        
        return combined_results
        
    except Exception as e:
        print(f"❌ Ошибка при комбинированном анализе: {e}")
        import traceback
        traceback.print_exc()
        return []

def analyze_folder(json_folder, output_folder="analysis_results", quantity_column="ШТУК_ЗАКАЗАНО"):
    """
    Выполняет анализ для всех JSON файлов в папке
    
    Args:
        json_folder (str): Папка с JSON файлами
        output_folder (str): Подпапка для сохранения результатов
        quantity_column (str): Название столбца с количеством для анализа
    
    Returns:
        list: Список обработанных файлов
    """
    json_path = Path(json_folder)
    
    if not json_path.exists():
        print(f"❌ Папка {json_folder} не найдена!")
        return []
    
    json_files = list(json_path.glob("*.json"))
    
    if not json_files:
        print(f"⚠ Папка {json_folder} не содержит JSON файлов!")
        return []
    
    print(f"📁 Найдено {len(json_files)} JSON файлов для анализа:")
    
    processed_files = []
    
    for json_file in json_files:
        print(f"\n{'='*60}")
        print(f"🔍 Анализ файла: {json_file.name}")
        print('='*60)
        
        # ABC-XYZ анализ
        results = perform_abc_xyz_analysis(
            str(json_file), 
            f"{json_file.stem}_analysis.json",
            quantity_column
        )
        
        if results:
            processed_files.append({
                'input': str(json_file),
                'output': f"{json_file.stem}_analysis.json",
                'results_count': len(results),
                'results': results
            })
    
    return processed_files

def create_summary_report(processed_files, output_file="analysis_summary.csv"):
    """
    Создает сводный отчет по всем проанализированным файлам
    
    Args:
        processed_files (list): Список обработанных файлов
        output_file (str): Имя файла для сводного отчета
    """
    if not processed_files:
        print("⚠ Нет данных для создания сводного отчета")
        return
    
    summary_data = []
    
    for file_info in processed_files:
        input_file = Path(file_info['input'])
        
        # Создаем сводку по файлу
        abc_counts = {'A': 0, 'B': 0, 'C': 0}
        xyz_counts = {'X': 0, 'Y': 0, 'Z': 0}
        total_quantity = 0
        
        if 'results' in file_info:
            for item in file_info['results']:
                abc = item.get('ABC', '')
                xyz = item.get('XYZ', '')
                quantity = item.get('quantity', 0)
                
                if abc in abc_counts:
                    abc_counts[abc] += 1
                if xyz in xyz_counts:
                    xyz_counts[xyz] += 1
                
                total_quantity += quantity
        
        summary_data.append({
            'Файл': input_file.name,
            'Всего_товаров': file_info.get('results_count', 0),
            'Общее_количество_шт': total_quantity,
            'Категория_A': abc_counts['A'],
            'Категория_B': abc_counts['B'],
            'Категория_C': abc_counts['C'],
            'Категория_X': xyz_counts['X'],
            'Категория_Y': xyz_counts['Y'],
            'Категория_Z': xyz_counts['Z'],
            'Доля_A_%': (abc_counts['A'] / file_info.get('results_count', 1)) * 100,
            'Доля_X_%': (xyz_counts['X'] / file_info.get('results_count', 1)) * 100
        })
    
    if summary_data:
        df_summary = pd.DataFrame(summary_data)
        
        # Определяем путь для сохранения
        if processed_files:
            output_path = BASE_DIR / "analysis_results" / output_file
        else:
            output_path = BASE_DIR / "analysis_results" / output_file
        
        output_path.parent.mkdir(exist_ok=True, parents=True)
        
        df_summary.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n✅ Сводный отчет сохранен: {output_path}")
        print("\n📊 Сводные данные:")
        print(df_summary.to_string(index=False))

def test_analysis():
    """
    Тестирует анализ на примере данных
    """
    # Пример данных для тестирования
    test_data = [
        {
            "АРТИКУЛ": "PFSP29788",
            "НАИМЕНОВАНИЕ": "Торт Красный бархат С.Пудовъ, Россия, фасовка 400 г, 1/400",
            "ШТУК_ЗАКАЗАНО": 624,
            "q1": 150,
            "q2": 180,
            "q3": 145,
            "q4": 149
        },
        {
            "АРТИКУЛ": "PFSP29788",
            "НАИМЕНОВАНИЕ": "Торт Красный бархат С.Пудовъ, Россия, фасовка 400 г, 1/400",
            "ШТУК_ЗАКАЗАНО": 32,
            "q1": 8,
            "q2": 9,
            "q3": 7,
            "q4": 8
        },
        {
            "АРТИКУЛ": "SFSS03145",
            "НАИМЕНОВАНИЕ": "Мучная смесь \"Блины\" т.м. \"Сем ейные секреты\", бум/пак, 0,5 к",
            "ШТУК_ЗАКАЗАНО": 12,
            "q1": 5,
            "q2": 3,
            "q3": 2,
            "q4": 2
        }
    ]
    
    # Сохраняем тестовые данные
    test_file = "test_data.json"
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    
    print(f"📁 Создан тестовый файл: {test_file}")
    print("🔍 Запуск ABC анализа по столбцу 'ШТУК_ЗАКАЗАНО'...")
    
    # Запускаем анализ
    results = perform_abc_xyz_analysis(test_file, "test_analysis.json")
    
    if results:
        print(f"\n✅ Тестовый анализ завершен успешно!")
        print(f"   Обработано товаров: {len(results)}")
        
        # Показываем результаты
        print("\n📋 Результаты:")
        for item in results:
            print(f"   • {item['name']}: {item['quantity']} шт., ABC={item['ABC']}, XYZ={item['XYZ']}")
    
    # Удаляем тестовый файл
    try:
        Path(test_file).unlink()
        print(f"\n🗑️ Тестовый файл удален")
    except:
        pass

if __name__ == "__main__":
    print("🔍 ABC-XYZ АНАЛИЗАТОР ДАННЫХ")
    print("="*60)
    print("📊 Анализ по количеству (столбец 'ШТУК_ЗАКАЗАНО')")
    print("="*60)
    
    # Проверяем аргументы командной строки
    import sys
    if len(sys.argv) > 1:
        # Если передан аргумент - путь к файлу
        file_path = sys.argv[1]
        print(f"Запуск анализа для файла: {file_path}")
        
        if len(sys.argv) > 2:
            quantity_column = sys.argv[2]
        else:
            quantity_column = "ШТУК_ЗАКАЗАНО"
            
        results = perform_abc_xyz_analysis(file_path, quantity_column=quantity_column)
        
        if results:
            print(f"\n✅ Анализ завершен. Обработано {len(results)} товаров.")
            
            # Создаем сводный отчет
            create_summary_report([{
                'input': file_path,
                'results': results,
                'results_count': len(results)
            }])
    else:
        print("Запуск в интерактивном режиме")
        print("\nДоступные команды:")
        print("  1. Протестировать анализ на примере")
        print("  2. Проанализировать существующий файл")
        print("  3. Проанализировать папку с JSON файлами")
        
        choice = input("\nВыберите действие (1-3): ").strip()
        
        if choice == "1":
            # Тестируем анализ
            test_analysis()
        
        elif choice == "2":
            # Анализ файла
            file_path = input("Введите путь к JSON файлу: ").strip()
            quantity_col = input("Введите название столбца с количеством [по умолчанию: ШТУК_ЗАКАЗАНО]: ").strip()
            
            if not quantity_col:
                quantity_col = "ШТУК_ЗАКАЗАНО"
            
            if Path(file_path).exists():
                results = perform_abc_xyz_analysis(file_path, quantity_column=quantity_col)
                if results:
                    print(f"\n✅ Анализ завершен. Обработано {len(results)} товаров.")
            else:
                print(f"❌ Файл {file_path} не найден!")
        
        elif choice == "3":
            # Анализ папки
            folder_path = input("Введите путь к папке с JSON файлами: ").strip()
            quantity_col = input("Введите название столбца с количеством [по умолчанию: ШТУК_ЗАКАЗАНО]: ").strip()
            
            if not quantity_col:
                quantity_col = "ШТУК_ЗАКАЗАНО"
            
            processed_files = analyze_folder(folder_path, quantity_column=quantity_col)
            
            if processed_files:
                create_summary_report(processed_files)
                print(f"\n✅ Анализ папки завершен. Обработано {len(processed_files)} файлов.")
        
        else:
            print("❌ Неверный выбор")
