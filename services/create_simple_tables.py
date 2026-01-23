import sqlite3

# Удаляем старый файл если есть
import os
if os.path.exists('pepe_database.db'):
    os.remove('pepe_database.db')

# Создаем новую БД
conn = sqlite3.connect('pepe_database.db')
cursor = conn.cursor()

# Создаем простую таблицу store
cursor.execute("""
CREATE TABLE store (
    id INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    revenue REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Создаем простую таблицу analysis
cursor.execute("""
CREATE TABLE analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id INTEGER REFERENCES store(id),
    product_name TEXT NOT NULL,
    abc_category TEXT NOT NULL,
    xyz_category TEXT NOT NULL,
    abc_xyz_category TEXT NOT NULL,
    revenue REAL NOT NULL,
    analysis_date DATE DEFAULT CURRENT_DATE
)
""")

conn.commit()
conn.close()

print("✅ Таблицы созданы:")
print("   - store (id, product_name, revenue)")
print("   - analysis (abc_category, xyz_category, abc_xyz_category)")
print("🎉 Готово! Теперь запусти app.py и загрузи данные")