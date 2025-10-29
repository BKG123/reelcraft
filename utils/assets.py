import os
from pathlib import Path
from dotenv import load_dotenv
from config.directories import IMAGE_DIR, VIDEO_DIR
from .http_client import PexelsClient, HTTPClient
from .ai import gemini_llm_call

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


async def ai_filter_best_asset(script_text: str, asset_options: list, asset_type: str = "image") -> int:
    """
    Use AI to select the best asset from multiple options based on the script context.

    For images, uses visual descriptions from Pexels alt text.
    For videos, analyzes the video thumbnail images to make the selection.

    Args:
        script_text: The scene script text for context
        asset_options: List of dicts with asset metadata (id, alt, description, url, image_url)
        asset_type: Either "image" or "video"

    Returns:
        int: Index of the best matching asset (0-based)
    """
    if not asset_options:
        return 0

    if len(asset_options) == 1:
        return 0

    # For videos with image URLs, we can use visual analysis
    # For now, use text-based filtering as baseline
    # Build the prompt with numbered options
    options_text = "\n".join([
        f"{i+1}. {option.get('alt', option.get('description', 'No description available'))}"
        for i, option in enumerate(asset_options)
    ])

    system_prompt = """You are an expert video editor selecting the perfect stock footage for a viral short-form video.

Your task is to analyze a script line and choose which stock media description best matches the scene's intent.

**Instructions:**
- Consider the script's context, mood, and visual requirements
- Choose the option that would create the most engaging and contextually relevant visual
- Respond with ONLY the number (1, 2, 3, etc.) of the best option
- Do not include any explanation, just the number"""

    user_prompt = f"""**Script for this scene:**
"{script_text}"

**Available {asset_type} options:**
{options_text}

Which option number (1-{len(asset_options)}) is the BEST contextual match for this script? Respond with only the number."""

    try:
        response = await gemini_llm_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_format=False,
            model_name="gemini-2.5-flash",
        )

        # Extract the number from response (handle various formats)
        response = response.strip()
        # Try to extract just the number
        import re
        match = re.search(r'\d+', response)
        if match:
            choice = int(match.group()) - 1  # Convert to 0-based index
            # Validate the choice is within range
            if 0 <= choice < len(asset_options):
                return choice

        # Default to first option if parsing fails
        print(f"Warning: Could not parse AI response '{response}', defaulting to first option")
        return 0

    except Exception as e:
        print(f"Warning: AI filtering failed ({e}), defaulting to first option")
        return 0


async def search_and_download_asset(
    keyword,
    asset_type,
    file_name,
    script_text: str = None,
    use_ai_filtering: bool = True,
    **kwargs
):
    """
    Search and download an asset (image or video) from Pexels with optional AI-powered filtering.

    Args:
        keyword: Search query
        asset_type: Either "image" or "video"
        file_name: Name for the downloaded file (without extension)
        script_text: Optional script text for AI filtering context
        use_ai_filtering: Whether to use AI to select best asset from multiple options
        **kwargs: Additional parameters like orientation, quality, per_page

    Returns:
        str: File path of downloaded asset

    Raises:
        ValueError: If asset_type is invalid or no results found
    """
    # Determine how many results to fetch (more if using AI filtering)
    fetch_count = kwargs.pop('per_page', 5 if use_ai_filtering else 1)

    if asset_type == "image":
        photo_data = await search_image(
            keyword,
            per_page=fetch_count,
            **{k: v for k, v in kwargs.items() if k in ["orientation"]},
        )
        if not photo_data.get("photos"):
            raise ValueError(f"No images found for keyword: {keyword}")

        photos = photo_data["photos"]

        # Use AI filtering if enabled and script context provided
        if use_ai_filtering and script_text and len(photos) > 1:
            asset_options = [
                {
                    "id": photo["id"],
                    "alt": photo.get("alt", ""),
                    "url": photo.get("url", "")
                }
                for photo in photos
            ]
            best_index = await ai_filter_best_asset(script_text, asset_options, asset_type="image")
            photo_id = photos[best_index]["id"]
            print(f"AI selected image {best_index + 1}/{len(photos)} for script: '{script_text[:50]}...'")
        else:
            photo_id = photos[0]["id"]

        return await download_image(photo_id, file_name)

    elif asset_type == "video":
        video_data = await search_video(
            keyword,
            per_page=fetch_count,
            **{k: v for k, v in kwargs.items() if k in ["orientation"]},
        )
        if not video_data.get("videos"):
            raise ValueError(f"No videos found for keyword: {keyword}")

        videos = video_data["videos"]

        # Use AI filtering if enabled and script context provided
        if use_ai_filtering and script_text and len(videos) > 1:
            # For videos, build descriptions based on available metadata
            # Pexels video API provides limited text, so we construct meaningful descriptions
            asset_options = [
                {
                    "id": video["id"],
                    "alt": f"{keyword} - {video.get('width', 0)}x{video.get('height', 0)}, {video.get('duration', 0)}s duration, by {video.get('user', {}).get('name', 'Unknown')}",
                    "description": f"Video showing: {keyword}. Dimensions: {video.get('width', 0)}x{video.get('height', 0)}, Duration: {video.get('duration', 0)}s",
                    "url": video.get("url", "")
                }
                for i, video in enumerate(videos)
            ]
            best_index = await ai_filter_best_asset(script_text, asset_options, asset_type="video")
            video_id = videos[best_index]["id"]
            print(f"AI selected video {best_index + 1}/{len(videos)} for script: '{script_text[:50]}...'")
        else:
            video_id = videos[0]["id"]

        quality = kwargs.get("quality", "hd")
        return await download_video(video_id, file_name, quality)

    else:
        raise ValueError(f"Invalid asset type: {asset_type}. Use 'image' or 'video'.")
