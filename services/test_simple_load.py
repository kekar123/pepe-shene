import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.data_loader import JSONToDBLoader

# Загружаем тестовые данные
loader = JSONToDBLoader()
result = loader.load_from_json("data_analysis.json")

print("📊 Результат загрузки:")
print(f"Товаров добавлено: {result['store_inserted']}")
print(f"Анализов добавлено: {result['analysis_inserted']}")
print(f"Ошибок: {len(result['errors'])}")

if result['errors']:
    print("Ошибки:")
    for error in result['errors']:
        print(f"  - {error}")