from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import sys
# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import config after updating sys.path
import config

# Database connection string
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{config.DB_CONFIG['user']}:{config.DB_CONFIG['password']}@{config.DB_CONFIG['host']}:{config.DB_CONFIG['port']}/{config.DB_CONFIG['database']}"

# Create database engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declare base class
Base = declarative_base()


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
    """Initialize the database, creating all tables"""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()