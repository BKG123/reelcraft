"""
Simple test script to upload a video to cloud storage.
"""

import asyncio
import sys
from pathlib import Path
from services.storage import storage_manager
from services.database import init_db, async_session, Video
from sqlalchemy import select
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def test_upload():
    """Test cloud storage upload with first available video"""

    # Check if cloud storage is enabled
    if not storage_manager.is_enabled():
        print("\n❌ Cloud storage is NOT enabled")
        print("\nTo enable Cloudflare R2:")
        print("  1. Set R2_ENABLED=true in .env")
        print("  2. Add your R2 credentials")
        print("\nSee resources/STORAGE_SETUP.md for details")
        return False

    print("✅ Cloud storage is ENABLED")

    # Initialize database
    await init_db()

    # Find videos
    output_dir = Path("assets/temp/outputs")
    videos = list(output_dir.glob("*.mp4"))

    if not videos:
        print("\n❌ No videos found in assets/temp/outputs/")
        return False

    # Use first video
    video_path = videos[0]
    video_title = video_path.stem
    size_mb = video_path.stat().st_size / (1024 * 1024)

    print(f"\n📹 Testing upload with: {video_title}")
    print(f"   Size: {size_mb:.2f} MB")
    print(f"   Path: {video_path}")

    # Create or get video in database
    async with async_session() as session:
        # Check if video exists
        result = await session.execute(
            select(Video).where(Video.title == video_title)
        )
        video = result.scalar_one_or_none()

        if not video:
            # Create new video entry
            video = Video(
                title=video_title,
                source_url=f"test://upload/{video_title}",
                file_path=str(video_path),
                size_mb=size_mb
            )
            session.add(video)
            await session.commit()
            await session.refresh(video)
            print(f"   📝 Created database entry (ID: {video.id})")
        else:
            print(f"   📝 Using existing database entry (ID: {video.id})")

        # Upload to cloud
        print(f"\n☁️  Uploading to cloud storage...")
        cloud_url = await storage_manager.upload_video(str(video_path), video.id)

        if cloud_url:
            print(f"\n✅ Upload SUCCESSFUL!")
            print(f"🔗 Public URL: {cloud_url}")

            # Update database with cloud URL
            video.file_path = cloud_url
            await session.commit()
            print(f"💾 Database updated with cloud URL")
            return True
        else:
            print(f"\n❌ Upload FAILED")
            return False


async def main():
    print("\n" + "="*60)
    print("   ReelCraft Cloud Storage Upload Test")
    print("="*60 + "\n")

    try:
        success = await test_upload()

        print("\n" + "="*60)
        if success:
            print("✅ Test completed successfully!")
        else:
            print("❌ Test failed")
        print("="*60 + "\n")

        sys.exit(0 if success else 1)

    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
