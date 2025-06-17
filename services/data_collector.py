import akshare as ak
import pandas as pd
from models.stock_model import StockData
from database import SessionLocal
from sqlalchemy.exc import IntegrityError
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_stock_data():
    """
    使用 AkShare 获取 A 股市场实时数据
    :return: 包含股票数据的 DataFrame
    """
    try:
        # 获取实时行情数据
        df = ak.stock_zh_a_spot_em()
        
        # 重命名列以匹配数据库模型
        df.rename(columns={
            '代码': 'symbol',
            '名称': 'name',
            '最新价': 'close',
            '最高价': 'high',
            '最低价': 'low',
            '开盘价': 'open',
            '昨收': 'yesterday_close',
            '成交量': 'volume',
            '成交额': 'turnover_value',
            '振幅': 'amplitude',
            '涨跌幅': 'change_percent',
            '涨跌额': 'change_amount',
            '换手率': 'turnover_ratio',
            '市盈率-动态': 'pe_ttm',
            '市净率': 'pb',
            '总市值': 'market_value',
            '流通市值': 'circulation_market_value'
        }, inplace=True)
        
        # 添加日期字段
        df['date'] = pd.to_datetime('today').date()
        
        return df
    except Exception as e:
        logger.error(f"Error fetching stock data: {e}", exc_info=True)
        return pd.DataFrame()

def save_stock_data(df):
    """
    将股票数据保存到数据库，跳过重复记录
    :param df: 包含股票数据的 DataFrame
    """
    if df.empty:
        logger.warning("No data to save.")
        return

    db = SessionLocal()
    try:
        # 获取已存在的记录避免重复插入
        existing_records = db.query(StockData.symbol, StockData.date).all()
        existing_set = set(existing_records)
        
        # 将 DataFrame 转换为字典列表
        data = df.to_dict(orient='records')
        
        # 过滤掉重复数据
        new_data = [
            record for record in data 
            if (record['symbol'], record['date']) not in existing_set
        ]
        
        if not new_data:
            logger.info("No new data to insert.")
            return
        
        # 批量插入新数据
        db.bulk_insert_mappings(StockData, new_data)
        db.commit()
        logger.info(f"Inserted {len(new_data)} new records.")
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error during data insertion: {e}", exc_info=True)
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during data insertion: {e}", exc_info=True)
    finally:
        db.close()