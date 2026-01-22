import pandas as pd
import json
from pathlib import Path

def xls_to_json_batch(input_folder, output_folder, sheet_name=0):
    """
    Парсер всех XLS/XLSX файлов из папки в JSON файлы в другую папку
    
    Args:
        input_folder (str): Путь к папке с XLS/XLSX файлами
        output_folder (str): Путь к папке для сохранения JSON файлов
        sheet_name (int/str): Номер или имя листа для чтения (по умолчанию: 0)
    
    Returns:
        list: Список обработанных файлов с метаданными
    """
    # Создаем объекты Path для удобной работы с путями
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    
    # Проверяем существование входной папки
    if not input_path.exists():
        raise FileNotFoundError(f"Папка {input_folder} не найдена!")
    
    # Создаем выходную папку, если она не существует
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Получаем список всех XLS/XLSX файлов
    excel_files = list(input_path.glob("*.xlsx")) + list(input_path.glob("*.xls"))
    
    if not excel_files:
        print("⚠ Входная папка не содержит XLS/XLSX файлов!")
        return []
    
    print(f"Найдено {len(excel_files)} файлов для обработки:")
    
    processed_files = []
    
    for excel_file in excel_files:
        try:
            print(f"\nОбработка файла: {excel_file.name}")
            
            # Чтение Excel файла
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            
            # Формируем имя выходного JSON файла
            json_file_name = excel_file.stem + ".json"
            json_file_path = output_path / json_file_name
            
            # Конвертация в JSON и сохранение
            json_data = df.to_json(orient='records', force_ascii=False, indent=2)
            
            with open(json_file_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
            
            print(f"✓ JSON сохранен в: {json_file_path}")
            
            processed_files.append({
                'input': str(excel_file),
                'output': str(json_file_path),
                'rows': len(df),
                'columns': len(df.columns),
                'file_name': json_file_name
            })
            
        except Exception as e:
            print(f"✗ Ошибка при обработке файла {excel_file.name}: {e}")
    
    return processed_files

# Функция для парсинга одного файла
def xls_to_json_single(input_file, output_folder, sheet_name=0):
    """
    Парсит один XLS/XLSX файл в JSON
    
    Args:
        input_file (str): Путь к XLS/XLSX файлу
        output_folder (str): Путь к папке для сохранения JSON файла
        sheet_name (int/str): Номер или имя листа для чтения
    
    Returns:
        dict: Метаданные обработанного файла или None в случае ошибки
    """
    input_path = Path(input_file)
    output_path = Path(output_folder)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Файл {input_file} не найден!")
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        print(f"Обработка файла: {input_path.name}")
        
        df = pd.read_excel(input_path, sheet_name=sheet_name)
        
        json_file_name = input_path.stem + ".json"
        json_file_path = output_path / json_file_name
        
        json_data = df.to_json(orient='records', force_ascii=False, indent=2)
        
        with open(json_file_path, 'w', encoding='utf-8') as f:
            f.write(json_data)
        
        print(f"✓ JSON сохранен в: {json_file_path}")
        
        return {
            'input': str(input_path),
            'output': str(json_file_path),
            'rows': len(df),
            'columns': len(df.columns),
            'file_name': json_file_name
        }
        
    except Exception as e:
        print(f"✗ Ошибка при обработке файла {input_path.name}: {e}")
        return None