import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# 新增函数：将中文字段名转换为英文字段名
def translate_chinese_columns(df):
    """
    将中文字段名转换为英文字段名
    :param df: 原始股票数据 DataFrame
    :return: 字段名转换后的 DataFrame
    """
    chinese_to_english = {
        '序号': 'id',
        '代码': 'symbol',
        '名称': 'name',
        '最新价': 'close',
        '涨跌幅': 'change_percent',
        '涨跌额': 'change_amount',
        '成交量': 'volume',
        '成交额': 'turnover_value',
        '振幅': 'amplitude',
        '最高': 'high',
        '最低': 'low',
        '今开': 'open',
        '昨收': 'yesterday_close',
        '换手率': 'turnover_ratio',
        '市盈率-动态': 'pe_ttm',
        '市净率': 'pb',
        '总市值': 'market_value',
        '流通市值': 'circulation_market_value',
        '涨速': 'rise_speed',
        '5分钟涨跌': 'five_minute_change',
        '60日涨跌幅': 'sixty_day_change_percent',
        '年初至今涨跌幅': 'year_to_date_change_percent'
    }
    try:
        logger.debug("开始转换中文字段名为英文字段名")
        df = df.rename(columns=chinese_to_english)
        logger.debug("中文字段名转换完成")
        return df
    except Exception as e:
        logger.error(f"字段名转换失败: {e}")
        raise

def clean_stock_data(df):
    """
    清洗股票数据 DataFrame
    :param df: 原始股票数据 DataFrame
    :return: 清洗后的 DataFrame
    """
    try:
        logger.debug("开始清洗股票数据")
        df = translate_chinese_columns(df)

        df_cleaned = df.copy()

        # 1. 处理缺失值
        numeric_cols = df_cleaned.select_dtypes(include=np.number).columns
        df_cleaned[numeric_cols] = df_cleaned[numeric_cols].fillna(0)

        if 'name' in df_cleaned.columns:
            df_cleaned['name'] = df_cleaned['name'].fillna('未知')

        # 2. 数据类型转换
        cols_to_numeric = [
            'close', 'change_percent', 'change_amount', 'volume', 'turnover_value',
            'amplitude', 'high', 'low', 'open', 'yesterday_close', 'turnover_ratio',
            'pe_ttm', 'pb', 'market_value', 'circulation_market_value',
            'rise_speed', 'five_minute_change', 'sixty_day_change_percent',
            'year_to_date_change_percent'
        ]
        for col in cols_to_numeric:
            if col in df_cleaned.columns:
                df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce').fillna(0)

        # 3. 处理 symbol 列
        df_cleaned['symbol'] = df_cleaned['symbol'].astype(str).str.strip()

        # 4. 清理文本数据
        if 'name' in df_cleaned.columns:
            df_cleaned['name'] = df_cleaned['name'].str.strip()

        # 5. 去重
        df_cleaned = df_cleaned.drop_duplicates()

        # 6. 过滤异常值
        if 'close' in df_cleaned.columns:
            df_cleaned = df_cleaned[df_cleaned['close'] >= 0]

        # 7. 选择需要的列
        columns_to_keep = [
            'symbol', 'name', 'close', 'change_percent', 'change_amount',
            'volume', 'turnover_value', 'amplitude', 'high', 'low', 'open',
            'yesterday_close', 'turnover_ratio', 'pe_ttm', 'pb',
            'market_value', 'circulation_market_value', 'rise_speed',
            'five_minute_change', 'sixty_day_change_percent', 'year_to_date_change_percent'
        ]
        # 补全缺失列（新浪源缺少部分字段）
        for col in columns_to_keep:
            if col not in df_cleaned.columns:
                df_cleaned[col] = 0
        df_cleaned = df_cleaned[columns_to_keep]

        logger.info("股票数据清洗完成")
        return df_cleaned
    except Exception as e:
        logger.error(f"数据清洗失败: {e}")
        raise