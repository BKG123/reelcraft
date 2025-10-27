"""
Test script for storage and cleanup functionality.

This script tests:
1. Cleanup of temporary assets
2. Cloud storage upload (if enabled)
3. Storage statistics
"""

import asyncio
import sys
from pathlib import Path
from services.cleanup import cleanup_generation_assets, get_storage_stats
from services.storage import storage_manager
from services.database import init_db, async_session, Video
from sqlalchemy import select
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_storage_stats():
    """Test 1: Display current storage statistics"""
    print("\n" + "="*60)
    print("TEST 1: Storage Statistics")
    print("="*60)

    stats = get_storage_stats()

    print(f"\n📊 Current Storage Usage:")
    for category, info in stats.items():
        if category == 'total':
            continue
        size_mb = info['size_mb']
        count = info['files']
        print(f"  {category:12s}: {count:3d} files, {size_mb:8.2f} MB")

    if 'total' in stats:
        total_info = stats['total']
        print(f"  {'TOTAL':12s}: {total_info['files']:3d} files, {total_info['size_mb']:8.2f} MB")

    return stats


async def test_cleanup():
    """Test 2: Test cleanup functionality"""
    print("\n" + "="*60)
    print("TEST 2: Cleanup Temporary Assets")
    print("="*60)

    # List all video titles
    output_dir = Path("assets/temp/outputs")
    videos = list(output_dir.glob("*.mp4"))

    if not videos:
        print("\n⚠️  No videos found in outputs directory")
        return

    print(f"\n📹 Found {len(videos)} video(s) in outputs:")
    for i, video in enumerate(videos, 1):
        size_mb = video.stat().st_size / (1024 * 1024)
        print(f"  {i}. {video.stem} ({size_mb:.2f} MB)")

    # Ask user which video to test cleanup with
    print("\nℹ️  Cleanup will remove temporary audio, images, and raw video files")
    print("   (The final output video will NOT be deleted)")

    choice = input("\nEnter video number to test cleanup (or 'skip' to skip): ").strip()

    if choice.lower() == 'skip':
        print("⏭️  Skipping cleanup test")
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(videos):
            video_path = videos[idx]
            video_title = video_path.stem

            print(f"\n🧹 Testing cleanup for: {video_title}")

            # Run cleanup
            cleaned_count, cleaned_size = cleanup_generation_assets(video_title)
            cleaned_mb = cleaned_size / (1024 * 1024)

            print(f"✅ Cleaned up {cleaned_count} files ({cleaned_mb:.2f} MB)")
        else:
            print("❌ Invalid choice")
    except ValueError:
        print("❌ Invalid input")


async def test_cloud_upload():
    """Test 3: Test cloud storage upload"""
    print("\n" + "="*60)
    print("TEST 3: Cloud Storage Upload")
    print("="*60)

    # Check if cloud storage is enabled
    if not storage_manager.is_enabled():
        print("\n⚠️  Cloud storage is NOT enabled")
        print("\nTo enable Cloudflare R2:")
        print("  1. Copy .env.example to .env")
        print("  2. Set R2_ENABLED=true")
        print("  3. Add your R2 credentials:")
        print("     - R2_ENDPOINT_URL")
        print("     - R2_ACCESS_KEY_ID")
        print("     - R2_SECRET_ACCESS_KEY")
        print("     - R2_BUCKET_NAME")
        print("     - R2_PUBLIC_URL")
        print("\nSee STORAGE_SETUP.md for detailed instructions")
        return

    print("\n✅ Cloud storage is ENABLED")

    # Initialize database
    await init_db()

    # List available videos
    output_dir = Path("assets/temp/outputs")
    videos = list(output_dir.glob("*.mp4"))

    if not videos:
        print("\n⚠️  No videos found in outputs directory")
        return

    print(f"\n📹 Found {len(videos)} video(s):")
    for i, video in enumerate(videos, 1):
        size_mb = video.stat().st_size / (1024 * 1024)
        print(f"  {i}. {video.stem} ({size_mb:.2f} MB)")

    choice = input("\nEnter video number to upload (or 'all' for all, 'skip' to skip): ").strip()

    if choice.lower() == 'skip':
        print("⏭️  Skipping upload test")
        return

    # Determine which videos to upload
    videos_to_upload = []
    if choice.lower() == 'all':
        videos_to_upload = videos
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(videos):
                videos_to_upload = [videos[idx]]
            else:
                print("❌ Invalid choice")
                return
        except ValueError:
            print("❌ Invalid input")
            return

    # Upload videos
    for video_path in videos_to_upload:
        video_title = video_path.stem
        size_mb = video_path.stat().st_size / (1024 * 1024)

        print(f"\n☁️  Uploading: {video_title} ({size_mb:.2f} MB)")

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
            cloud_url = await storage_manager.upload_video(str(video_path), video.id)

            if cloud_url:
                print(f"   ✅ Upload successful!")
                print(f"   🔗 Public URL: {cloud_url}")

                # Update database with cloud URL
                video.file_path = cloud_url
                await session.commit()
                print(f"   💾 Database updated with cloud URL")
            else:
                print(f"   ❌ Upload failed")


async def main():
    """Run all tests"""
    print("\n" + "🧪 " + "="*58)
    print("   ReelCraft Storage & Cleanup Test Suite")
    print("="*60)

    try:
        # Test 1: Storage stats
        await test_storage_stats()

        # Test 2: Cleanup
        await test_cleanup()

        # Test 3: Cloud upload
        await test_cloud_upload()

        # Final stats
        print("\n" + "="*60)
        print("Final Storage Statistics")
        print("="*60)
        await test_storage_stats()

        print("\n✅ All tests completed!")
        print("\nℹ️  For production use:")
        print("  - Cleanup runs automatically after each video generation")
        print("  - Cloud upload runs automatically if R2_ENABLED=true")
        print("  - See STORAGE_SETUP.md for configuration details")

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
