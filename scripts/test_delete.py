"""
Test script to verify video deletion functionality.
This script performs a dry-run test without actually deleting anything.
"""

import asyncio
from pathlib import Path
from services.database import async_session, Video, StorageLocation
from services.storage import storage_manager
from sqlalchemy import select


async def test_delete_logic():
    """Test delete logic without actually deleting."""

    async with async_session() as session:
        # Get all videos
        result = await session.execute(
            select(Video).order_by(Video.created_at.desc())
        )
        videos = result.scalars().all()

        print("=" * 70)
        print("VIDEO DELETE TEST (DRY RUN)")
        print("=" * 70)
        print(f"\nTotal videos in database: {len(videos)}\n")

        for video in videos:
            print("-" * 70)
            print(f"Video ID: {video.id}")
            print(f"Title: {video.title}")
            print(f"Storage: {video.storage_location.value}")
            print(f"File Path: {video.file_path}")

            # Check what would happen on delete
            if video.storage_location == StorageLocation.CLOUD:
                print(f"\n[CLOUD DELETE LOGIC]")
                if video.file_path and video.file_path.startswith(("http://", "https://")):
                    parts = video.file_path.split("/")
                    if len(parts) >= 3:
                        object_key = "/".join(parts[-3:])
                        print(f"  Would delete from R2 with object_key: {object_key}")
                        print(f"  R2 Enabled: {storage_manager.is_enabled()}")
                    else:
                        print(f"  ERROR: Could not parse object key from URL")
                else:
                    print(f"  ERROR: Invalid cloud URL")

            else:  # LOCAL
                print(f"\n[LOCAL DELETE LOGIC]")
                if video.file_path:
                    local_path = Path(video.file_path)
                    if not local_path.is_absolute():
                        local_path = Path.cwd() / local_path

                    print(f"  Absolute path: {local_path}")
                    print(f"  File exists: {local_path.exists()}")

                    if local_path.exists():
                        size_mb = local_path.stat().st_size / (1024 * 1024)
                        print(f"  File size: {size_mb:.2f} MB")
                        print(f"  Would delete file: {local_path}")
                    else:
                        print(f"  WARNING: File not found!")
                else:
                    print(f"  ERROR: No file path")

            print(f"\n  Database entry would be deleted: YES")
            print()

        print("=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"Total videos: {len(videos)}")
        print(f"Cloud videos: {sum(1 for v in videos if v.storage_location == StorageLocation.CLOUD)}")
        print(f"Local videos: {sum(1 for v in videos if v.storage_location == StorageLocation.LOCAL)}")
        print("\nNo actual deletions were performed (dry run).")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_delete_logic())
