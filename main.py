import logging
import time  # Import time module for sleep function
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from services.data_collector import fetch_stock_data, save_stock_data

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化调度器
scheduler = BackgroundScheduler()

# 创建FastAPI实例
from fastapi import FastAPI
from routes.api_routes import router as api_router

app = FastAPI(title="Stock Monitoring API")

app.include_router(api_router)


def daily_data_collection():
    """
    每日定时任务：采集股票数据并保存到数据库
    默认在每个交易日的 15:30 执行
    """
    logger.info("Starting daily stock data collection...")
    try:
        df = fetch_stock_data()
        save_stock_data(df)
    except Exception as e:
        logger.error(f"Error in daily data collection: {e}")


def init_scheduler():
    """初始化定时任务，每天15:30执行"""
    # 添加每日任务，15:30 执行
    scheduler.add_job(
        func=daily_data_collection,
        trigger='cron',
        hour=15,
        minute=30
    )
    
    # 启动调度器
    scheduler.start()
    logger.info("Scheduler started.")

# 注册退出时的清理函数
atexit.register(lambda: scheduler.shutdown() if not scheduler.shutdown else None)

# 导入FastAPI实例
from main import app  # 确保app实例可以从main模块导入

if __name__ == "__main__":
    # 初始化定时任务
    init_scheduler()
    
    # 启动FastAPI应用
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
    
    # 保持主线程运行，防止程序退出
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
