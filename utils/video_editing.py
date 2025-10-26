import ffmpeg
import os
from pydub import AudioSegment


async def combine_audio_files(audio_file_paths: list, output_filename: str) -> str:
    """
    Combine multiple audio files into a single audio file sequentially.

    Args:
        audio_file_paths: List of paths to audio files
        output_filename: Base name for the output file

    Returns:
        Path to the combined audio file
    """
    if not audio_file_paths:
        raise ValueError("No audio files provided to combine")

    # Create output directory if it doesn't exist
    output_dir = "assets/temp/audio"
    os.makedirs(output_dir, exist_ok=True)

    # Sanitize the output filename
    safe_filename = output_filename.lower().replace(" ", "_")
    output_path = os.path.join(output_dir, f"{safe_filename}_combined.wav")

    # Load and concatenate all audio files
    combined_audio = AudioSegment.empty()
    for audio_path in audio_file_paths:
        audio_segment = AudioSegment.from_wav(audio_path)
        combined_audio += audio_segment

    # Export the combined audio
    combined_audio.export(output_path, format="wav")

    return output_path


async def script_to_asset_details(script: dict, background_music_path: str = None) -> dict:
    """
    Transform script structure to video_editing_pipeline format.

    Args:
        script: Script dictionary with scenes
        background_music_path: Optional path to background music file

    Returns:
        Asset details dictionary ready for video_editing_pipeline
    """
    scenes = script.get("scenes", [])
    title = script.get("title", "untitled")

    # Extract visual assets and audio files from scenes
    visual_assets = []
    audio_file_paths = []

    for scene in scenes:
        # Add visual asset
        asset_file_path = scene.get("asset_file_path")

        # Determine actual type from file extension (more reliable than asset_type field)
        if asset_file_path:
            file_ext = os.path.splitext(asset_file_path)[1].lower()
            if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
                actual_type = "image"
            elif file_ext in ['.mp4', '.mov', '.avi', '.webm', '.mkv', '.flv']:
                actual_type = "video"
            else:
                # Fallback to asset_type from script
                asset_type = scene.get("asset_type", "video")
                if "image" in asset_type:
                    actual_type = "image"
                else:
                    actual_type = "video"  # default to video
        else:
            actual_type = "video"  # default

        visual_assets.append({
            "path": asset_file_path,
            "type": actual_type,
            "duration": scene.get("duration", 5.0)
        })

        # Collect audio file paths
        if scene.get("audio_file_path"):
            audio_file_paths.append(scene["audio_file_path"])

    # Combine all scene audio files into one
    combined_voiceover_path = await combine_audio_files(audio_file_paths, title)

    # Build asset_details structure
    asset_details = {
        "visual_assets": visual_assets,
        "audio_assets": {
            "voice_over": {
                "path": combined_voiceover_path
            }
        },
        "output_video": f"assets/outputs/{title.lower().replace(' ', '_')}.mp4"
    }

    # Add background music if provided
    if background_music_path and os.path.exists(background_music_path):
        asset_details["audio_assets"]["background_score"] = {
            "path": background_music_path
        }

    return asset_details


async def stitch_assets(visual_assets: list):
    ffmpeg_asset_objects = []
    total_video_duration = 0

    fps = 25
    asset_width = 720
    asset_height = 1280

    if not visual_assets:
        return ffmpeg_asset_objects, total_video_duration
    for asset in visual_assets:
        asset_path = asset.get("path")
        asset_type = asset.get("type")
        duration = asset.get("duration")
        total_video_duration += duration
        if asset_type == "image":
            # Applying stock zoom and pan filter for still images
            ffmpeg_asset_objects.append(
                (
                    ffmpeg.input(asset_path, loop=1, framerate=fps)
                    .filter(
                        "zoompan",
                        z="zoom+0.001",
                        s=f"{asset_width}x{asset_height}",
                        d=duration * fps,  # duration in frames
                    )
                    .filter("format", "yuv420p")
                    .trim(duration=duration)
                    .setpts("PTS-STARTPTS")
                )
            )
        elif asset_type == "video":
            ffmpeg_asset_objects.append(
                ffmpeg.input(asset_path)
                .trim(start=0, duration=duration)
                .setpts("PTS-STARTPTS")
                .filter("scale", asset_width, asset_height)
                .filter("fps", fps=fps)
                .filter("format", "yuv420p")
            )
        elif asset_type == "scroll_image":
            # Assuming dynamic scroll speed is calculated elsewhere and passed in the asset details
            scroll_speed = asset.get(
                "scroll_speed", 0.008
            )  # Default to 0.008 if not specified
            ffmpeg_asset_objects.append(
                ffmpeg.input(asset_path, loop=1, framerate=fps)
                .filter("scroll", vertical=scroll_speed)
                .filter(
                    "crop", str(asset_width), str(asset_height), "0", "0"
                )  # Crop width:720, height:1280, x:0, y:0
                .filter("format", "yuv420p")
                .trim(duration=duration)
            )
    concatenated_video_stream = ffmpeg.concat(*ffmpeg_asset_objects, v=1, a=0)
    return concatenated_video_stream, total_video_duration


async def adjust_audio_tempo(voiceover_audio_path: str, total_video_duration: int):
    # Calculate the duration of the voiceover audio
    # Use FFprobe to get the duration of the voiceover audio file
    voiceover_audio_info = ffmpeg.probe(voiceover_audio_path)
    voiceover_audio_duration = float(voiceover_audio_info["format"]["duration"])

    # Calculate the tempo adjustment needed for the voiceover audio
    if (
        voiceover_audio_duration != total_video_duration
        and voiceover_audio_duration > 0
    ):
        tempo_adjustment = voiceover_audio_duration / total_video_duration
        # Ensure the tempo adjustment is within the valid range
        tempo_adjustment = max(0.5, min(2.0, tempo_adjustment))
    else:
        tempo_adjustment = 1.0

    # Apply the tempo filter to the voiceover audio stream
    voiceover_audio_stream = ffmpeg.input(voiceover_audio_path)
    voiceover_audio_stream = voiceover_audio_stream.filter(
        "atempo", tempo=tempo_adjustment
    )

    return voiceover_audio_stream


async def mix_audio_streams(voiceover_audio_stream, background_score_stream):
    background_score_stream_with_volume = background_score_stream.filter(
        "volume", volume=0.2
    )
    voiceover_stream_with_volume = voiceover_audio_stream.filter("volume", volume=2)

    # Merge the audio streams together
    mixed_audio_stream = ffmpeg.filter(
        [voiceover_stream_with_volume, background_score_stream_with_volume],
        "amerge",
        inputs=2,
    )
    return mixed_audio_stream


async def video_editing_pipeline(asset_details: dict):
    try:
        visual_assets = asset_details.get("visual_assets", [])
        voiceover_audio_path = (
            asset_details.get("audio_assets", {}).get("voice_over", {}).get("path")
        )
        subtitles_path = asset_details.get("subtitles")
        background_score_path = (
            asset_details.get("audio_assets", {})
            .get("background_score", {})
            .get("path")
        )
        output_video_path = asset_details.get("output_video")

        concatenated_video_stream, total_video_duration = await stitch_assets(
            visual_assets
        )

        voiceover_audio_stream = await adjust_audio_tempo(
            voiceover_audio_path, total_video_duration
        )

        # add voiceover and background score

        # Apply the volume filter to each audio stream

        if background_score_path:
            background_score_stream = ffmpeg.input(background_score_path)
            mixed_audio_stream = await mix_audio_streams(
                voiceover_audio_stream, background_score_stream
            )

        else:
            mixed_audio_stream = voiceover_audio_stream

        concatenated_video_stream_with_audio = ffmpeg.concat(
            concatenated_video_stream,
            mixed_audio_stream,
            v=1,
            a=1,
        )
        # add subtitles
        # concatenated_stream_with_audio_and_subtitles = (
        #     concatenated_video_stream_with_audio.filter("subtitles", subtitles_path)
        # )

        # Call the output method on the result of the concatenation
        output_stream = ffmpeg.output(
            concatenated_video_stream_with_audio,
            output_video_path,
            t=total_video_duration,
            vcodec="libx264",
        )

        # Run the FFmpeg command
        output_stream.run()
        print(f"Video successfully created at: {output_video_path}")

    except Exception as e:
        print(f"Error during video editing: {e}")
        raise
