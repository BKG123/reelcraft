import json
import os
import asyncio
from typing import Callable, Optional
from pathlib import Path
from pydub import AudioSegment
from utils.assets import search_and_download_asset
from utils.ai import generate_audio_file, gemini_llm_call
from utils.fire_crawl import get_webpage_markdown
from utils.video_editing import script_to_asset_details, video_editing_pipeline
from config.prompts import SCRIPT_GENERATOR_SYSTEM
from services.storage import storage_manager
from services.database import async_session, Video
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)


async def pipeline(url: str, progress_callback: Optional[Callable] = None):
    """
    Main video generation pipeline with progress tracking.

    Args:
        url: Article URL to process
        progress_callback: Optional async callback function(progress: int, message: str)

    Returns:
        Dictionary with output_video path and script
    """
    async def update_progress(progress: int, message: str):
        """Helper to update progress if callback provided."""
        if progress_callback:
            await progress_callback(progress, message)

    # Step 1: Get content from article
    await update_progress(5, "Extracting article content...")
    article_content = get_webpage_markdown(url)
    await update_progress(10, "Article content extracted")

    # Step 2: Generate script
    await update_progress(15, "Generating video script...")
    user_prompt = f"""
ARTICLE CONTENT:
\"\"\"
{article_content}
\"\"\"
"""
    script = await gemini_llm_call(
        system_prompt=SCRIPT_GENERATOR_SYSTEM,
        user_prompt=user_prompt,
        json_format=True,
        model_name="gemini-2.5-flash",
    )

    if isinstance(script, str):
        script = json.loads(script)

    reel_title = script["title"]
    scenes = script["scenes"]
    await update_progress(25, f"Script generated with {len(scenes)} scenes")

    # Step 3: Generate audio files
    await update_progress(30, "Generating voice-over audio...")
    audio_tasks = [
        generate_audio_file(scene["script"], f"{reel_title}_{scene['scene_number']}")
        for scene in scenes
    ]

    audio_file_paths = await asyncio.gather(*audio_tasks)
    await update_progress(50, "Audio generation completed")

    # Assign the generated audio file paths back to scenes
    for scene, audio_file_path in zip(scenes, audio_file_paths):
        scene["audio_file_path"] = audio_file_path
        # Get audio duration in seconds
        audio = AudioSegment.from_wav(audio_file_path)
        scene["duration"] = len(audio) / 1000.0  # Convert milliseconds to seconds

    # Step 4: Download assets
    await update_progress(55, "Downloading visual assets...")
    script = await generate_assets(script, progress_callback=update_progress)
    await update_progress(75, "Assets downloaded successfully")

    # Step 5: Transform script to asset_details and create final video
    await update_progress(80, "Composing video...")
    asset_details = await script_to_asset_details(script)

    await update_progress(85, "Editing video with FFmpeg...")
    await video_editing_pipeline(asset_details)

    await update_progress(90, "Video editing completed")

    output_video = asset_details['output_video']
    output_video_path = Path(output_video)

    # Step 6: Upload to cloud storage (if enabled)
    cloud_url = None
    if storage_manager.is_enabled():
        await update_progress(92, "Uploading video to cloud storage...")

        # Create video entry in database
        async with async_session() as session:
            # Check if video already exists
            result = await session.execute(
                select(Video).where(Video.title == reel_title)
            )
            video = result.scalar_one_or_none()

            if not video:
                # Create new video entry
                size_mb = output_video_path.stat().st_size / (1024 * 1024)
                video = Video(
                    title=reel_title,
                    source_url=url,
                    file_path=str(output_video),
                    size_mb=size_mb,
                    script_json=json.dumps(script)
                )
                session.add(video)
                await session.commit()
                await session.refresh(video)
                logger.info(f"Created database entry for video: {reel_title} (ID: {video.id})")

            # Upload to cloud storage
            cloud_url = await storage_manager.upload_video(str(output_video), video.id)

            if cloud_url:
                # Update database with cloud URL
                video.file_path = cloud_url
                await session.commit()
                logger.info(f"Video uploaded to cloud: {cloud_url}")
                await update_progress(97, "Video uploaded to cloud storage")
            else:
                logger.info("Cloud storage upload skipped or failed, using local path")
                await update_progress(97, "Using local video storage")
    else:
        logger.info("Cloud storage not enabled, keeping video locally")
        await update_progress(97, "Video saved locally")

    await update_progress(100, f"Video created successfully: {output_video}")

    return {
        "output_video": output_video,
        "cloud_url": cloud_url,
        "script": script,
        "title": reel_title
    }


async def generate_assets(script: dict, progress_callback: Optional[Callable] = None):
    """
    Generate and download assets for all scenes.

    Args:
        script: Script dictionary with scenes
        progress_callback: Optional progress callback function

    Returns:
        Updated script with asset file paths
    """
    # Parse script if it's a string
    if isinstance(script, str):
        script = json.loads(script)

    reel_title = script["title"]
    scenes = script["scenes"]

    # Generate all assets in parallel
    asset_tasks = []
    for scene in scenes:
        asset_type = scene["asset_type"]
        asset_keywords = scene["asset_keywords"]
        scene_number = scene["scene_number"]

        # Pick the first keyword for simplicity
        keyword = asset_keywords[0] if asset_keywords else "generic"

        # Sanitize filename: lowercase and remove spaces (same as audio pipeline)
        file_name = f"{reel_title}_{scene_number}".lower().replace(" ", "_")

        # Determine the actual asset type to download
        # Handle cases like "image/video" by defaulting to video
        actual_asset_type = "video" if "video" in asset_type else "image"

        # Create async task for downloading asset
        asset_tasks.append(
            search_and_download_asset(
                keyword=keyword,
                asset_type=actual_asset_type,
                file_name=file_name,
                orientation="portrait",
            )
        )

    # Execute all downloads in parallel
    asset_file_paths = await asyncio.gather(*asset_tasks)

    # Assign the generated asset file paths back to scenes
    for scene, asset_file_path in zip(scenes, asset_file_paths):
        scene["asset_file_path"] = asset_file_path

    return script


if __name__ == "__main__":
    asyncio.run(pipeline("asd"))
