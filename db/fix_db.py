import sys
import os

# Добавляем корневую директорию в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect

# Создаем движок с echo=True чтобы видеть SQL запросы
engine = create_engine('sqlite:///pepe_database.db', echo=True)

# Создаем таблицы вручную
print("Создаем таблицы вручную...")

# SQL для таблицы store
store_sql = """
CREATE TABLE IF NOT EXISTS store (
    id INTEGER PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    product_weight NUMERIC(10, 3) NOT NULL,
    city_from VARCHAR(100) NOT NULL,
    city_to VARCHAR(100) NOT NULL,
    arrival_date DATE NOT NULL,
    departure_date DATE,
    current_location VARCHAR(100),
    storage_cell VARCHAR(20),
    status VARCHAR(50) DEFAULT 'на складе',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
)
"""

# SQL для таблицы analysis
analysis_sql = """
CREATE TABLE IF NOT EXISTS analysis (
    id INTEGER PRIMARY KEY,
    store_id INTEGER REFERENCES store(id),
    product_name VARCHAR(200) NOT NULL,
    abc_category VARCHAR(1) NOT NULL,
    xyz_category VARCHAR(1) NOT NULL,
    abc_xyz_category VARCHAR(2),
    recommended_cell VARCHAR(20) NOT NULL,
    revenue NUMERIC(15, 2),
    turnover_rate NUMERIC(5, 2),
    analysis_date DATE DEFAULT CURRENT_DATE,
    is_active BOOLEAN DEFAULT 1
)
"""

with engine.connect() as conn:
    conn.execute(store_sql)
    conn.execute(analysis_sql)
    conn.commit()

print("✅ Таблицы созданы вручную!")

# Проверяем
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"📊 Таблицы в базе: {tables}")