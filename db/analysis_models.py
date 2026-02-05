# db/analysis_models.py

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class AnalysisSession(Base):
    """Модель для сессии анализа"""
    __tablename__ = 'analysis_sessions'
    
    id = Column(Integer, primary_key=True)
    excel_filename = Column(String(255), nullable=False)
    json_filename = Column(String(255))
    analysis_filename = Column(String(255))
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    total_products = Column(Integer, default=0)
    total_revenue = Column(Numeric(15, 2), default=0)
    status = Column(String(50), default='completed')
    session_data = Column(Text)  # JSON данные
    
    # Связи
    products = relationship("Product", back_populates="analysis_session", cascade="all, delete-orphan")
    category_stats = relationship("CategoryStat", back_populates="analysis_session", cascade="all, delete-orphan")
    matrix_cells = relationship("MatrixCell", back_populates="analysis_session", cascade="all, delete-orphan")
    charts = relationship("Chart", back_populates="analysis_session", cascade="all, delete-orphan")

class Product(Base):
    """Модель для продукта/товара"""
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    analysis_session_id = Column(Integer, ForeignKey('analysis_sessions.id'), nullable=False)
    product_name = Column(String(500), nullable=False)
    product_code = Column(String(200))
    quantity = Column(Numeric(15, 3), default=0)
    revenue = Column(Numeric(15, 2), default=0)
    abc_category = Column(String(1))
    xyz_category = Column(String(1))
    abc_xyz_category = Column(String(3))
    revenue_share = Column(Numeric(5, 2))
    cumulative_share = Column(Numeric(5, 2))
    rank = Column(Integer)
    category = Column(String(100))
    
    # Связь
    analysis_session = relationship("AnalysisSession", back_populates="products")

class CategoryStat(Base):
    """Модель для статистики по категориям"""
    __tablename__ = 'category_stats'
    
    id = Column(Integer, primary_key=True)
    analysis_session_id = Column(Integer, ForeignKey('analysis_sessions.id'), nullable=False)
    category_type = Column(String(10), nullable=False)  # 'abc' или 'xyz'
    category_name = Column(String(1), nullable=False)   # 'A', 'B', 'C' или 'X', 'Y', 'Z'
    products_count = Column(Integer, default=0)
    total_revenue = Column(Numeric(15, 2), default=0)
    revenue_percentage = Column(Numeric(5, 2), default=0)
    
    # Связь
    analysis_session = relationship("AnalysisSession", back_populates="category_stats")
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class MatrixCell(Base):
    """Модель для ячейки матрицы ABC-XYZ"""
    __tablename__ = 'matrix_cells'
    
    id = Column(Integer, primary_key=True)
    analysis_session_id = Column(Integer, ForeignKey('analysis_sessions.id'), nullable=False)
    abc_category = Column(String(1), nullable=False)
    xyz_category = Column(String(1), nullable=False)
    products_count = Column(Integer, default=0)
    total_revenue = Column(Numeric(15, 2), default=0)
    avg_revenue = Column(Numeric(15, 2), default=0)
    min_revenue = Column(Numeric(15, 2), default=0)
    max_revenue = Column(Numeric(15, 2), default=0)
    recommendation = Column(Text)
    
    # Связь
    analysis_session = relationship("AnalysisSession", back_populates="matrix_cells")
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class Chart(Base):
    """Модель для хранения графиков"""
    __tablename__ = 'charts'
    
    id = Column(Integer, primary_key=True)
    analysis_session_id = Column(Integer, ForeignKey('analysis_sessions.id'), nullable=False)
    chart_type = Column(String(50), nullable=False)  # 'abc_pie', 'xyz_bar', 'matrix', 'top_products'
    chart_data = Column(Text, nullable=False)  # base64 изображение
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связь
    analysis_session = relationship("AnalysisSession", back_populates="charts")
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )