# This file makes Python treat the directory as a package
import os
import sys
# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import engine, Base
try:
    from models.stock_model import StockData
except ImportError:
    from stock_monitor.models.stock_model import StockData


def init_db():
    """Initialize the database, creating all tables"""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()