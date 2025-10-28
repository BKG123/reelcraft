"""
Script to delete a video via the API or directly via database.

Usage:
    python scripts/delete_video.py <video_id>
"""

import asyncio
import sys
from pathlib import Path
from services.database import async_session, Video, StorageLocation
from services.storage import storage_manager
from sqlalchemy import select


async def delete_video_direct(video_id: int):
    """Delete a video directly via database (same logic as API endpoint)."""

    async with async_session() as session:
        # Get the video
        result = await session.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one_or_none()

        if not video:
            print(f"Error: Video ID {video_id} not found")
            return False

        # Display video info
        print("=" * 70)
        print("VIDEO TO DELETE")
        print("=" * 70)
        print(f"ID: {video.id}")
        print(f"Title: {video.title}")
        print(f"Storage: {video.storage_location.value}")
        print(f"File Path: {video.file_path}")
        print(f"Source URL: {video.source_url}")
        print()

        # Confirm deletion
        response = input("Are you sure you want to delete this video? (yes/no): ")
        if response.lower() != "yes":
            print("Deletion cancelled.")
            return False

        print("\nDeleting video...")

        # Store info for logging
        video_title = video.title
        storage_location = video.storage_location
        file_path = video.file_path

        # Delete from storage based on location
        storage_deleted = False
        if storage_location == StorageLocation.CLOUD:
            # Extract object key from cloud URL
            if file_path and file_path.startswith(("http://", "https://")):
                parts = file_path.split("/")
                if len(parts) >= 3:
                    object_key = "/".join(parts[-3:])
                    print(f"Deleting from cloud storage: {object_key}")
                    storage_deleted = await storage_manager.delete_video(object_key)
                    if storage_deleted:
                        print("✓ Cloud file deleted")
                    else:
                        print("✗ Could not delete cloud file (may not be enabled or file not found)")
                else:
                    print(f"✗ Could not parse object key from URL: {file_path}")
        else:  # LOCAL
            if file_path:
                print(f"Deleting local file: {file_path}")
                storage_deleted = await storage_manager.delete_local_video(file_path)
                if storage_deleted:
                    print("✓ Local file deleted")
                else:
                    print("✗ Could not delete local file (file may not exist)")

        # Delete from database
        await session.delete(video)
        await session.commit()
        print("✓ Database entry deleted")

        print()
        print("=" * 70)
        print(f"Video '{video_title}' deleted successfully!")
        print("=" * 70)
        return True


async def list_videos():
    """List all videos in the database."""
    async with async_session() as session:
        result = await session.execute(
            select(Video).order_by(Video.created_at.desc())
        )
        videos = result.scalars().all()

        print("\n" + "=" * 70)
        print("ALL VIDEOS IN DATABASE")
        print("=" * 70)
        for video in videos:
            print(f"\nID: {video.id}")
            print(f"Title: {video.title}")
            print(f"Storage: {video.storage_location.value}")
            print(f"File: {video.file_path[:60]}..." if len(video.file_path) > 60 else f"File: {video.file_path}")
        print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/delete_video.py <video_id>")
        print("       python scripts/delete_video.py list")
        sys.exit(1)

    if sys.argv[1] == "list":
        asyncio.run(list_videos())
    else:
        try:
            video_id = int(sys.argv[1])
            asyncio.run(delete_video_direct(video_id))
        except ValueError:
            print("Error: video_id must be a number")
            sys.exit(1)
