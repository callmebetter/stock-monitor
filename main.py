from contextlib import asynccontextmanager
from services.scheduler_service import SchedulerService
from app_logger import setup_logging
import logging
from services.data_collector import sync_trading_calendar

setup_logging(log_level=logging.DEBUG, console=True)
logger = logging.getLogger(__name__)

scheduler_service = SchedulerService()

# 创建FastAPI实例
from fastapi import FastAPI
from routes.api_routes import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI应用的生命周期管理器，用于在应用启动和关闭时执行特定操作。
    """
    # 在应用启动时执行初始化操作
    logger.info("Starting up the application...")
    # 初始化数据库
    from database import init_db

    init_db()
    scheduler_service.start_scheduler()
    scheduler_service.add_job(
        func=sync_trading_calendar,
        trigger="cron", 
        month=1,
        hour=0, 
        minute=0, 
    )

    yield
    # 在应用关闭时执行清理操作
    logger.info("Shutting down the application...")
    scheduler_service.stop_scheduler()


app = FastAPI(title="Stock Monitoring API", lifespan=lifespan)

app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    # 启动FastAPI应用
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
