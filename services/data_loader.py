# services/data_loader.py
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

# Добавляем пути для корректного импорта
current_dir = Path(__file__).parent
project_root = current_dir.parent

sys.path.insert(0, str(project_root))

try:
    from db.database import db
    from db.models import Store, Analysis
    DB_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Не удалось импортировать модули БД: {e}")
    DB_AVAILABLE = False
    db = None
    Store = None
    Analysis = None

class JSONToDBLoader:
    def __init__(self):
        if not DB_AVAILABLE:
            print("⚠️  ВНИМАНИЕ: Модули БД недоступны, работа в режиме эмуляции")
            self.session = None
        else:
            try:
                self.session = db.get_session()
                print("✅ Сессия БД создана")
            except Exception as e:
                print(f"❌ Ошибка создания сессии: {e}")
                self.session = None
    
    def load_from_json(self, json_file_path: str) -> Dict:
        """
        Загружает данные из JSON файла в БД
        Возвращает результат загрузки
        """
        results = {
            "store_inserted": 0,
            "analysis_inserted": 0,
            "errors": [],
            "file": os.path.basename(json_file_path)
        }
        
        if not DB_AVAILABLE or not self.session:
            results["errors"].append("Модули БД недоступны")
            return results
        
        try:
            # Нормализуем путь к файлу
            json_file_path = self._find_json_file(json_file_path)
            
            if not json_file_path or not os.path.exists(json_file_path):
                error_msg = f"Файл не найден: {json_file_path}"
                results["errors"].append(error_msg)
                print(f"❌ {error_msg}")
                return results
            
            print(f"📥 Загрузка данных из {json_file_path}")
            
            # Читаем данные из файла
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"📊 Найдено {len(data) if isinstance(data, list) else 1} записей")
            
            # Обрабатываем данные
            if isinstance(data, list):
                for item in data:
                    self._process_item(item, results)
            else:
                self._process_item(data, results)
            
            # Сохраняем изменения
            if self.session:
                self.session.commit()
                print(f"✅ Успешно загружено: {results['store_inserted']} товаров, {results['analysis_inserted']} анализов")
            
        except json.JSONDecodeError as e:
            error_msg = f"Ошибка чтения JSON: {e}"
            results["errors"].append(error_msg)
            print(f"❌ {error_msg}")
            if self.session:
                self.session.rollback()
        except Exception as e:
            error_msg = f"Ошибка при загрузке: {e}"
            results["errors"].append(error_msg)
            print(f"❌ {error_msg}")
            if self.session:
                self.session.rollback()
            import traceback
            traceback.print_exc()
        
        finally:
            if self.session:
                self.session.close()
                # Создаем новую сессию для следующих операций
                self.session = db.get_session()
        
        return results
    
    def _find_json_file(self, json_file_path: str) -> str:
        """
        Ищет JSON файл по различным путям
        """
        if not json_file_path:
            return ""
        
        # Преобразуем в абсолютный путь
        json_file_path = os.path.abspath(json_file_path)
        
        # Если файл существует по указанному пути
        if os.path.exists(json_file_path):
            return json_file_path
        
        # Получаем имя файла
        file_name = os.path.basename(json_file_path)
        
        # Все возможные пути для поиска
        search_paths = [
            file_name,
            f"analysis_results/{file_name}",
            f"output_json/{file_name}",
            f"uploads/{file_name}",
            str(project_root / "analysis_results" / file_name),
            str(project_root / "output_json" / file_name),
            str(project_root / file_name),
        ]
        
        # Проверяем все пути
        for path in search_paths:
            try:
                path_obj = Path(path)
                if path_obj.exists() and path_obj.is_file():
                    abs_path = str(path_obj.absolute())
                    print(f"🔍 Найден файл по пути: {abs_path}")
                    return abs_path
            except Exception:
                continue
        
        return ""
    
    def _process_item(self, item: Dict, results: Dict):
        """
        Обрабатывает один элемент JSON и сохраняет в БД
        """
        if not self.session or not DB_AVAILABLE:
            results["errors"].append("Сессия БД недоступна")
            return
        
        try:
            # 1. Извлекаем название товара
            product_name = item.get("name") or item.get("Наименование товара", "").strip()
            if not product_name:
                product_name = f"Товар_{results['store_inserted'] + 1}"
            
            # 2. Извлекаем выручку
            revenue = 0.0
            revenue_keys = ["revenue", "Выручка (У.Е.)", "выручка", "Revenue", "Выручка"]
            for key in revenue_keys:
                if key in item and item[key] is not None:
                    try:
                        revenue = float(item[key])
                        break
                    except (ValueError, TypeError):
                        continue
            
            # 3. Создаем запись в таблице store
            store_item = Store(
                product_name=product_name,
                revenue=revenue
            )
            self.session.add(store_item)
            self.session.flush()  # Получаем сгенерированный ID
            
            results["store_inserted"] += 1
            
            # 4. Извлекаем категории для анализа
            abc_category = item.get("ABC", "C")
            xyz_category = item.get("XYZ", "Z")
            abc_xyz_category = item.get("ABC_XYZ", "")
            
            # Валидация категорий
            if abc_category not in ["A", "B", "C"]:
                abc_category = "C"
            
            if xyz_category not in ["X", "Y", "Z"]:
                xyz_category = "Z"
            
            if not abc_xyz_category or len(abc_xyz_category) != 2:
                abc_xyz_category = abc_category + xyz_category
            
            # 5. Создаем запись в таблице analysis
            analysis_item = Analysis(
                store_id=store_item.id,
                product_name=product_name,
                abc_category=abc_category,
                xyz_category=xyz_category,
                abc_xyz_category=abc_xyz_category,
                revenue=revenue
            )
            self.session.add(analysis_item)
            results["analysis_inserted"] += 1
            
            print(f"  ✓ {product_name[:30]:30} | ID:{store_item.id:3} | Кат:{abc_xyz_category} | Выр:{revenue:10.2f}")
                
        except Exception as e:
            error_msg = f"Ошибка обработки товара: {str(e)[:100]}"
            results["errors"].append(error_msg)
            print(f"  ❌ {error_msg}")