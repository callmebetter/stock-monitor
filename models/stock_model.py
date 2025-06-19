import os
import sys

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from database import Base
from sqlalchemy import Column, Integer, String, DECIMAL, BigInteger, TIMESTAMP, Date, UniqueConstraint, func


class StockData(Base):
    __tablename__ = 'stock_data'

    symbol = Column(String(10), primary_key=True, comment='代码')
    trade_date = Column(Date, primary_key=True, comment='交易日期')
    id = Column(Integer, autoincrement=True, comment='序号') # Make it a regular column
    name = Column(String(50), nullable=False, comment='名称')
    close = Column(DECIMAL(10, 2), comment='最新价')
    change_percent = Column(DECIMAL(6, 3), comment='涨跌幅')
    change_amount = Column(DECIMAL(10, 2), comment='涨跌额')
    volume = Column(BigInteger, comment='成交量')
    turnover_value = Column(DECIMAL(15, 2), comment='成交额')
    amplitude = Column(DECIMAL(6, 3), comment='振幅')
    high = Column(DECIMAL(10, 2), comment='最高')
    low = Column(DECIMAL(10, 2), comment='最低')
    open = Column(DECIMAL(10, 2), comment='今开')
    yesterday_close = Column(DECIMAL(10, 2), comment='昨收')
    turnover_ratio = Column(DECIMAL(6, 3), comment='换手率')
    pe_ttm = Column(DECIMAL(10, 2), comment='市盈率-动态')
    pb = Column(DECIMAL(10, 2), comment='市净率')
    market_value = Column(DECIMAL(15, 2), comment='总市值')
    circulation_market_value = Column(DECIMAL(15, 2), comment='流通市值')
    rise_speed = Column(DECIMAL(6, 3), comment='涨速')
    five_minute_change = Column(DECIMAL(6, 3), comment='5分钟涨跌')
    sixty_day_change_percent = Column(DECIMAL(8, 2), comment='60日涨跌幅')
    year_to_date_change_percent = Column(DECIMAL(10, 2), comment='年初至今涨跌幅')
    update_time = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间')

    __table_args__ = (UniqueConstraint('symbol', 'trade_date', name='idx_symbol_trade_date'),)

    def __repr__(self):
        return f"<StockData(symbol='{self.symbol}', trade_date='{self.trade_date}')>"
    # ma5 = Column(Float)  # 5日均线
    # ma10 = Column(Float)  # 10日均线
    # ma20 = Column(Float)  # 20日均线
    # ma30 = Column(Float)  # 30日均线
    # ma60 = Column(Float)  # 60日均线
    # ma120 = Column(Float)  # 120日均线
    # zhanhe = Column(Float)  # 均线粘合度

# 新增: TradingCalendar 模型定义
class TradingCalendar(Base):
    __tablename__ = 'trading_calendar'
    
    id = Column(Integer, autoincrement=True, comment='序号')  # 新增：自增主键
    trade_date = Column(Date, primary_key=True, nullable=False, comment='交易日期')

    def __repr__(self):
        return f"<TradingCalendar(trade_date='{self.trade_date}')>"
