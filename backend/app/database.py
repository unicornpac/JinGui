"""
数据库连接和会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 数据库文件路径
# DATA_DIR 环境变量用于云平台持久磁盘挂载（如 Render），未设置时使用本地 data/ 目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)

# 导出供其他模块使用
__all__ = ['BASE_DIR', 'DATA_DIR', 'engine', 'SessionLocal', 'Base', 'get_db', 'init_db']

DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'tcm.db')}"

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
    初始化数据库，创建所有表，并执行轻量迁移（添加新列）
    """
    from . import models  # 确保模型已注册到 Base.metadata
    # 创建新表（已存在的跳过）
    Base.metadata.create_all(bind=engine)
    # 对已有表添加可能缺失的新列（SQLite 轻量迁移）
    _migrate_columns()


def _migrate_columns():
    """为已有表添加新列（如果不存在）；创建新表（如果不存在）"""
    import sqlite3
    db_path = os.path.join(DATA_DIR, "tcm.db")
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    try:
        # ── classic_texts 新列 ──
        cur = conn.execute("PRAGMA table_info(classic_texts)")
        existing = {row[1] for row in cur.fetchall()}
        new_columns = {
            "section": "VARCHAR(100)",
            "article_number": "INTEGER",
            "order_index": "INTEGER",
            "verified": "BOOLEAN DEFAULT 0",
            "verified_at": "DATETIME",
            "source_url": "VARCHAR(500)",
            "raw_content": "TEXT",
            "layout_marker": "VARCHAR(10)",
            "source_file": "VARCHAR(500)",
            "source_hash": "VARCHAR(64)",
            "source_offset": "INTEGER",
            "source_edition": "VARCHAR(200)",
            "import_batch_id": "VARCHAR(36)",
        }
        for col_name, col_type in new_columns.items():
            if col_name not in existing:
                conn.execute(f"ALTER TABLE classic_texts ADD COLUMN {col_name} {col_type}")
                print(f"[migrate] 已添加列 classic_texts.{col_name}")

        # ── documents 新列 ──
        cur = conn.execute("PRAGMA table_info(documents)")
        document_columns = {row[1] for row in cur.fetchall()}
        if "error_message" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN error_message TEXT")
            print("[migrate] 已添加列 documents.error_message")
        conn.commit()
    finally:
        conn.close()

    # ── 新表由 SQLAlchemy create_all 自动创建 ──
    from . import models  # noqa: F401
