from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Store(Base):
    __tablename__ = 'store'
    
    id = Column(Integer, primary_key=True)
    product_name = Column(String(200), nullable=False)
    revenue = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связь с анализом
    analysis = relationship("Analysis", back_populates="store", cascade="all, delete-orphan")

class Analysis(Base):
    __tablename__ = 'analysis'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey('store.id', ondelete='CASCADE'))
    product_name = Column(String(200), nullable=False)
    abc_category = Column(String(1), nullable=False)
    xyz_category = Column(String(1), nullable=False)
    abc_xyz_category = Column(String(2), nullable=False)
    revenue = Column(Numeric(15, 2), nullable=False)
    analysis_date = Column(Date, server_default=func.current_date())
    
    # Связь с товаром
    store = relationship("Store", back_populates="analysis")