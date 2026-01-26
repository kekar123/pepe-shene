# check_db_load.py
import sys
import os
import json  # Добавить эту строку!
from pathlib import Path

# Добавляем пути
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))
sys.path.append(str(current_dir.parent))

from db.database import db
from db.models import Base
from services.data_loader import JSONToDBLoader

def test_db_connection():
    """Тест подключения к БД"""
    print("🔍 Проверка подключения к БД...")
    try:
        engine = db.connect()
        
        # Создаем таблицы
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы созданы/проверены")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_json_load():
    """Тест загрузки данных из JSON"""
    print("\n📥 Тест загрузки данных из JSON...")
    
    # Путь к тестовому JSON файлу
    json_path = current_dir.parent / "data_analysis.json"
    
    if not json_path.exists():
        print(f"❌ Файл {json_path} не найден")
        # Создаем тестовый файл
        test_data = [
            {
                "id": 1,
                "name": "Тестовый товар 1",
                "revenue": 5000.0,
                "ABC": "A",
                "XYZ": "X",
                "ABC_XYZ": "AX"
            },
            {
                "id": 2,
                "name": "Тестовый товар 2",
                "revenue": 3000.0,
                "ABC": "B",
                "XYZ": "Y",
                "ABC_XYZ": "BY"
            }
        ]
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Создан тестовый файл: {json_path}")
    
    # Загружаем данные
    loader = JSONToDBLoader()
    result = loader.load_from_json(str(json_path))
    
    print(f"\n📊 Результат загрузки:")
    print(f"  Товаров добавлено: {result['store_inserted']}")
    print(f"  Анализов добавлено: {result['analysis_inserted']}")
    
    if result['errors']:
        print(f"  Ошибок: {len(result['errors'])}")
        for error in result['errors']:
            print(f"    - {error}")
    else:
        print("  ✅ Ошибок нет")
    
    return result

def check_data_in_db():
    """Проверяем данные в БД"""
    print("\n🔍 Проверка данных в БД...")
    try:
        session = db.get_session()
        from db.models import Store, Analysis
        
        store_count = session.query(Store).count()
        analysis_count = session.query(Analysis).count()
        
        print(f"  Товаров в таблице store: {store_count}")
        print(f"  Записей в таблице analysis: {analysis_count}")
        
        if store_count > 0:
            print("\n  Пример товаров:")
            items = session.query(Store).limit(5).all()
            for item in items:
                print(f"    - {item.product_name} (ID: {item.id}, Выручка: {item.revenue})")
        
        session.close()
        
    except Exception as e:
        print(f"❌ Ошибка при проверке БД: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("ТЕСТ ЗАГРУЗКИ ДАННЫХ В БАЗУ ДАННЫХ")
    print("=" * 50)
    
    # Тест подключения
    if test_db_connection():
        # Тест загрузки JSON
        result = test_json_load()
        
        # Проверяем данные
        check_data_in_db()
        
        if result['store_inserted'] > 0:
            print("\n✅ Тест пройден успешно!")
        else:
            print("\n⚠️ Тест не прошел: данные не загружены")
    else:
        print("\n❌ Не удалось подключиться к БД")