from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from services.data_collector import fetch_stock_data, save_stock_data
from services.stock_analyzer import get_screened_stocks

router = APIRouter()

def get_db():
    """
    获取数据库会话
    :return: 数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
def update_stock_data(db: Session = Depends(get_db)):
    """
    更新股票数据
    :param db: 数据库会话
    :return: 更新结果
    """
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