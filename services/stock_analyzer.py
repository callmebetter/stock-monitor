import pandas as pd
import numpy as np
from models.stock_model import StockData
from database import SessionLocal

def calculate_moving_averages(df):
    """
    计算常用移动平均线
    :param df: 包含股票数据的 DataFrame
    :return: 添加了移动平均线的 DataFrame
    """
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma10'] = df['close'].rolling(window=10).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma30'] = df['close'].rolling(window=30).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()
    df['ma120'] = df['close'].rolling(window=120).mean()
    return df

def calculate_convergence(df):
    """
    计算均线粘合度
    :param df: 包含移动平均线的 DataFrame
    :return: 添加了粘合度指标的 DataFrame
    """
    # 计算最大值和最小值
    df['max_ma'] = df[['ma5', 'ma10', 'ma20', 'ma30', 'ma60']].max(axis=1)
    df['min_ma'] = df[['ma5', 'ma10', 'ma20', 'ma30', 'ma60']].min(axis=1)
    
    # 计算粘合度
    df['zhanhe'] = (df['max_ma'] / df['min_ma'] - 1) * 100
    
    return df

def screen_stocks(df):
    """
    根据TDX公式筛选符合条件的股票
    :param df: 包含股票数据的 DataFrame
    :return: 符合条件的股票 DataFrame
    """
    # 计算移动平均线
    df = calculate_moving_averages(df)
    
    # 计算粘合度
    df = calculate_convergence(df)
    
    # 均线粘合条件：近15天中至少有10天粘合度 < 3%，并且当前也满足该条件
    df['zhanhe_less_3'] = (df['zhanhe'] < 3).rolling(15).sum() >= 10
    
    # 放量大涨条件：涨幅 > 5% 且 成交量 > 昨日成交量 × 1.5 倍
    df['rise_5'] = (df['close'] - df['yesterday_close']) / df['yesterday_close'] > 0.05
    df['vol_up'] = df['volume'] > df['volume'].shift(1) * 1.5
    
    # 阳线上穿多根均线条件
    up2 = (df['close'] > df['ma5']) & (df['close'] > df['ma10']) & ((df['open'] < df['ma5']) | (df['open'] < df['ma10']))
    up3 = (df['close'] > df['ma5']) & (df['close'] > df['ma10']) & (df['close'] > df['ma20']) & ((df['open'] < df['ma5']) | (df['open'] < df['ma10']) | (df['open'] < df['ma20']))
    up4 = (df['close'] > df['ma5']) & (df['close'] > df['ma10']) & (df['close'] > df['ma20']) & (df['close'] > df['ma30']) & ((df['open'] < df['ma5']) | (df['open'] < df['ma10']) | (df['open'] < df['ma20']) | (df['open'] < df['ma30']))
    df['break_ma'] = up2 | up3 | up4
    
    # 换手率倍增条件：当前换手率是前一日的 2~5 倍
    df['turnover_ratio_condition'] = (df['turnover_ratio'] >= 2) & (df['turnover_ratio'] <= 5)
    
    # 长期均线金叉条件：MA60 上穿 MA120
    df['golden_cross'] = (df['ma60'] > df['ma120']) & (df['ma60'].shift(1) <= df['ma120'].shift(1))
    
    # 综合选股条件
    selected_stocks = df[
        df['zhanhe_less_3'] &
        df['rise_5'] &
        df['vol_up'] &
        df['break_ma'] &
        df['turnover_ratio_condition'] &
        df['golden_cross']
    ]
    
    return selected_stocks

def get_screened_stocks():
    """
    获取并筛选符合条件的股票
    :return: 符合条件的股票 DataFrame
    """
    db = SessionLocal()
    try:
        # 查询最新股票数据
        df = pd.read_sql(db.query(StockData).statement, db.bind)
        
        # 筛选符合条件的股票
        selected_stocks = screen_stocks(df)
        
        return selected_stocks
    except Exception as e:
        print(f"Error getting screened stocks: {e}")
        return pd.DataFrame()
    finally:
        db.close()