import json
import os
import asyncio
from pydub import AudioSegment
from utils.assets import search_and_download_asset
from utils.ai import generate_audio_file, gemini_llm_call
from utils.fire_crawl import get_webpage_markdown
from utils.video_editing import script_to_asset_details, video_editing_pipeline
from config.prompts import SCRIPT_GENERATOR_SYSTEM


async def pipeline(url: str):
    # step1: Get content from article
    article_content = get_webpage_markdown(url)

    # step 2: Generate script
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

    # Generate all audio files in parallel with rate limiting
    audio_tasks = [
        generate_audio_file(scene["script"], f"{reel_title}_{scene['scene_number']}")
        for scene in scenes
    ]

    audio_file_paths = await asyncio.gather(*audio_tasks)

    # Assign the generated audio file paths back to scenes
    for scene, audio_file_path in zip(scenes, audio_file_paths):
        scene["audio_file_path"] = audio_file_path
        # Get audio duration in seconds
        audio = AudioSegment.from_wav(audio_file_path)
        scene["duration"] = len(audio) / 1000.0  # Convert milliseconds to seconds

    audio_file_paths = sorted(
        [
            os.path.join("assets/temp/audio", f)
            for f in os.listdir("assets/temp/audio")
            if f.endswith(".wav")
        ]
    )

    script = await generate_assets(script)
    print(json.dumps(script, indent=2))

    # Step 3: Transform script to asset_details and create final video
    asset_details = await script_to_asset_details(script)
    print("\n=== Starting Video Editing Pipeline ===")
    await video_editing_pipeline(asset_details)
    print(f"\n=== Video Created: {asset_details['output_video']} ===")


async def generate_assets(script: dict):
    # Parse script if it's a string
    if isinstance(script, str):
        script = json.loads(script)

    reel_title = script["title"]
    scenes = script["scenes"]

    # # Generate all assets in parallel
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
