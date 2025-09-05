import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from typing import Optional
from src.services.sync_service import SyncService
from src.core.config import Settings
from src.core.sync_state import sync_state

logger = logging.getLogger(__name__)


class SyncScheduler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.scheduler = AsyncIOScheduler()
        self.sync_service = None
        self.last_sync: Optional[datetime] = None
        self.last_sync_result: Optional[dict] = None
        
    async def sync_job(self):
        """Job to run the sync process"""
        try:
            logger.info("Starting scheduled sync...")
            self.last_sync = datetime.now()
            
            async with SyncService(self.settings) as sync_service:
                result = await sync_service.full_sync()
                self.last_sync_result = result
                sync_state.update_sync("scheduled", result)
                logger.info(f"Scheduled sync completed: {result}")
                
        except Exception as e:
            logger.error(f"Scheduled sync failed: {e}")
            self.last_sync_result = {"error": str(e)}
            sync_state.update_sync("scheduled", {"error": str(e)})
            
    def start(self):
        """Start the scheduler"""
        if not self.settings.sync_enabled:
            logger.info("Sync scheduler is disabled")
            return
            
        # Add job to scheduler
        self.scheduler.add_job(
            self.sync_job,
            trigger=IntervalTrigger(minutes=self.settings.sync_interval_minutes),
            id='sync_job',
            name='Keycloak to vCenter sync',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info(f"Sync scheduler started with interval of {self.settings.sync_interval_minutes} minutes")
        
    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Sync scheduler stopped")
            
    def get_status(self) -> dict:
        """Get scheduler status"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
            })
            
        return {
            "running": self.scheduler.running,
            "jobs": jobs,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_sync_result": self.last_sync_result,
            "sync_interval_minutes": self.settings.sync_interval_minutes
        }