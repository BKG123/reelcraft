import json
import os
import random
from turtle import title
from utils.assets import search_and_download_asset, ASSET_FOLDER
from utils.ai import generate_audio_file, gemini_llm_call
from utils.fire_crawl import get_webpage_markdown
from config.prompts import SCRIPT_GENERATOR_SYSTEM


def create_srt(data):
    srt_content = ""
    counter = 1

    for i in range(len(data)):
        item = data[i]
        start_time = item["start_time"]
        end_time = item["end_time"]
        content = item["content"]

        # Adjust end time to be one millisecond more than the actual end time
        end_time_parts = end_time.split(",")
        adjusted_end_time = (
            f"{end_time_parts[0]},{str(int(end_time_parts[1]) + 1).zfill(3)}"
        )

        srt_content += f"{counter}\n"
        srt_content += f"{start_time} --> {adjusted_end_time}\n"
        srt_content += f"{content}\n\n"

        counter += 1

    return srt_content


def cleanup_assets(asset_details: dict):
    visual_assets = asset_details.get("visual_assets", [])
    audio_assets = asset_details.get("audio_assets", {})

    for asset in visual_assets:
        try:
            os.remove(asset.get("path"))
        except OSError as e:
            print(f"Error deleting file {asset.get('path')}: {e.strerror}")

    for key in audio_assets:
        try:
            os.remove(audio_assets[key].get("path"))
        except OSError as e:
            print(f"Error deleting file {audio_assets[key].get('path')}: {e.strerror}")

    subtitles_path = asset_details.get("subtitles")
    if subtitles_path:
        try:
            os.remove(subtitles_path)
        except OSError as e:
            print(f"Error deleting subtitles file {subtitles_path}: {e.strerror}")


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

    subtitles = create_srt(data)

    subtitle_file_path = ASSET_FOLDER / "subtitles.srt"
    with open(subtitle_file_path, "w") as f:
        f.write(subtitles)

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

    asset_details["subtitles"] = str(subtitle_file_path)
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
