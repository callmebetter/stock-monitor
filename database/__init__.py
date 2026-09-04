from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import logging

import config

logger = logging.getLogger(__name__)

# Database connection string
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{config.DB_CONFIG['user']}:{config.DB_CONFIG['password']}@{config.DB_CONFIG['host']}:{config.DB_CONFIG['port']}/{config.DB_CONFIG['database']}"

# Create database engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base"""
    pass


def get_db():
    """
    获取数据库会话
    :return: 数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize the database, creating all tables.

    DB 不可用时降级运行（黄金前端页面不依赖数据库，快照任务会自行报错）。
    """
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.error(f"Database init failed, running without DB: {e}")

if __name__ == "__main__":
    init_db()