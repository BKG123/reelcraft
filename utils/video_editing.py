import ffmpeg
from asset_generation import cleanup_assets


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
                    )  # zoom+0.001 for slow zoom in
                    .filter("format", "yuv420p")
                    .trim(duration=duration)
                )
            )
        elif asset_type == "video":
            ffmpeg_asset_objects.append(
                ffmpeg.input(asset_path)
                .filter("scale", asset_width, asset_height)
                .trim(duration=duration)
                .setpts("PTS-STARTPTS")
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
        cleanup_assets(asset_details)

    except Exception as e:
        print(e)
        cleanup_assets(asset_details)
