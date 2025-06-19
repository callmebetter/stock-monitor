from typing import Optional
import akshare as ak
import pandas as pd
from models.stock_model import StockData, TradingCalendar
from database import SessionLocal
import os
import re
from datetime import datetime, timedelta, date
from helpers.data_cleaner import clean_stock_data
from functools import lru_cache  # 新增：用于缓存交易日历
import logging
from database.database_utils import db_session_scope

logger = logging.getLogger(__name__)


def load_trading_calendar_from_db():
    db = SessionLocal()
    try:
        trading_calendar = db.query(TradingCalendar.trade_date)
        trading_calendar = (
            trading_calendar.order_by(TradingCalendar.trade_date.desc())
            .limit(365)
            .all()
        )
        logger.debug(
            f"Loaded trading calendar from DB: {[date[0] for date in trading_calendar][:-5:]}"
        )
        return [date[0] for date in trading_calendar]
    except Exception as e:
        print(f"Error loading trading calendar from DB: {e}")
        return []
    finally:
        db.close()


def save_trading_calendar_to_db(trading_calendar):
    db = SessionLocal()
    try:
        # 使用ORM批量插入交易日
        for date in trading_calendar:
            db.add(TradingCalendar(trade_date=date))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving trading calendar to DB: {e}")
    finally:
        db.close()
    # with db_session_scope() as db:
    #     # 确保交易日历表中没有重复的日期
    #     db.query(TradingCalendar).filter(
    #         TradingCalendar.trade_date.in_(trading_calendar)
    #     ).delete(synchronize_session=False)
    #     db.bulk_insert_mappings(
    #         TradingCalendar.__mapper__,
    #         [{"trade_date": date} for date in trading_calendar],
    #     )
    #     db.commit()


def sync_trading_calendar():
    """
    同步交易日历到数据库
    """
    db = SessionLocal()
    try:
        # 从 AkShare 获取最新的交易日历
        trade_date_hist = ak.tool_trade_date_hist_sina()
        logger.info("Fetching latest trading calendar from AkShare")
        logger.debug(f"first 5 trading dates: {trade_date_hist['trade_date'].head()}")

        if trade_date_hist.empty:
            logger.warning("No trading dates found in AkShare data.")
            return

        latest_calendar = set(
            ak.tool_trade_date_hist_sina()["trade_date"].values.tolist()
        )

        # 从数据库中加载现有的交易日历
        cached_calendar = load_trading_calendar_from_db()
        cached_set = set(cached_calendar)

        # 计算需要添加和删除的日期
        to_add = latest_calendar - cached_set
        to_remove = cached_set - latest_calendar

        # 添加新日期
        for date in to_add:
            db.add(TradingCalendar(trade_date=date))

        # 删除过期日期
        if to_remove:
            db.query(TradingCalendar).filter(
                TradingCalendar.trade_date.in_(to_remove)
            ).delete(synchronize_session=False)

        # 提交更改
        db.commit()
        logger.info(
            f"Synced trading calendar: Added {len(to_add)} dates, Removed {len(to_remove)} dates"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error syncing trading calendar: {e}")
    finally:
        db.close()


# 修改：is_trading_day 函数，优先从缓存或数据库中读取交易日历
@lru_cache(maxsize=None)  # 新增：使用缓存机制
def is_trading_day(date):
    """
    判断给定日期是否为交易日
    :param date: 需要判断的日期
    :return: True if trading day, False otherwise
    """
    # 优先从缓存中读取交易日历
    cached_calendar = load_trading_calendar_from_db()
    if cached_calendar:
        return date.strftime("%Y-%m-%d") in cached_calendar

    # 如果缓存为空，从 AkShare 获取交易日历并保存到数据库
    trading_calendar = ak.tool_trade_date_hist_sina()["trade_date"].values.tolist()
    save_trading_calendar_to_db(trading_calendar)
    return date.strftime("%Y-%m-%d") in trading_calendar


def fetch_stock_data(date_str_req: Optional[str] = None) -> pd.DataFrame:
    """
    使用 AkShare 获取 A 股市场实时数据
    :return: 包含股票数据的 DataFrame
    """
    try:
        # 检查本地CSV文件是否存在
        today = datetime.now().date()
        file_str = date_str_req if date_str_req else today.strftime("%Y%m%d")
        local_csv_path = f"stock_data_{file_str}.csv"

        if os.path.exists(local_csv_path):
            # 从本地CSV读取数据
            df = pd.read_csv(
                local_csv_path,
                dtype={"代码": str},  # 确保代码列为字符串类型
            )
            logger.info("成功从本地CSV加载股票数据")

            # 从文件名提取日期
            match = re.search(r"stock_data_(\d{8})", local_csv_path)
            if match:
                date_str = match.group(1)
                date = datetime.strptime(date_str, "%Y%m%d").date()
            else:
                raise ValueError("无法从文件名中提取日期")
                date = datetime.now().date()  # 默认使用当前日期
        else:
            # 获取实时行情数据
            df = ak.stock_zh_a_spot_em()
            if df.empty:
                logger.warning("没有获取到股票数据")
                return pd.DataFrame()

            # 判断当前时间是否为交易日
            current_time = datetime.now()
            if current_time.hour >= 15:
                date = current_time.date()
            else:
                # 优化逻辑：逐次减一天查找最近的交易日，最大查找次数为10
                date = current_time.date()
                max_attempts = 10
                attempts = 0
                while not is_trading_day(date) and attempts < max_attempts:
                    date -= timedelta(days=1)
                    attempts += 1
                if attempts == max_attempts:
                    print("警告：在10次查找内未找到交易日，使用当前日期作为默认值")
                    date = current_time.date()

        df.to_csv(f"stock_data_{date.strftime('%Y%m%d')}", index=False)
        logger.info("成功从AkShare获取股票数据并保存到CSV")
        # 清洗数据
        df = clean_stock_data(df)

        # 添加日期字段
        df["trade_date"] = date.strftime("%Y-%m-%d")
        return df
    except Exception as e:
        print(f"Error fetching stock data: {e}")
        return pd.DataFrame()


def save_stock_data(df: pd.DataFrame):
    """Saves stock data to the database using a managed session."""
    if df.empty:
        logger.info("DataFrame is empty, skipping database save.")
        return

    with db_session_scope() as db:
        data = df.to_dict(orient="records")
        # Ensure all keys in each dict are strings
        data = [{str(k): v for k, v in record.items()} for record in data]
        # Check if date already exists to prevent duplicates
        trade_date = data[0]["trade_date"]
        exists = db.query(StockData).filter(StockData.trade_date == trade_date).first()
        if not exists:
            db.bulk_insert_mappings(StockData.__mapper__, data)
            logger.info(
                f"Successfully saved {len(data)} records for date {trade_date}."
            )
        else:
            logger.warning(
                f"Data for date {trade_date} already exists in DB. Skipping."
            )


def get_latest_trade_date(trading_days: set[str]) -> date:
    """
    Calculates the most recent valid trading date.

    If it's before 3 PM on a trading day, it returns the previous trading day.
    Otherwise, it returns today's date (if it's a trading day) or the most
    recent previous trading day.
    """
    today = datetime.now().date()
    # If market is still open, data is for the previous day
    if datetime.now().hour < 15 and today.strftime("%Y-%m-%d") in trading_days:
        date_to_check = today - timedelta(days=1)
    else:
        date_to_check = today

    # Find the most recent trading day, looking back up to 10 days
    for i in range(10):
        check_str = (date_to_check - timedelta(days=i)).strftime("%Y-%m-%d")
        if check_str in trading_days:
            return date_to_check - timedelta(days=i)

    logger.error("Could not find a recent trading day in the last 10 days.")
    raise ValueError("Failed to determine a valid recent trade date.")


# This function should be called at startup and on a schedule (e.g., daily)
@lru_cache(maxsize=1)
def get_trading_calendar_set(force_refresh: bool = False) -> set[str]:
    """
    Loads the trading calendar from the DB. Uses a cache for performance.
    The cache is only refreshed when force_refresh=True.
    """
    logger.info("Loading trading calendar into memory set.")
    with db_session_scope() as db:
        dates = (
            db.query(TradingCalendar.trade_date)
            .filter(TradingCalendar.trade_date >= datetime.now() - timedelta(days=365))
            .all()
        )
        return {d.trade_date.strftime("%Y-%m-%d") for d in dates}


# Refactored fetch_stock_data, now with clear responsibilities
def get_stock_data(target_date: date) -> pd.DataFrame:
    """
    Fetches stock data for a specific date, prioritizing local cache.

    This function is now responsible ONLY for fetching/loading for a GIVEN date.
    The logic to decide the date is handled elsewhere.
    """
    date_str = target_date.strftime("%Y%m%d")
    local_csv_path = f"stock_data_{date_str}.csv"

    # 1. Try loading from local CSV cache
    if os.path.exists(local_csv_path):
        logger.info(f"Loading stock data from local file: {local_csv_path}")
        df = pd.read_csv(local_csv_path, dtype={"代码": str})
        df["trade_date"] = target_date.strftime("%Y-%m-%d")
        return df

    # 2. If not cached, fetch from API
    logger.info(f"Fetching stock data from AkShare for date: {target_date}")
    try:
        df = ak.stock_zh_a_spot_em()
        if df.empty:
            logger.warning("AkShare returned no data.")
            return pd.DataFrame()

        # 3. Clean and save to cache for next time
        df = clean_stock_data(df)
        df["trade_date"] = target_date.strftime("%Y-%m-%d")
        df.to_csv(local_csv_path, index=False)
        logger.info(f"Saved new data to {local_csv_path}")
        return df
    except Exception as e:
        logger.error(f"Failed to fetch data from AkShare: {e}")
        return pd.DataFrame()


def get_stock_data_for_date():
    """
    Fetches stock data for a specific date, ensuring the date is a trading day.
    If the date is not a trading day, it fetches data for the most recent trading day.
    """
    # 2. Get the calendar once into a fast, in-memory set
    trading_days_set = get_trading_calendar_set(force_refresh=True)

    # 3. Determine the date you want to process
    try:
        target_date = get_latest_trade_date(trading_days_set)
        logger.info(f"Determined target trade date is: {target_date}")

        # 4. Get the data for that specific date
        stock_df = get_stock_data(target_date)

        # 5. If data is retrieved, save it to the database
        if not stock_df.empty:
            save_stock_data(stock_df)

    except ValueError as e:
        logger.error(f"Could not run stock data job: {e}")
