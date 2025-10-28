import json
import os
import asyncio
from typing import Callable, Optional
from pydub import AudioSegment
from utils.assets import search_and_download_asset
from utils.ai import generate_audio_file, gemini_llm_call
from utils.fire_crawl import get_webpage_markdown
from utils.video_editing import script_to_asset_details, video_editing_pipeline
from config.prompts import SCRIPT_GENERATOR_SYSTEM


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

    # Note: Database entry and cloud upload are handled by api.py
    # This keeps the pipeline focused on video generation only
    await update_progress(95, "Video generation complete")
    await update_progress(100, f"Video created successfully: {output_video}")

    return {
        "output_video": output_video,
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
        scene_type = scene.get("scene_type", "media")  # Default to media if not specified
        scene_number = scene["scene_number"]

        # Handle text-only scenes
        if scene_type == "text":
            # Text scenes don't need asset downloads
            scene["asset_file_path"] = None
            scene["asset_type"] = "text"
            continue

        # Regular media scenes
        asset_type = scene.get("asset_type", "video")
        asset_keywords = scene.get("asset_keywords", [])
        script_text = scene.get("script", "")

        # Pick the first keyword for simplicity
        keyword = asset_keywords[0] if asset_keywords else "generic"

        # Sanitize filename: lowercase and remove spaces (same as audio pipeline)
        file_name = f"{reel_title}_{scene_number}".lower().replace(" ", "_")

        # Determine the actual asset type to download
        # Handle cases like "image/video" by defaulting to video
        actual_asset_type = "video" if "video" in asset_type else "image"

        # Create async task for downloading asset with AI filtering
        asset_tasks.append(
            (scene_number, search_and_download_asset(
                keyword=keyword,
                asset_type=actual_asset_type,
                file_name=file_name,
                script_text=script_text,  # Pass script for AI filtering
                use_ai_filtering=True,    # Enable AI filtering
                orientation="portrait",
            ))
        )

    # Execute all downloads in parallel
    if asset_tasks:
        results = await asyncio.gather(*[task for _, task in asset_tasks])

        # Assign the generated asset file paths back to scenes
        for (scene_number, _), asset_file_path in zip(asset_tasks, results):
            for scene in scenes:
                if scene["scene_number"] == scene_number:
                    scene["asset_file_path"] = asset_file_path
                    break

    return script


if __name__ == "__main__":
    asyncio.run(pipeline("asd"))
