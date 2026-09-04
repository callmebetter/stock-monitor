from apscheduler.schedulers.background import BackgroundScheduler
from services.data_collector import fetch_stock_data, save_stock_data, is_trading_day
from datetime import date
import time
import logging

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()

    def start_scheduler(self):
        """Start the scheduler and add jobs"""
        self.scheduler.add_job(
            func=self._collect_data,
            trigger="cron",
            hour=15,
            minute=30,
            second=0,
            id="collect_stock_data",
            replace_existing=True,
        )
        self.scheduler.add_job(
            func=self._snapshot_gold,
            trigger="cron",
            hour=16,
            minute=0,
            second=0,
            id="snapshot_gold",
            replace_existing=True,
        )
        # Au(T+D) 日K线：日盘收盘后（当日为交易日）+ 夜盘收盘后（前一自然日
        # 为交易日，即周一~周五夜市 20:00~次日02:30，周五夜市归属下周一）
        self.scheduler.add_job(
            func=self._sync_kline,
            trigger="cron",
            hour=15,
            minute=45,
            second=0,
            id="sync_gold_kline_day",
            replace_existing=True,
        )
        self.scheduler.add_job(
            func=self._sync_kline,
            trigger="cron",
            hour=2,
            minute=40,
            second=0,
            id="sync_gold_kline_night",
            kwargs={"day_offset": 1},
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Scheduler started")

    def add_job(self, func, trigger, **kwargs):
        """Add a job to the scheduler"""
        self.scheduler.add_job(func, trigger, **kwargs)

    def stop_scheduler(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    def _collect_data(self):
        """Collect stock data at regular intervals"""
        try:
            logger.info(
                f"Collecting stock data at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            df = fetch_stock_data()
            if not df.empty:
                save_stock_data(df)
            else:
                logger.info("No data collected.")
        except Exception as e:
            logger.error(f"Error collecting data: {e}")

    def _snapshot_gold(self):
        """每日收盘后保存黄金行情快照（非交易日跳过，需 GOLD_SNAPSHOT=1）"""
        import config

        if not config.GOLD_CONFIG.get("snapshot", True):
            logger.info("Gold snapshot disabled (GOLD_SNAPSHOT=0), skipping.")
            return
        if not is_trading_day(date.today()):
            logger.info("Today is not a trading day, skipping gold snapshot.")
            return
        try:
            from services.gold.persistence import snapshot_gold_job

            result = snapshot_gold_job()
            logger.info(f"Gold snapshot result: {result}")
        except Exception as e:
            logger.error(f"Error snapshotting gold data: {e}")

    def _sync_kline(self, day_offset: int = 0):
        """黄金日K线同步：day_offset=0 校验当日为交易日（日盘 15:45）；
        day_offset=1 校验前一自然日为交易日（夜盘 02:40，覆盖周五夜市）。
        非交易日本身无新 K 线，upsert 幂等，重复同步无害。"""
        if not is_trading_day(date.today() - timedelta(days=day_offset)):
            logger.info("Trading-day check failed (offset=%d), skipping kline sync.", day_offset)
            return
        try:
            from services.gold.kline import sync_kline

            result = sync_kline()
            logger.info(f"Gold kline sync result: {result}")
        except Exception as e:
            logger.error(f"Error syncing gold kline: {e}")

    def get_scheduler_status(self):
        """Get current scheduler status"""
        return {
            "status": "running" if self.scheduler.running else "stopped",
            "job_count": len(self.scheduler.get_jobs()),
        }
