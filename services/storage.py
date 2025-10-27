"""Cloud storage integration for video files."""

import os
from pathlib import Path
from typing import Optional
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Storage configuration
STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "local")  # local, r2, s3, gcs
R2_ENABLED = os.getenv("R2_ENABLED", "false").lower() == "true"

# Cloudflare R2 Configuration
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "reelcraft-videos")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL")  # e.g., https://videos.yourdomain.com


class StorageManager:
    """Manages video file storage (local or cloud)."""

    def __init__(self):
        self.provider = STORAGE_PROVIDER
        self.r2_client = None

        if R2_ENABLED and self._r2_configured():
            self._init_r2()

    def _r2_configured(self) -> bool:
        """Check if R2 credentials are configured."""
        return all([R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY])

    def _init_r2(self):
        """Initialize Cloudflare R2 client (S3-compatible)."""
        try:
            import boto3
            from botocore.config import Config

            self.r2_client = boto3.client(
                "s3",
                endpoint_url=R2_ENDPOINT_URL,
                aws_access_key_id=R2_ACCESS_KEY_ID,
                aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
            )
            logger.info("Cloudflare R2 storage initialized")
        except ImportError:
            logger.warning("boto3 not installed. Run: uv add boto3")
            self.r2_client = None
        except Exception as e:
            logger.error(f"Failed to initialize R2 client: {e}")
            self.r2_client = None

    def is_enabled(self) -> bool:
        """Check if cloud storage is enabled and configured."""
        return R2_ENABLED and self.r2_client is not None

    async def upload_video(self, local_path: str, video_id: int) -> Optional[str]:
        """
        Upload video to cloud storage.

        Args:
            local_path: Path to local video file
            video_id: Database video ID

        Returns:
            Public URL of uploaded video, or None if upload failed/disabled
        """
        if not R2_ENABLED or not self.r2_client:
            logger.info("Cloud storage disabled, keeping video locally")
            return None

        try:
            file_path = Path(local_path)
            if not file_path.exists():
                logger.error(f"Video file not found: {local_path}")
                return None

            # Generate object key (path in bucket)
            object_key = f"videos/{video_id}/{file_path.name}"

            # Upload to R2
            logger.info(f"Uploading {file_path.name} to R2...")
            with open(local_path, "rb") as f:
                self.r2_client.upload_fileobj(
                    f,
                    R2_BUCKET_NAME,
                    object_key,
                    ExtraArgs={
                        "ContentType": "video/mp4",
                        "CacheControl": "public, max-age=31536000",  # 1 year
                    },
                )

            # Generate public URL
            if R2_PUBLIC_URL:
                public_url = f"{R2_PUBLIC_URL}/{object_key}"
            else:
                # Use default R2.dev URL
                public_url = f"{R2_ENDPOINT_URL.replace('https://', 'https://pub-')}/{R2_BUCKET_NAME}/{object_key}"

            logger.info(f"Video uploaded successfully: {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"Error uploading to R2: {e}")
            return None

    async def delete_video(self, object_key: str) -> bool:
        """
        Delete video from cloud storage.

        Args:
            object_key: Object key in bucket (e.g., "videos/5/video.mp4")

        Returns:
            True if deleted successfully
        """
        if not R2_ENABLED or not self.r2_client:
            return False

        try:
            self.r2_client.delete_object(Bucket=R2_BUCKET_NAME, Key=object_key)
            logger.info(f"Deleted video from R2: {object_key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting from R2: {e}")
            return False

    def get_video_url(self, video_id: int, filename: str) -> str:
        """
        Get public URL for a video.

        Args:
            video_id: Database video ID
            filename: Video filename

        Returns:
            Public URL
        """
        if R2_ENABLED and R2_PUBLIC_URL:
            object_key = f"videos/{video_id}/{filename}"
            return f"{R2_PUBLIC_URL}/{object_key}"

        # Fallback to local serving
        return f"/api/videos/{video_id}/file"


# Global storage manager instance
storage_manager = StorageManager()
