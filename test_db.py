import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("🔍 Проверка импорта модулей...")
try:
    from db.database import db
    from db.models import Base
    print("✅ Модули импортированы")
    
    # Подключаемся к БД
    db.connect()
    print("✅ Подключение к БД установлено")
    
    # Пытаемся создать таблицы
    print("🔄 Создание таблиц...")
    Base.metadata.create_all(bind=db.engine)
    print("✅ Таблицы созданы (если не было ошибки)")
    
    # Проверяем таблицы
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    if tables:
        print(f"✅ Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"   - {table}")
    else:
        print("❌ Таблицы не найдены! Проверьте ошибки выше")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()