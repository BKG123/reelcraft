"""
Script to add existing video from outputs folder to database.
"""

import asyncio
from pathlib import Path
from services.database import async_session, Video, StorageLocation


async def add_video():
    """Add existing video to database."""

    # Video details
    video_file = "how_chatgpt_actually_works_(the_simple_explanation).mp4"
    source_url = "https://medium.com/data-science-at-microsoft/how-large-language-models-work-91c362f5b78f"
    title = "How ChatGPT Actually Works (The Simple Explanation)"

    # File information
    video_path = Path("assets/temp/outputs") / video_file
    full_path = Path.cwd() / video_path

    if not full_path.exists():
        print(f"Error: Video file not found at {full_path}")
        return

    # Get file size in MB
    size_bytes = full_path.stat().st_size
    size_mb = round(size_bytes / (1024 * 1024), 2)

    # Duration from ffprobe (91.609 seconds)
    duration = 91.609

    print(f"Adding video to database:")
    print(f"  Title: {title}")
    print(f"  URL: {source_url}")
    print(f"  File: {video_path}")
    print(f"  Size: {size_mb} MB")
    print(f"  Duration: {duration:.2f} seconds")

    async with async_session() as session:
        # Check if video already exists
        from sqlalchemy import select
        result = await session.execute(
            select(Video).where(Video.source_url == source_url)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"\nVideo already exists in database with ID: {existing.id}")
            print(f"Updating storage location to LOCAL...")
            existing.storage_location = StorageLocation.LOCAL
            existing.file_path = str(video_path)
            await session.commit()
            print(f"Updated video ID {existing.id}")
            return

        # Create new video entry
        video = Video(
            title=title,
            source_url=source_url,
            file_path=str(video_path),
            storage_location=StorageLocation.LOCAL,
            duration=duration,
            size_mb=size_mb,
        )

        session.add(video)
        await session.commit()
        await session.refresh(video)

        print(f"\nVideo added successfully!")
        print(f"  ID: {video.id}")
        print(f"  Storage Location: {video.storage_location.value}")


if __name__ == "__main__":
    asyncio.run(add_video())
