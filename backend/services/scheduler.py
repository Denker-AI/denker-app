import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI

from .file_cleanup import cleanup_deleted_files

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self, app: FastAPI):
        self.app = app
        self.cleanup_task: Optional[asyncio.Task] = None
        self.is_running = False

    async def start(self):
        """Start the scheduler service"""
        if not self.is_running:
            self.is_running = True
            self.cleanup_task = asyncio.create_task(self._run_cleanup_schedule())
            logger.info("Scheduler service started")

    async def stop(self):
        """Stop the scheduler service"""
        if self.is_running:
            self.is_running = False
            if self.cleanup_task:
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            logger.info("Scheduler service stopped")

    async def _run_cleanup_schedule(self):
        """Run the cleanup schedule"""
        while self.is_running:
            try:
                # Run cleanup at midnight every day
                now = datetime.utcnow()
                next_run = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                
                # Calculate delay until next run
                delay = (next_run - now).total_seconds()
                
                # Wait until next run
                await asyncio.sleep(delay)
                
                # Run cleanup
                logger.info("Starting daily cleanup of deleted files")
                await cleanup_deleted_files()
                logger.info("Completed daily cleanup of deleted files")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup schedule: {str(e)}")
                # Wait for 1 hour before retrying on error
                await asyncio.sleep(3600) 