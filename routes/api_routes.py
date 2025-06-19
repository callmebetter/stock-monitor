import datetime
from typing import Annotated
from fastapi import APIRouter, Depends,Body
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from services.data_collector import fetch_stock_data, save_stock_data, sync_trading_calendar
from services.stock_analyzer import get_screened_stocks
import logging
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)
router = APIRouter()

class StockUpdateRequest(BaseModel):
    date: str
    
    @field_validator('date', mode='before')
    @classmethod
    def validate_date_format(cls, value):
        """
        Validates that the date string is in 'YYYY-MM-DD' format.
        Converts the string to a datetime.date object if valid.
        """
        if isinstance(value, datetime.date):
            return value  # Already a date object, no need to parse

        if not isinstance(value, str):
            raise TypeError("Date must be a string in 'YYYY-MM-DD' format.")

        try:
            # Attempt to parse the string into a date object
            parsed_date = datetime.date.fromisoformat(value)
            return parsed_date  # Return the date object for direct use in the model
        except ValueError as e:
            # Log the error for debugging purposes (optional)
            logger.error(f"Invalid date format received: '{value}'. Error: {e}")
            raise ValueError("Invalid date format. Expected 'YYYY-MM-DD'.")
@router.get("/stocks/today")
def get_today_stock_data(db: Session = Depends(get_db)):
    """
    获取今日最新行情
    :param db: 数据库会话
    :return: 今日最新行情数据
    """
    df = fetch_stock_data()
    return df.to_dict(orient='records')

@router.post("/stocks/update")
def update_stock_data(date: Annotated[datetime.date, Body(embed=True)], db: Session = Depends(get_db)):
    """
    更新股票数据
    :param db: 数据库会话
    :return: 更新结果
    """
    # retrieve date from the request body if needed
    logger.info(f"Updating stock data for date: {date}")
    df = fetch_stock_data()
    if not df.empty:
        save_stock_data(df)
        return {"message": "Stock data updated successfully"}
    else:
        return {"error": "Failed to fetch stock data"}

@router.get("/stocks/screened")
def get_screened_stocks_endpoint(db: Session = Depends(get_db)):
    """
    获取符合选股条件的股票列表
    :param db: 数据库会话
    :return: 符合条件的股票列表
    """
    selected_stocks = get_screened_stocks()
    return selected_stocks.to_dict(orient='records')

@router.post("/stocks/sync_trading_calendar")
def sync_trading_calendar_endpoint():
    res = sync_trading_calendar()
    if res is None:
        return {"error": "Failed to sync trading calendar"}
    return res