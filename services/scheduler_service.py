from apscheduler.schedulers.background import BackgroundScheduler
from services.data_collector import fetch_stock_data, save_stock_data
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
            pd = fetch_stock_data()
            if not pd.empty:
                save_stock_data(pd)
            else:
                logger.info("No data collected.")
        except Exception as e:
            logger.error(f"Error collecting data: {str(e)}")

    def get_scheduler_status(self):
        """Get current scheduler status"""
        return {
            "status": "running" if self.scheduler.running else "stopped",
            "job_count": len(self.scheduler.get_jobs()),
        }
