"""Clean all temporary assets (audio, images, videos) while keeping output videos."""

import sys
from pathlib import Path
from services.cleanup import get_storage_stats
from config.directories import AUDIO_DIR, VIDEO_DIR, IMAGE_DIR
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_all_temp_assets():
    """Clean all temporary assets from audio, images, and videos directories."""

    # Show before stats
    print("\n" + "="*60)
    print("BEFORE CLEANUP - Storage Statistics")
    print("="*60)
    before_stats = get_storage_stats()

    for category, info in before_stats.items():
        if category == 'total':
            continue
        print(f"  {category:12s}: {info['files']:3d} files, {info['size_mb']:8.2f} MB")

    if 'total' in before_stats:
        total_info = before_stats['total']
        print(f"  {'TOTAL':12s}: {total_info['files']:3d} files, {total_info['size_mb']:8.2f} MB")

    # Directories to clean
    temp_dirs = [
        (AUDIO_DIR, "audio"),
        (IMAGE_DIR, "images"),
        (VIDEO_DIR, "videos")
    ]

    total_cleaned = 0
    total_size = 0

    print("\n" + "="*60)
    print("CLEANING TEMPORARY ASSETS")
    print("="*60)

    for dir_path, dir_name in temp_dirs:
        if not Path(dir_path).exists():
            print(f"\n{dir_name}: Directory does not exist, skipping...")
            continue

        files = list(Path(dir_path).glob("*"))
        if not files:
            print(f"\n{dir_name}: No files to clean")
            continue

        print(f"\n{dir_name}: Cleaning {len(files)} files...")
        cleaned_count = 0
        cleaned_size = 0

        for file_path in files:
            if file_path.is_file():
                try:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    cleaned_count += 1
                    cleaned_size += file_size
                except Exception as e:
                    logger.error(f"Error deleting {file_path}: {e}")

        size_mb = cleaned_size / (1024 * 1024)
        print(f"  Cleaned {cleaned_count} files ({size_mb:.2f} MB)")

        total_cleaned += cleaned_count
        total_size += cleaned_size

    # Show after stats
    print("\n" + "="*60)
    print("AFTER CLEANUP - Storage Statistics")
    print("="*60)
    after_stats = get_storage_stats()

    for category, info in after_stats.items():
        if category == 'total':
            continue
        print(f"  {category:12s}: {info['files']:3d} files, {info['size_mb']:8.2f} MB")

    if 'total' in after_stats:
        total_info = after_stats['total']
        print(f"  {'TOTAL':12s}: {total_info['files']:3d} files, {total_info['size_mb']:8.2f} MB")

    # Summary
    total_mb = total_size / (1024 * 1024)
    print("\n" + "="*60)
    print("CLEANUP SUMMARY")
    print("="*60)
    print(f"  Total files cleaned: {total_cleaned}")
    print(f"  Total space freed:   {total_mb:.2f} MB")
    print(f"  Output videos kept:  {after_stats['outputs']['files']} files ({after_stats['outputs']['size_mb']:.2f} MB)")
    print("="*60)


if __name__ == "__main__":
    try:
        cleanup_all_temp_assets()
        print("\nCleanup completed successfully!")
    except KeyboardInterrupt:
        print("\n\nCleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)
