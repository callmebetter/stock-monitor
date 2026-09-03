from typing import Optional
from pathlib import Path
import akshare as ak
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from functools import lru_cache
import logging
import re
import os

from models.stock_model import StockData, TradingCalendar
from database.database_utils import db_session_scope
from helpers.data_cleaner import clean_stock_data
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

# CSV 缓存目录
CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────
#  交易日历
# ──────────────────────────────────────────

def load_trading_calendar_from_db() -> list:
    """从数据库加载近一年的交易日历"""
    with db_session_scope() as db:
        rows = (
            db.query(TradingCalendar.trade_date)
            .order_by(TradingCalendar.trade_date.desc())
            .limit(365)
            .all()
        )
        logger.debug(f"Loaded {len(rows)} trading dates from DB")
        return [row[0] for row in rows]


def save_trading_calendar_to_db(trading_calendar: list):
    """批量保存交易日历到数据库"""
    with db_session_scope() as db:
        for d in trading_calendar:
            db.add(TradingCalendar(trade_date=d))


def sync_trading_calendar() -> dict:
    """
    同步交易日历：从 AkShare 拉取最新数据，与数据库做差量更新。
    """
    try:
        logger.info("Initiating trading calendar synchronization...")

        ak_calendar_df = ak.tool_trade_date_hist_sina()
        if ak_calendar_df.empty:
            logger.warning("AkShare returned an empty trading calendar.")
            return {"status": "warning", "message": "AkShare data is empty."}

        latest_dates = set(ak_calendar_df["trade_date"].values)

        with db_session_scope() as db:
            # 查询 DB 中所有日期（而非仅 365 天），确保差集计算正确
            all_rows = db.query(TradingCalendar.trade_date).all()
            cached_dates = set(row[0] for row in all_rows)
            logger.debug(f"DB has {len(cached_dates)} dates, AkShare has {len(latest_dates)} dates")
            to_add = latest_dates - cached_dates
            to_remove = cached_dates - latest_dates

            if to_add:
                db.add_all([TradingCalendar(trade_date=d) for d in to_add])
                logger.info(f"Prepared to add {len(to_add)} new trading dates.")

            if to_remove:
                db.query(TradingCalendar).filter(
                    TradingCalendar.trade_date.in_(list(to_remove))
                ).delete(synchronize_session=False)
                logger.info(f"Prepared to remove {len(to_remove)} outdated trading dates.")

            if not to_add and not to_remove:
                return {"status": "success", "message": "Trading calendar is already up to date."}

        logger.info(f"Synced trading calendar: +{len(to_add)}, -{len(to_remove)}")
        return {
            "status": "success",
            "message": "Trading calendar synchronized successfully.",
            "added_count": len(to_add),
            "removed_count": len(to_remove),
        }

    except SQLAlchemyError as e:
        logger.error(f"Database error during trading calendar sync: {e}", exc_info=True)
        return {"status": "error", "message": f"Database error: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error during trading calendar sync: {e}", exc_info=True)
        return {"status": "error", "message": f"Unexpected error: {e}"}


@lru_cache(maxsize=None)
def is_trading_day(d: date) -> bool:
    """判断给定日期是否为交易日"""
    cached_calendar = load_trading_calendar_from_db()
    if cached_calendar:
        return d.strftime("%Y-%m-%d") in cached_calendar

    # 缓存为空时从 AkShare 获取并保存
    trading_calendar = ak.tool_trade_date_hist_sina()["trade_date"].values.tolist()
    save_trading_calendar_to_db(trading_calendar)
    return d.strftime("%Y-%m-%d") in trading_calendar


@lru_cache(maxsize=1)
def get_trading_calendar_set() -> set[str]:
    """加载交易日历到内存 set，用于快速查找"""
    logger.info("Loading trading calendar into memory set.")
    dates = load_trading_calendar_from_db()
    return {d.strftime("%Y-%m-%d") for d in dates}


def get_latest_trade_date(trading_days: set[str]) -> date:
    """计算最近的交易日（回看最多 10 天）"""
    today = datetime.now().date()
    date_to_check = today - timedelta(days=1) if (
        datetime.now().hour < 15 and today.strftime("%Y-%m-%d") in trading_days
    ) else today

    for i in range(10):
        check = date_to_check - timedelta(days=i)
        if check.strftime("%Y-%m-%d") in trading_days:
            return check

    raise ValueError("Failed to determine a valid recent trade date.")


# ──────────────────────────────────────────
#  股票数据采集
# ──────────────────────────────────────────

def _csv_path(date_str: str) -> Path:
    """生成 CSV 缓存路径"""
    return CACHE_DIR / f"stock_data_{date_str}.csv"


def fetch_stock_data(date_str_req: Optional[str] = None) -> pd.DataFrame:
    """
    获取 A 股实时行情数据，优先从本地 CSV 缓存读取。
    """
    try:
        today = datetime.now().date()
        file_str = date_str_req or today.strftime("%Y%m%d")
        csv_path = _csv_path(file_str)

        if csv_path.exists():
            df = pd.read_csv(csv_path, dtype={"代码": str})
            logger.info("Loaded stock data from local CSV cache")

            match = re.search(r"stock_data_(\d{8})", csv_path.name)
            if match:
                trade_date = datetime.strptime(match.group(1), "%Y%m%d").date()
            else:
                raise ValueError(f"Cannot extract date from filename: {csv_path.name}")
        else:
            df = ak.stock_zh_a_spot_em()
            if df.empty:
                logger.warning("AkShare returned no data")
                return pd.DataFrame()

            # 确定交易日期
            current_time = datetime.now()
            if current_time.hour >= 15:
                trade_date = current_time.date()
            else:
                trade_date = current_time.date()
                for _ in range(10):
                    if is_trading_day(trade_date):
                        break
                    trade_date -= timedelta(days=1)
                else:
                    logger.warning("No trading day found in 10 attempts, using today")
                    trade_date = current_time.date()

            # 保存到缓存
            df.to_csv(csv_path, index=False)
            logger.info(f"Saved AkShare data to {csv_path}")

        df = clean_stock_data(df)
        df["trade_date"] = trade_date.strftime("%Y-%m-%d")
        return df

    except Exception as e:
        logger.error(f"Error fetching stock data: {e}", exc_info=True)
        return pd.DataFrame()


def save_stock_data(df: pd.DataFrame):
    """保存股票数据到数据库（去重）"""
    if df.empty:
        logger.info("DataFrame is empty, skipping database save.")
        return

    with db_session_scope() as db:
        data = [{str(k): v for k, v in record.items()} for record in df.to_dict(orient="records")]
        trade_date = data[0]["trade_date"]

        exists = db.query(StockData).filter(StockData.trade_date == trade_date).first()
        if not exists:
            db.bulk_insert_mappings(StockData.__mapper__, data)
            logger.info(f"Saved {len(data)} records for date {trade_date}.")
        else:
            logger.warning(f"Data for date {trade_date} already exists. Skipping.")


def get_stock_data_for_date():
    """获取指定日期的股票数据并入库"""
    trading_days_set = get_trading_calendar_set()

    try:
        target_date = get_latest_trade_date(trading_days_set)
        logger.info(f"Determined target trade date: {target_date}")

        stock_df = fetch_stock_data(target_date.strftime("%Y%m%d"))
        if not stock_df.empty:
            save_stock_data(stock_df)

    except ValueError as e:
        logger.error(f"Could not run stock data job: {e}")
