import os
import sys

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import Column, String, Float, Integer, Date
from database import Base

class StockData(Base):
    __tablename__ = 'stock_data'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)  # 股票代码
    name = Column(String(100))  # 股票名称
    date = Column(Date, nullable=False)  # 交易日期
    open = Column(Float)  # 开盘价
    high = Column(Float)  # 最高价
    low = Column(Float)  # 最低价
    close = Column(Float)  # 收盘价
    volume = Column(Integer)  # 成交量（手）
    turnover_value = Column(Float)  # 成交金额（元）
    amplitude = Column(Float)  # 当日振幅百分比
    high_limit = Column(Float)  # 涨停价
    low_limit = Column(Float)  # 跌停价
    open_price = Column(Float)  # 开盘价
    yesterday_close = Column(Float)  # 昨日收盘价
    volume_ratio = Column(Float)  # 量比
    turnover_ratio = Column(Float)  # 换手率百分比
    pe_ttm = Column(Float)  # 市盈率（TTM）
    pb = Column(Float)  # 市净率
    market_value = Column(Float)  # 总市值（元）
    circulation_market_value = Column(Float)  # 流通市值（元）
    rise_speed = Column(Float)  # 涨速百分比
    change_from_beginning = Column(Float)  # 年初至今涨跌幅百分比
    ma5 = Column(Float)  # 5日均线
    ma10 = Column(Float)  # 10日均线
    ma20 = Column(Float)  # 20日均线
    ma30 = Column(Float)  # 30日均线
    ma60 = Column(Float)  # 60日均线
    ma120 = Column(Float)  # 120日均线
    zhanhe = Column(Float)  # 均线粘合度
    created_at = Column(Date)