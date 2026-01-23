import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from db.database import db
from db.models import Base

def init_database():
    """Создает таблицы в БД"""
    try:
        print("🔄 Создание таблиц в БД...")
        
        # Подключаемся
        db.connect()
        
        # Создаем все таблицы
        Base.metadata.create_all(bind=db.engine)
        
        print("✅ Таблицы успешно созданы:")
        print("   - store (товары на складе)")
        print("   - analysis (ABC/XYZ анализ)")
        
        # Простая проверка
        print("🎉 База данных готова к работе!")
        
    except Exception as e:
        print(f"❌ Ошибка при создании БД: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    init_database()