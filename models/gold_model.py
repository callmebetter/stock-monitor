from database import Base
from sqlalchemy import Column, Integer, String, DECIMAL, BigInteger, TIMESTAMP, Date, UniqueConstraint, func


class GoldPriceSnapshot(Base):
    """金价快照：国内现货 + 国际指标，append-only，供后续沪伦溢价历史曲线使用。"""

    __tablename__ = 'gold_price_snapshot'

    id = Column(Integer, autoincrement=True, primary_key=True, comment='序号')
    symbol = Column(String(20), nullable=False, comment='标识，如 Au9999/XAU/DXY')
    name = Column(String(50), comment='名称')
    price = Column(DECIMAL(15, 4), comment='价格/点位/汇率')
    change_pct = Column(DECIMAL(10, 4), comment='涨跌幅%')
    unit = Column(String(20), comment='单位：元/克、美元/盎司、点、汇率')
    source = Column(String(50), comment='数据源：akshare/sina/yahoo/tiantian-fund')
    ts = Column(TIMESTAMP(timezone=True), nullable=False, comment='采集时间UTC')

    __table_args__ = (UniqueConstraint('symbol', 'ts', name='idx_gold_price_symbol_ts'),)

    def __repr__(self):
        return f"<GoldPriceSnapshot(symbol='{self.symbol}', ts='{self.ts}')>"


class GoldEtfSnapshot(Base):
    """黄金ETF/场外基金快照：每日一条（同 code 同日去重）。"""

    __tablename__ = 'gold_etf_snapshot'

    id = Column(Integer, autoincrement=True, primary_key=True, comment='序号')
    code = Column(String(10), nullable=False, comment='基金代码')
    trade_date = Column(Date, nullable=False, comment='交易日期')
    price = Column(DECIMAL(10, 4), comment='场内价/场外估值')
    change_pct = Column(DECIMAL(10, 4), comment='涨跌幅%')
    volume = Column(BigInteger, comment='成交量')
    nav = Column(DECIMAL(10, 4), comment='确认净值')
    est_nav = Column(DECIMAL(10, 4), comment='盘中估值')
    source = Column(String(50), comment='数据源')
    ts = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp(), comment='更新时间')

    __table_args__ = (UniqueConstraint('code', 'trade_date', name='idx_gold_etf_code_date'),)

    def __repr__(self):
        return f"<GoldEtfSnapshot(code='{self.code}', trade_date='{self.trade_date}')>"


class GoldKlineDaily(Base):
    """黄金日K线：第三方源（汇率表）Au(T+D) 日线，upsert 更新（复合主键去重）。

    交易日归属沿用上游 day 字段：夜市（20:00~02:30）归属下一交易日，
    进行中的 K 线随夜市推进被反复 upsert 直至收盘定型。
    """

    __tablename__ = 'gold_kline_daily'

    symbol = Column(String(10), nullable=False, primary_key=True, comment='标的，如 AUTD')
    trade_date = Column(Date, nullable=False, primary_key=True, comment='交易日期')
    open = Column(DECIMAL(12, 3), comment='开盘价')
    high = Column(DECIMAL(12, 3), comment='最高价')
    low = Column(DECIMAL(12, 3), comment='最低价')
    close = Column(DECIMAL(12, 3), comment='收盘价')
    change = Column(DECIMAL(12, 3), comment='涨跌额（相对上一交易日收盘）')
    amplitude = Column(DECIMAL(10, 3), comment='振幅%')
    volume = Column(BigInteger, comment='成交量（手）')
    source = Column(String(50), comment='数据源：huilvbiao')
    ts = Column(TIMESTAMP(timezone=True), server_default=func.current_timestamp(), comment='更新时间UTC')

    def __repr__(self):
        return f"<GoldKlineDaily(symbol='{self.symbol}', trade_date='{self.trade_date}')>"
