# services/data_loader.py
import json
import os
from datetime import datetime
from typing import Dict, List
from sqlalchemy.exc import IntegrityError

# Используем относительные импорты
try:
    from ..db.database import db
    from ..db.models import Store, Analysis
except ImportError:
    # Для прямого запуска из папки services
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from db.database import db
    from db.models import Store, Analysis

class JSONToDBLoader:
    def __init__(self):
        self.session = db.get_session()
    
    def load_from_json(self, json_file_path: str) -> Dict:
        """
        Загружает данные из JSON файла в БД
        """
        results = {
            "store_inserted": 0,
            "analysis_inserted": 0,
            "errors": [],
            "file": os.path.basename(json_file_path)
        }
        
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"📥 Загрузка данных из {json_file_path}")
            
            # СОЗДАЕМ ТАБЛИЦЫ ПЕРЕД ЗАГРУЗКОЙ
            from db.models import Base
            Base.metadata.create_all(bind=self.session.bind)
            print("✅ Таблицы проверены/созданы")
            
            if isinstance(data, list):
                for item in data:
                    self._process_item(item, results)
            else:
                self._process_item(data, results)
            
            self.session.commit()
            print(f"✅ Успешно загружено: {results['store_inserted']} товаров, {results['analysis_inserted']} анализов")
            
        except Exception as e:
            self.session.rollback()
            results["errors"].append(str(e))
            print(f"❌ Ошибка при загрузке: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self.session.close()
        
        return results
    
    def _process_item(self, item: Dict, results: Dict):
        """Обрабатывает один элемент JSON"""
        try:
            # 1. Сохраняем в таблицу store
            store_data = {
                "id": item.get("id"),
                "product_name": item.get("name", ""),
                "revenue": item.get("revenue", 0)
            }
            
            if not store_data["id"]:
                results["errors"].append(f"Пропущен id для {item.get('name')}")
                return
            
            store_item = Store(**store_data)
            self.session.add(store_item)
            self.session.flush()  # Получаем ID
            results["store_inserted"] += 1
            
            # 2. Сохраняем в таблицу analysis
            analysis_data = {
                "store_id": store_item.id,
                "product_name": item.get("name", ""),
                "abc_category": item.get("ABC", "C"),
                "xyz_category": item.get("XYZ", "Z"),
                "abc_xyz_category": item.get("ABC_XYZ", "CZ"),
                "revenue": item.get("revenue", 0)
            }
            
            analysis_item = Analysis(**analysis_data)
            self.session.add(analysis_item)
            results["analysis_inserted"] += 1
                
        except IntegrityError as e:
            # Если запись уже существует - обновляем
            self.session.rollback()
            self._update_existing_item(item, results)
            
        except Exception as e:
            results["errors"].append(f"Ошибка обработки {item.get('name', 'Unknown')}: {str(e)}")
    
    def _update_existing_item(self, item: Dict, results: Dict):
        """Обновляет существующую запись"""
        try:
            product_id = item.get("id")
            if not product_id:
                return
            
            # Обновляем store
            store_item = self.session.query(Store).filter(
                Store.id == product_id
            ).first()
            
            if store_item:
                store_item.product_name = item.get("name", store_item.product_name)
                store_item.revenue = item.get("revenue", store_item.revenue)
                
                # Обновляем analysis
                analysis_item = self.session.query(Analysis).filter(
                    Analysis.store_id == store_item.id
                ).first()
                
                if analysis_item:
                    analysis_item.product_name = item.get("name", analysis_item.product_name)
                    analysis_item.abc_category = item.get("ABC", analysis_item.abc_category)
                    analysis_item.xyz_category = item.get("XYZ", analysis_item.xyz_category)
                    analysis_item.abc_xyz_category = item.get("ABC_XYZ", analysis_item.abc_xyz_category)
                    analysis_item.revenue = item.get("revenue", analysis_item.revenue)
                
                results["store_inserted"] += 1
                results["analysis_inserted"] += 1
            
        except Exception as e:
            results["errors"].append(f"Ошибка обновления {item.get('name')}: {str(e)}")