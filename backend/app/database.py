"""
数据库连接和会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 数据库文件路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATABASE_DIR, exist_ok=True)

# 导出BASE_DIR供其他模块使用
__all__ = ['BASE_DIR', 'DATABASE_DIR', 'engine', 'SessionLocal', 'Base', 'get_db', 'init_db']

DATABASE_URL = f"sqlite:///{os.path.join(DATABASE_DIR, 'tcm.db')}"

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite需要这个参数
    echo=False  # 设置为True可以看到SQL语句
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型类
Base = declarative_base()


def get_db():
    """
    获取数据库会话
    用于依赖注入
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化数据库，创建所有表
    """
    from . import models  # 确保模型已注册到 Base.metadata
    Base.metadata.create_all(bind=engine)
