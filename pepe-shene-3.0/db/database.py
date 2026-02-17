import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.db_url = os.getenv('DATABASE_URL', 'sqlite:///pepe_database.db')
        self.engine = None
        self.SessionLocal = None
        
    def connect(self):
        """Создает подключение к БД"""
        try:
            self.engine = create_engine(
                self.db_url,
                echo=True  # ВКЛЮЧИ ЭТО ДЛЯ ОТЛАДКИ!
            )
            
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            print("✅ Подключение к БД установлено")
            return self.engine
            
        except Exception as e:
            print(f"❌ Ошибка подключения к БД: {e}")
            raise
    
    def get_session(self):
        """Возвращает сессию для работы с БД"""
        if not self.SessionLocal:
            self.connect()
        return self.SessionLocal()

db = Database()