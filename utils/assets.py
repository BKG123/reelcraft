import os
from pathlib import Path
from dotenv import load_dotenv
from config.directories import IMAGE_DIR, VIDEO_DIR
from .http_client import PexelsClient, HTTPClient

load_dotenv()

# Configuration
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")


# Initialize Pexels client
pexels_client = PexelsClient(api_key=PEXELS_API_KEY)


async def search_image(keyword, orientation="portrait", per_page=1):
    """Search for images on Pexels."""
    return await pexels_client.search_photos(
        query=keyword, orientation=orientation, per_page=per_page
    )


async def download_image(photo_id, file_name):
    """Download an image by photo ID."""
    photo_data = await pexels_client.get_photo(photo_id)
    img_url = photo_data["src"]["original"]

    # Ensure IMAGE_DIR exists
    image_dir = Path(IMAGE_DIR)
    image_dir.mkdir(parents=True, exist_ok=True)

    file_path = image_dir / f"{file_name}.jpg"

    # Use generic HTTP client for downloading the actual image file
    http_client = HTTPClient()
    await http_client.download_file(img_url, file_path)

    print(f"Image downloaded successfully: {file_path}")
    return str(file_path)


async def search_video(keyword, orientation="portrait", per_page=1):
    """Search for videos on Pexels."""
    return await pexels_client.search_videos(
        query=keyword, orientation=orientation, per_page=per_page
    )


async def download_video(video_id, file_name, quality="hd"):
    """Download a video by video ID with specified quality (hd, sd)."""
    video_data = await pexels_client.get_video(video_id)

    # Find video link with requested quality
    video_link = next(
        (vf["link"] for vf in video_data["video_files"] if vf["quality"] == quality),
        None,
    )

    # If requested quality not found, use first available video file
    if not video_link and video_data["video_files"]:
        video_link = video_data["video_files"][0]["link"]
        print(
            f"Warning: {quality.upper()} quality not found, using first available video"
        )

    if not video_link:
        raise ValueError(
            f"No video links found. "
            f"Available qualities: {[vf['quality'] for vf in video_data['video_files']]}"
        )

    # Ensure VIDEO_DIR exists
    video_dir = Path(VIDEO_DIR)
    video_dir.mkdir(parents=True, exist_ok=True)

    file_path = video_dir / f"{file_name}.mp4"

    # Use generic HTTP client for downloading the actual video file
    http_client = HTTPClient()
    await http_client.download_file(video_link, file_path)

    print(f"Video downloaded successfully: {file_path}")
    return str(file_path)


async def search_and_download_asset(keyword, asset_type, file_name, **kwargs):
    """
    Search and download an asset (image or video) from Pexels.

    Args:
        keyword: Search query
        asset_type: Either "image" or "video"
        file_name: Name for the downloaded file (without extension)
        **kwargs: Additional parameters like orientation, quality, per_page

    Returns:
        str: File path of downloaded asset

    Raises:
        ValueError: If asset_type is invalid or no results found
    """
    if asset_type == "image":
        photo_data = await search_image(
            keyword,
            **{k: v for k, v in kwargs.items() if k in ["orientation", "per_page"]},
        )
        if not photo_data.get("photos"):
            raise ValueError(f"No images found for keyword: {keyword}")
        photo_id = photo_data["photos"][0]["id"]
        return await download_image(photo_id, file_name)

    elif asset_type == "video":
        video_data = await search_video(
            keyword,
            **{k: v for k, v in kwargs.items() if k in ["orientation", "per_page"]},
        )
        if not video_data.get("videos"):
            raise ValueError(f"No videos found for keyword: {keyword}")
        video_id = video_data["videos"][0]["id"]
        quality = kwargs.get("quality", "hd")
        return await download_video(video_id, file_name, quality)

    else:
        raise ValueError(f"Invalid asset type: {asset_type}. Use 'image' or 'video'.")
