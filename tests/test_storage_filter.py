"""
Test script to verify storage location filtering works correctly.
"""

import asyncio
from services.database import async_session, Video, StorageLocation
from sqlalchemy import select


async def test_storage_filter():
    """Test querying videos by storage location."""

    async with async_session() as session:
        # Test 1: Get all videos
        print("=" * 60)
        print("TEST 1: All Videos")
        print("=" * 60)
        result = await session.execute(
            select(Video).order_by(Video.created_at.desc())
        )
        all_videos = result.scalars().all()
        print(f"Total videos: {len(all_videos)}")
        for video in all_videos:
            print(f"  [{video.id}] {video.title}")
            print(f"      Storage: {video.storage_location.value}")
            print(f"      Path: {video.file_path[:60]}...")
        print()

        # Test 2: Get only LOCAL videos
        print("=" * 60)
        print("TEST 2: LOCAL Videos Only")
        print("=" * 60)
        result = await session.execute(
            select(Video)
            .where(Video.storage_location == StorageLocation.LOCAL)
            .order_by(Video.created_at.desc())
        )
        local_videos = result.scalars().all()
        print(f"Total LOCAL videos: {len(local_videos)}")
        for video in local_videos:
            print(f"  [{video.id}] {video.title}")
            print(f"      Path: {video.file_path}")
        print()

        # Test 3: Get only CLOUD videos
        print("=" * 60)
        print("TEST 3: CLOUD Videos Only")
        print("=" * 60)
        result = await session.execute(
            select(Video)
            .where(Video.storage_location == StorageLocation.CLOUD)
            .order_by(Video.created_at.desc())
        )
        cloud_videos = result.scalars().all()
        print(f"Total CLOUD videos: {len(cloud_videos)}")
        for video in cloud_videos:
            print(f"  [{video.id}] {video.title}")
            print(f"      URL: {video.file_path[:80]}...")
        print()

        # Summary
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total videos: {len(all_videos)}")
        print(f"LOCAL: {len(local_videos)}")
        print(f"CLOUD: {len(cloud_videos)}")


if __name__ == "__main__":
    asyncio.run(test_storage_filter())
