"""Asset cleanup utilities for managing temporary files."""

import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import logging
from config.directories import AUDIO_DIR, VIDEO_DIR, IMAGE_DIR, OUTPUT_FOLDER

logger = logging.getLogger(__name__)


def cleanup_generation_assets(video_title: str):
    """
    Clean up temporary assets (audio, images, videos) used for a specific video generation.
    Keeps the final output video but removes intermediate files.

    Args:
        video_title: Title of the video (used to match filenames)
    """
    cleaned_count = 0
    cleaned_size = 0

    # Sanitize title for filename matching
    sanitized_title = video_title.lower().replace(" ", "_")

    # Directories to clean
    temp_dirs = [
        (AUDIO_DIR, "audio"),
        (IMAGE_DIR, "images"),
        (VIDEO_DIR, "videos")
    ]

    for dir_path, dir_name in temp_dirs:
        if not os.path.exists(dir_path):
            continue

        for file in os.listdir(dir_path):
            # Match files that start with the video title
            if file.lower().startswith(sanitized_title):
                file_path = os.path.join(dir_path, file)
                try:
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    cleaned_count += 1
                    cleaned_size += file_size
                    logger.info(f"Cleaned up {dir_name}: {file}")
                except Exception as e:
                    logger.error(f"Error cleaning {file_path}: {e}")

    if cleaned_count > 0:
        size_mb = cleaned_size / (1024 * 1024)
        logger.info(f"Cleaned up {cleaned_count} files ({size_mb:.2f} MB) for '{video_title}'")

    return cleaned_count, cleaned_size


def cleanup_old_assets(days: int = 7):
    """
    Clean up all temporary assets older than specified days.
    Does NOT delete final output videos.

    Args:
        days: Delete files older than this many days (default: 7)
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    cleaned_count = 0
    cleaned_size = 0

    # Directories to clean (not including outputs)
    temp_dirs = [
        (AUDIO_DIR, "audio"),
        (IMAGE_DIR, "images"),
        (VIDEO_DIR, "videos")
    ]

    for dir_path, dir_name in temp_dirs:
        if not os.path.exists(dir_path):
            continue

        for file in os.listdir(dir_path):
            file_path = os.path.join(dir_path, file)

            try:
                # Check file modification time
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                if file_mtime < cutoff_date:
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    cleaned_count += 1
                    cleaned_size += file_size
                    logger.debug(f"Cleaned old {dir_name}: {file}")

            except Exception as e:
                logger.error(f"Error cleaning {file_path}: {e}")

    if cleaned_count > 0:
        size_mb = cleaned_size / (1024 * 1024)
        logger.info(f"Cleaned {cleaned_count} old files ({size_mb:.2f} MB) older than {days} days")

    return cleaned_count, cleaned_size


def cleanup_failed_generation(video_title: str):
    """
    Clean up ALL assets (including partial output) for a failed generation.

    Args:
        video_title: Title of the failed video generation
    """
    cleaned_count = 0
    cleaned_size = 0

    sanitized_title = video_title.lower().replace(" ", "_")

    # Clean from ALL directories including outputs
    all_dirs = [
        (AUDIO_DIR, "audio"),
        (IMAGE_DIR, "images"),
        (VIDEO_DIR, "videos"),
        (OUTPUT_FOLDER, "outputs")
    ]

    for dir_path, dir_name in all_dirs:
        if not os.path.exists(dir_path):
            continue

        for file in os.listdir(dir_path):
            if file.lower().startswith(sanitized_title) or sanitized_title in file.lower():
                file_path = os.path.join(dir_path, file)
                try:
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    cleaned_count += 1
                    cleaned_size += file_size
                    logger.info(f"Cleaned failed generation {dir_name}: {file}")
                except Exception as e:
                    logger.error(f"Error cleaning {file_path}: {e}")

    if cleaned_count > 0:
        size_mb = cleaned_size / (1024 * 1024)
        logger.info(f"Cleaned {cleaned_count} files ({size_mb:.2f} MB) from failed generation")

    return cleaned_count, cleaned_size


def get_storage_stats():
    """
    Get storage statistics for all asset directories.

    Returns:
        dict: Storage stats by directory
    """
    stats = {}

    dirs = {
        "audio": AUDIO_DIR,
        "images": IMAGE_DIR,
        "videos": VIDEO_DIR,
        "outputs": OUTPUT_FOLDER
    }

    total_size = 0
    total_files = 0

    for name, dir_path in dirs.items():
        if not os.path.exists(dir_path):
            stats[name] = {"files": 0, "size_mb": 0}
            continue

        file_count = len(os.listdir(dir_path))
        dir_size = sum(
            os.path.getsize(os.path.join(dir_path, f))
            for f in os.listdir(dir_path)
            if os.path.isfile(os.path.join(dir_path, f))
        )

        size_mb = dir_size / (1024 * 1024)
        stats[name] = {
            "files": file_count,
            "size_mb": round(size_mb, 2)
        }

        total_files += file_count
        total_size += dir_size

    stats["total"] = {
        "files": total_files,
        "size_mb": round(total_size / (1024 * 1024), 2)
    }

    return stats
