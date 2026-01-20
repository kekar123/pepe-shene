import json
import math
from pathlib import Path

def perform_abc_xyz_analysis(json_file_path, output_file_name="abc_xyz_result.json"):
    """
    Выполняет ABC-XYZ анализ на основе JSON файла
    
    Args:
        json_file_path (str): Путь к JSON файлу с данными
        output_file_name (str): Имя выходного файла с результатами анализа
    
    Returns:
        str: Путь к файлу с результатами анализа или None в случае ошибки
    """
    try:
        # Чтение данных из JSON файла
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\nЗагружено {len(data)} записей из {Path(json_file_path).name}")
        
        # Фильтрация данных - оставляем только элементы с числовым ID
        items = [i for i in data if isinstance(i.get('№'), (int, float))]
        print(f"После фильтрации осталось {len(items)} записей")
        
        if not items:
            print("⚠ Нет данных для анализа после фильтрации!")
            return None
        
        # ABC анализ (по выручке)
        items.sort(key=lambda x: x.get('Выручка (У.Е.)', 0), reverse=True)
        total_revenue = sum(i.get('Выручка (У.Е.)', 0) for i in items)
        
        if total_revenue <= 0:
            print("⚠ Общая выручка равна 0, ABC анализ невозможен!")
            return None
        
        cumulative = 0
        
        for item in items:
            revenue = item.get('Выручка (У.Е.)', 0)
            cumulative += revenue
            percentage = (cumulative / total_revenue) * 100
            
            if percentage <= 80:
                item['ABC'] = 'A'
            elif percentage <= 95:
                item['ABC'] = 'B'
            else:
                item['ABC'] = 'C'
        
        # XYZ анализ (по стабильности продаж по кварталам)
        for item in items:
            # Извлекаем квартальные данные
            quarters = [
                item.get('Выручка по кварталам (У.Е.)', 0),
                item.get('Unnamed: 4', 0),
                item.get('Unnamed: 5', 0),
                item.get('Unnamed: 6', 0)
            ]
            
            avg = sum(quarters) / len(quarters)
            
            if avg > 0:
                variance = sum((q - avg) ** 2 for q in quarters) / len(quarters)
                cv = (math.sqrt(variance) / avg) * 100  # Коэффициент вариации
            else:
                cv = 100  # Если среднее равно 0, считаем максимальную нестабильность
            
            if cv <= 15:
                item['XYZ'] = 'X'
            elif cv <= 25:
                item['XYZ'] = 'Y'
            else:
                item['XYZ'] = 'Z'
            
            item['ABC_XYZ'] = item['ABC'] + item['XYZ']
        
        # Формируем результат в удобном формате
        result = []
        for item in items:
            result_item = {
                'id': int(item.get('№', 0)),
                'name': item.get('Наименование товара', ''),
                'revenue': item.get('Выручка (У.Е.)', 0),
                'ABC': item.get('ABC', ''),
                'XYZ': item.get('XYZ', ''),
                'ABC_XYZ': item.get('ABC_XYZ', '')
            }
            result.append(result_item)
        
        # Определяем путь для сохранения результатов
        json_path = Path(json_file_path)
        results_path = json_path.parent / "analysis_results"
        results_path.mkdir(exist_ok=True)
        
        output_path = results_path / output_file_name
        
        # Сохраняем результат
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"✓ Анализ завершен. Результат сохранен в: {output_path}")
        
        # Дополнительная статистика
        abc_stats = {}
        xyz_stats = {}
        abc_xyz_stats = {}
        
        for item in items:
            abc_stats[item['ABC']] = abc_stats.get(item['ABC'], 0) + 1
            xyz_stats[item['XYZ']] = xyz_stats.get(item['XYZ'], 0) + 1
            abc_xyz_stats[item['ABC_XYZ']] = abc_xyz_stats.get(item['ABC_XYZ'], 0) + 1
        
        print("\nСтатистика анализа:")
        print(f"ABC распределение: {abc_stats}")
        print(f"XYZ распределение: {xyz_stats}")
        print(f"ABC-XYZ матрица: {abc_xyz_stats}")
        
        return str(output_path)
        
    except FileNotFoundError:
        print(f"✗ Файл {json_file_path} не найден!")
        return None
    except json.JSONDecodeError:
        print(f"✗ Ошибка чтения JSON файла {json_file_path}")
        return None
    except Exception as e:
        print(f"✗ Ошибка при выполнении анализа: {e}")
        return None

def analyze_folder(json_folder, output_folder="analysis_results"):
    """
    Выполняет ABC-XYZ анализ для всех JSON файлов в папке
    
    Args:
        json_folder (str): Папка с JSON файлами
        output_folder (str): Подпапка для сохранения результатов
    
    Returns:
        list: Список обработанных файлов
    """
    json_path = Path(json_folder)
    
    if not json_path.exists():
        print(f"✗ Папка {json_folder} не найдена!")
        return []
    
    json_files = list(json_path.glob("*.json"))
    
    if not json_files:
        print(f"⚠ Папка {json_folder} не содержит JSON файлов!")
        return []
    
    print(f"Найдено {len(json_files)} JSON файлов для анализа:")
    
    processed_files = []
    
    for json_file in json_files:
        print(f"\nАнализ файла: {json_file.name}")
        result_path = perform_abc_xyz_analysis(str(json_file), f"{json_file.stem}_analysis.json")
        
        if result_path:
            processed_files.append({
                'input': str(json_file),
                'output': result_path
            })
    
    return processed_files