"""Background job manager using asyncio tasks."""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Callable, Optional, Any
from dataclasses import dataclass
import logging

from sqlalchemy import select
from services.database import async_session, Job, JobStatus, Video

logger = logging.getLogger(__name__)


@dataclass
class JobProgress:
    """Job progress information."""
    progress: int  # 0-100
    message: str


class JobManager:
    """Manages background jobs using asyncio tasks."""

    def __init__(self):
        self._jobs: Dict[str, asyncio.Task] = {}
        self._progress_callbacks: Dict[str, list[Callable]] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, job_func: Callable, *args, **kwargs) -> str:
        """
        Create and start a background job.

        Args:
            job_func: Async function to run as background job
            *args, **kwargs: Arguments to pass to job_func

        Returns:
            Job ID (UUID string)
        """
        job_id = str(uuid.uuid4())

        # Create job record in database
        async with async_session() as session:
            job = Job(
                id=job_id,
                status=JobStatus.PENDING,
                progress=0,
                progress_message="Job created",
            )
            session.add(job)
            await session.commit()

        # Create asyncio task
        task = asyncio.create_task(self._run_job(job_id, job_func, *args, **kwargs))

        async with self._lock:
            self._jobs[job_id] = task
            self._progress_callbacks[job_id] = []

        logger.info(f"Created job {job_id}")
        return job_id

    async def _run_job(self, job_id: str, job_func: Callable, *args, **kwargs):
        """
        Run a job and handle status updates.

        Args:
            job_id: Job ID
            job_func: Function to execute
        """
        try:
            # Update status to processing
            await self._update_job_status(
                job_id,
                JobStatus.PROCESSING,
                started_at=datetime.utcnow()
            )

            # Create progress callback for this job
            async def progress_callback(progress: int, message: str):
                await self.update_progress(job_id, progress, message)

            # Run the job function with progress callback
            result = await job_func(job_id, progress_callback, *args, **kwargs)

            # Mark as completed
            await self._update_job_status(
                job_id,
                JobStatus.COMPLETED,
                progress=100,
                progress_message="Job completed successfully",
                completed_at=datetime.utcnow()
            )

            logger.info(f"Job {job_id} completed successfully")
            return result

        except asyncio.CancelledError:
            # Job was cancelled
            await self._update_job_status(
                job_id,
                JobStatus.CANCELLED,
                progress_message="Job cancelled by user",
                completed_at=datetime.utcnow()
            )
            logger.info(f"Job {job_id} was cancelled")
            raise

        except Exception as e:
            # Job failed
            error_msg = str(e)
            await self._update_job_status(
                job_id,
                JobStatus.FAILED,
                error_message=error_msg,
                progress_message=f"Job failed: {error_msg}",
                completed_at=datetime.utcnow()
            )
            logger.error(f"Job {job_id} failed: {error_msg}", exc_info=True)
            raise

        finally:
            # Cleanup
            async with self._lock:
                if job_id in self._jobs:
                    del self._jobs[job_id]
                if job_id in self._progress_callbacks:
                    del self._progress_callbacks[job_id]

    async def _update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[int] = None,
        progress_message: Optional[str] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ):
        """Update job status in database."""
        async with async_session() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()

            if job:
                job.status = status
                if progress is not None:
                    job.progress = progress
                if progress_message is not None:
                    job.progress_message = progress_message
                if error_message is not None:
                    job.error_message = error_message
                if started_at is not None:
                    job.started_at = started_at
                if completed_at is not None:
                    job.completed_at = completed_at

                await session.commit()

    async def update_progress(self, job_id: str, progress: int, message: str):
        """
        Update job progress.

        Args:
            job_id: Job ID
            progress: Progress percentage (0-100)
            message: Progress message
        """
        # Update database
        async with async_session() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()

            if job:
                job.progress = progress
                job.progress_message = message
                await session.commit()

        # Notify callbacks
        async with self._lock:
            callbacks = self._progress_callbacks.get(job_id, [])

        for callback in callbacks:
            try:
                await callback(JobProgress(progress=progress, message=message))
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status.

        Args:
            job_id: Job ID

        Returns:
            Job status dictionary or None if not found
        """
        async with async_session() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()

            if job:
                return job.to_dict()
            return None

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job.

        Args:
            job_id: Job ID

        Returns:
            True if job was cancelled, False if not found or already completed
        """
        async with self._lock:
            task = self._jobs.get(job_id)

        if task and not task.done():
            task.cancel()
            logger.info(f"Cancelled job {job_id}")
            return True

        return False

    async def register_progress_callback(self, job_id: str, callback: Callable):
        """
        Register a callback for job progress updates.

        Args:
            job_id: Job ID
            callback: Async function that receives JobProgress
        """
        async with self._lock:
            if job_id not in self._progress_callbacks:
                self._progress_callbacks[job_id] = []
            self._progress_callbacks[job_id].append(callback)

    async def unregister_progress_callback(self, job_id: str, callback: Callable):
        """Unregister a progress callback."""
        async with self._lock:
            if job_id in self._progress_callbacks:
                try:
                    self._progress_callbacks[job_id].remove(callback)
                except ValueError:
                    pass

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[Dict[str, Any]]:
        """
        List jobs with optional filtering.

        Args:
            status: Filter by status
            limit: Maximum number of jobs to return
            offset: Offset for pagination

        Returns:
            List of job dictionaries
        """
        async with async_session() as session:
            query = select(Job).order_by(Job.created_at.desc())

            if status:
                query = query.where(Job.status == status)

            query = query.limit(limit).offset(offset)
            result = await session.execute(query)
            jobs = result.scalars().all()

            return [job.to_dict() for job in jobs]


# Global job manager instance
job_manager = JobManager()
