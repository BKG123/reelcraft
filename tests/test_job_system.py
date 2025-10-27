"""Test script for the job-based video generation system."""

import asyncio
from database import init_db, async_session, Job, Video
from job_manager import job_manager
from sqlalchemy import select


async def test_job_creation():
    """Test basic job creation and tracking."""
    print("Testing job creation...")

    async def dummy_job(job_id: str, progress_callback, message: str):
        """Dummy job for testing."""
        await progress_callback(10, "Starting...")
        await asyncio.sleep(1)
        await progress_callback(50, f"Processing: {message}")
        await asyncio.sleep(1)
        await progress_callback(100, "Completed!")
        return {"result": message}

    # Create a job
    job_id = await job_manager.create_job(dummy_job, message="Test message")
    print(f"Created job: {job_id}")

    # Wait a bit and check status
    await asyncio.sleep(0.5)
    status = await job_manager.get_job_status(job_id)
    print(f"Job status after 0.5s: {status['status']} - {status['progress_message']}")

    # Wait for completion
    await asyncio.sleep(2)
    status = await job_manager.get_job_status(job_id)
    print(f"Final job status: {status['status']} - {status['progress_message']}")

    return job_id


async def test_database():
    """Test database operations."""
    print("\nTesting database operations...")

    # Initialize database
    await init_db()
    print("Database initialized")

    # Query jobs
    async with async_session() as session:
        result = await session.execute(select(Job))
        jobs = result.scalars().all()
        print(f"Total jobs in database: {len(jobs)}")

        if jobs:
            for job in jobs[:3]:  # Show first 3
                print(f"  - Job {job.id}: {job.status.value} ({job.progress}%)")

        # Query videos
        result = await session.execute(select(Video))
        videos = result.scalars().all()
        print(f"Total videos in database: {len(videos)}")

        if videos:
            for video in videos[:3]:  # Show first 3
                print(f"  - Video {video.id}: {video.title}")


async def test_job_cancellation():
    """Test job cancellation."""
    print("\nTesting job cancellation...")

    async def long_running_job(job_id: str, progress_callback):
        """Long running job for testing cancellation."""
        for i in range(10):
            await progress_callback(i * 10, f"Step {i}/10")
            await asyncio.sleep(1)

    # Create job
    job_id = await job_manager.create_job(long_running_job)
    print(f"Created long-running job: {job_id}")

    # Wait a bit then cancel
    await asyncio.sleep(2)
    cancelled = await job_manager.cancel_job(job_id)
    print(f"Job cancelled: {cancelled}")

    # Check status
    await asyncio.sleep(0.5)
    status = await job_manager.get_job_status(job_id)
    print(f"Job status after cancellation: {status['status']}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Job System Test Suite")
    print("=" * 60)

    # Initialize database first
    print("\nInitializing database...")
    await init_db()
    print("Database initialized!\n")

    # Test 1: Basic job creation
    await test_job_creation()

    # Test 2: Database operations
    await test_database()

    # Test 3: Job cancellation
    await test_job_cancellation()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
