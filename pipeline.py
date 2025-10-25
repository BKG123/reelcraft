import json
import os
import random
import asyncio
from turtle import title
from pydub import AudioSegment
from utils.assets import search_and_download_asset, ASSET_FOLDER
from utils.ai import generate_audio_file, gemini_llm_call
from utils.fire_crawl import get_webpage_markdown
from config.prompts import SCRIPT_GENERATOR_SYSTEM


async def generate_assets(script_json: dict, content: str):
    # Assuming this data comes from open AI
    asset_details = {}
    data = script_json["data"]

    for i, item in enumerate(data, 1):
        asset_keywords = item["asset_keywords"]
        asset_type = item["asset_type"]

        print(f"Generating asset for item {i}...")
        print(f"asset type: {asset_type}")

        # Choose a random keyword from the list of asset keywords
        chosen_keyword = random.choice(asset_keywords)

        print(f"keyword: {chosen_keyword}")
        # Search for the asset
        asset = await search_and_download_asset(chosen_keyword, asset_type, file_name=i)

        # Update the item with the asset
        item["asset"] = asset
        item["chosen_keyword"] = chosen_keyword
        print()

    asset_details["visual_assets"] = [
        {
            "path": f"{item['asset']}",
            "type": item["asset_type"],
            "duration": item["duration"],
        }
        for item in data
    ]
    voiceover_file_path = generate_audio_file(content, file_name="voiceover")

    # TODO: not using this now
    # background_score_file_path = ASSET_FOLDER + "background_score.mp3"

    asset_details["audio_assets"] = {
        "voice_over": {"path": voiceover_file_path},
        # "background_score": {"path": background_score_file_path},
    }

    return asset_details


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

    # # Generate all audio files in parallel with rate limiting
    # audio_tasks = [
    #     generate_audio_file(scene["script"], f"{reel_title}_{scene['scene_number']}")
    #     for scene in scenes
    # ]

    # audio_file_paths = await asyncio.gather(*audio_tasks)

    # List already-made audio assets for dry run
    audio_file_paths = sorted(
        [
            os.path.join("assets/temp/audio", f)
            for f in os.listdir("assets/temp/audio")
            if f.endswith(".wav")
        ]
    )

    # Assign the generated audio file paths back to scenes
    for scene, audio_file_path in zip(scenes, audio_file_paths):
        scene["audio_file_path"] = audio_file_path
        # Get audio duration in seconds
        audio = AudioSegment.from_wav(audio_file_path)
        scene["duration"] = len(audio) / 1000.0  # Convert milliseconds to seconds

    print(script)


if __name__ == "__main__":
    asyncio.run(pipeline("asd"))
