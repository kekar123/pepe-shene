import sys
from pathlib import Path
from parser import xls_to_json_batch, xls_to_json_single
from analyzer import perform_abc_xyz_analysis, analyze_folder

def main():
    """
    Основная программа: парсит Excel файлы и выполняет ABC-XYZ анализ
    """
    # Папки по умолчанию
    input_excel_folder = "input_excel"
    output_json_folder = "output_json"
    
    try:
        print("=" * 60)
        print("СИСТЕМА ПАРСИНГА И АНАЛИЗА ДАННЫХ")
        print("=" * 60)
        
        # Шаг 1: Парсинг Excel файлов в JSON
        print("\n1. ПАРСИНГ EXCEL ФАЙЛОВ В JSON")
        print("-" * 40)
        
        results = xls_to_json_batch(
            input_folder=input_excel_folder,
            output_folder=output_json_folder,
            sheet_name=0
        )
        
        if not results:
            print("Нет файлов для анализа. Программа завершена.")
            return
        
        # Выводим сводку по парсингу
        print("\n" + "=" * 50)
        print("СВОДКА ПАРСИНГА:")
        print("=" * 50)
        
        for result in results:
            print(f"\nФайл: {Path(result['input']).name}")
            print(f"  • Строк: {result['rows']}")
            print(f"  • Столбцов: {result['columns']}")
            print(f"  • JSON: {Path(result['output']).name}")
        
        print(f"\n✓ Всего обработано файлов: {len(results)}")
        print(f"✓ JSON файлы сохранены в папке: {output_json_folder}")
        
        # Шаг 2: ABC-XYZ анализ
        print("\n\n2. ВЫПОЛНЕНИЕ ABC-XYZ АНАЛИЗА")
        print("-" * 40)
        
        # Анализируем все JSON файлы в папке
        analysis_results = analyze_folder(output_json_folder)
        
        if analysis_results:
            print("\n" + "=" * 50)
            print("СВОДКА АНАЛИЗА:")
            print("=" * 50)
            
            for result in analysis_results:
                print(f"\nФайл: {Path(result['input']).name}")
                print(f"  • Результат: {Path(result['output']).name}")
        
        print("\n" + "=" * 60)
        print("ВСЕ ОПЕРАЦИИ УСПЕШНО ЗАВЕРШЕНЫ!")
        print("=" * 60)
        
    except FileNotFoundError as e:
        print(f"Ошибка: {e}")
    except Exception as e:
        print(f"Произошла ошибка: {e}")

def process_single_file(excel_file_path):
    """
    Обработка одного Excel файла: парсинг + анализ
    """
    try:
        # Парсинг одного файла
        print(f"Обработка файла: {Path(excel_file_path).name}")
        json_result = xls_to_json_single(
            input_file=excel_file_path,
            output_folder="output_json_single"
        )
        
        if json_result:
            # Анализ полученного JSON файла
            analysis_result = perform_abc_xyz_analysis(
                json_file_path=json_result['output'],
                output_file_name=f"{Path(excel_file_path).stem}_analysis.json"
            )
            
            if analysis_result:
                print(f"✓ Анализ завершен. Результат: {analysis_result}")
                return analysis_result
    
    except Exception as e:
        print(f"Ошибка при обработке файла: {e}")
    
    return None

if __name__ == "__main__":
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        # Если передан аргумент - путь к файлу
        file_path = sys.argv[1]
        process_single_file(file_path)
    else:
        # Или запускаем основную программу
        main()