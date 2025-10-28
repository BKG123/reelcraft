import ffmpeg
import os
import tempfile
from pydub import AudioSegment
from config.directories import OUTPUT_FOLDER


def get_video_dimensions(video_path: str) -> tuple:
    """
    Get the width and height of a video file.

    Args:
        video_path: Path to the video file

    Returns:
        Tuple of (width, height)
    """
    try:
        probe = ffmpeg.probe(video_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if video_stream:
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            return (width, height)
    except Exception as e:
        print(f"Error probing video dimensions: {e}")
    return (0, 0)


def get_image_dimensions(image_path: str) -> tuple:
    """
    Get the width and height of an image file using ffprobe.

    Args:
        image_path: Path to the image file

    Returns:
        Tuple of (width, height)
    """
    try:
        probe = ffmpeg.probe(image_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if video_stream:
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            return (width, height)
    except Exception as e:
        print(f"Error probing image dimensions: {e}")
    return (0, 0)


async def generate_text_clip(text: str, duration: float, fps: int = 25, width: int = 720, height: int = 1280) -> str:
    """
    Generate a text-only video clip with animated text on a solid background.

    Args:
        text: Text to display (should be short, 1-5 words)
        duration: Duration of the clip in seconds
        fps: Frame rate
        width: Video width
        height: Video height

    Returns:
        Path to the generated video file
    """
    # Create temp file for the text clip
    temp_dir = "assets/temp/text_clips"
    os.makedirs(temp_dir, exist_ok=True)

    # Sanitize text for filename
    safe_text = "".join(c if c.isalnum() else "_" for c in text)[:30]
    output_path = os.path.join(temp_dir, f"text_{safe_text}.mp4")

    # Escape text for FFmpeg drawtext filter
    escaped_text = text.replace("'", "\\'").replace(":", "\\:")

    # Create a solid color background with animated text
    # Text will fade in, stay, then fade out
    fade_duration = min(0.3, duration / 4)  # 0.3s fade or 1/4 of duration

    try:
        (
            ffmpeg
            .input(f'color=c=#1a1a2e:s={width}x{height}:d={duration}:r={fps}', f='lavfi')
            .drawtext(
                text=escaped_text,
                fontsize=80,
                fontcolor='white',
                font='Arial-Bold',
                x='(w-text_w)/2',
                y='(h-text_h)/2',
                enable=f'between(t,{fade_duration},{duration-fade_duration})',
                # Add text shadow for better readability
                shadowcolor='black',
                shadowx=3,
                shadowy=3
            )
            .output(output_path, vcodec='libx264', pix_fmt='yuv420p', t=duration)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output_path
    except ffmpeg.Error as e:
        print(f"Error generating text clip: {e.stderr.decode()}")
        raise


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


async def script_to_asset_details(
    script: dict, background_music_path: str = None
) -> dict:
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
        scene_type = scene.get("scene_type", "media")

        # Handle text-only scenes
        if scene_type == "text":
            visual_assets.append(
                {
                    "path": None,
                    "type": "text",
                    "duration": scene.get("duration", 2.0),  # Default 2s for text
                    "text": scene.get("script", "TEXT"),
                }
            )
            # Collect audio file paths (text scenes may still have audio)
            if scene.get("audio_file_path"):
                audio_file_paths.append(scene["audio_file_path"])
            continue

        # Add visual asset for media scenes
        asset_file_path = scene.get("asset_file_path")

        # Determine actual type from file extension (more reliable than asset_type field)
        if asset_file_path:
            file_ext = os.path.splitext(asset_file_path)[1].lower()
            if file_ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]:
                actual_type = "image"
            elif file_ext in [".mp4", ".mov", ".avi", ".webm", ".mkv", ".flv"]:
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

        visual_assets.append(
            {
                "path": asset_file_path,
                "type": actual_type,
                "duration": scene.get("duration", 5.0),
            }
        )

        # Collect audio file paths
        if scene.get("audio_file_path"):
            audio_file_paths.append(scene["audio_file_path"])

    # Combine all scene audio files into one
    combined_voiceover_path = await combine_audio_files(audio_file_paths, title)

    # Build asset_details structure
    asset_details = {
        "visual_assets": visual_assets,
        "audio_assets": {"voice_over": {"path": combined_voiceover_path}},
        "output_video": f"{OUTPUT_FOLDER}/{title.lower().replace(' ', '_')}.mp4",
    }

    # Add background music if provided
    if background_music_path and os.path.exists(background_music_path):
        asset_details["audio_assets"]["background_score"] = {
            "path": background_music_path
        }

    return asset_details


async def stitch_assets(visual_assets: list, use_transitions: bool = True):
    """
    Stitch visual assets together with optional transitions.

    Args:
        visual_assets: List of asset dictionaries
        use_transitions: Whether to add transitions between clips (default: True)

    Returns:
        Tuple of (concatenated_stream, total_duration)
    """
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

        if asset_type == "text":
            # Generate text clip on the fly
            text = asset.get("text", "TEXT")
            text_clip_path = await generate_text_clip(text, duration, fps, asset_width, asset_height)
            ffmpeg_asset_objects.append(
                ffmpeg.input(text_clip_path)
                .trim(start=0, duration=duration)
                .setpts("PTS-STARTPTS")
                .filter("fps", fps=fps)
                .filter("format", "yuv420p")
            )
        elif asset_type == "image":
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
            # Detect video aspect ratio
            video_width, video_height = get_video_dimensions(asset_path)

            if video_width > 0 and video_height > 0:
                aspect_ratio = video_width / video_height
                target_aspect_ratio = asset_width / asset_height  # 0.5625 for 720x1280

                # If video is landscape (wider than portrait), add blurred background
                if aspect_ratio > target_aspect_ratio * 1.2:  # 20% threshold
                    # Create blurred background
                    background = (
                        ffmpeg.input(asset_path)
                        .trim(start=0, duration=duration)
                        .setpts("PTS-STARTPTS")
                        .filter("scale", asset_width, asset_height, force_original_aspect_ratio='increase')
                        .filter("crop", asset_width, asset_height)
                        .filter("boxblur", 20)
                    )

                    # Create centered foreground
                    foreground = (
                        ffmpeg.input(asset_path)
                        .trim(start=0, duration=duration)
                        .setpts("PTS-STARTPTS")
                        .filter("scale", asset_width, -1)
                    )

                    # Overlay foreground on blurred background
                    combined = ffmpeg.overlay(background, foreground, x='(W-w)/2', y='(H-h)/2')
                    ffmpeg_asset_objects.append(
                        combined
                        .filter("fps", fps=fps)
                        .filter("format", "yuv420p")
                    )
                else:
                    # Normal scaling for portrait/square videos
                    ffmpeg_asset_objects.append(
                        ffmpeg.input(asset_path)
                        .trim(start=0, duration=duration)
                        .setpts("PTS-STARTPTS")
                        .filter("scale", asset_width, asset_height)
                        .filter("fps", fps=fps)
                        .filter("format", "yuv420p")
                    )
            else:
                # Fallback: normal scaling if dimensions couldn't be detected
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

    # Add transitions between clips if enabled and we have multiple clips
    if use_transitions and len(ffmpeg_asset_objects) > 1:
        transition_duration = 0.3  # 300ms transitions

        # Apply xfade transitions between consecutive clips
        result = ffmpeg_asset_objects[0]
        offset = 0

        for i in range(1, len(ffmpeg_asset_objects)):
            # Choose transition type (cycle through different types for variety)
            transition_types = ['fade', 'wipeleft', 'wiperight', 'slideleft', 'slideright', 'fadeblack']
            transition_type = transition_types[i % len(transition_types)]

            # Calculate offset for transition (overlap clips by transition_duration)
            clip_duration = visual_assets[i-1]['duration']
            offset += clip_duration - transition_duration

            # Apply xfade filter
            result = ffmpeg.filter(
                [result, ffmpeg_asset_objects[i]],
                'xfade',
                transition=transition_type,
                duration=transition_duration,
                offset=offset
            )

        concatenated_video_stream = result
    else:
        # No transitions: simple concatenation
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
    """
    Mix voiceover and background audio with dynamic ducking.

    Uses sidechaincompress to automatically lower background music volume
    when voiceover is playing, creating a professional audio mix.
    """
    # Apply sidechain compression - ducks background music when voiceover plays
    ducked_background = ffmpeg.filter(
        [background_score_stream, voiceover_audio_stream],
        'sidechaincompress',
        threshold=0.02,    # Start ducking at this audio level
        ratio=4,           # Compression ratio (how much to duck)
        attack=5,          # How fast to duck (milliseconds)
        release=200,       # How fast to return to normal (milliseconds)
        makeup=1           # Compensate for volume reduction
    )

    # Boost voiceover to ensure clarity
    voiceover_stream_with_volume = voiceover_audio_stream.filter("volume", volume=2.0)

    # Mix the ducked background with boosted voiceover
    mixed_audio_stream = ffmpeg.filter(
        [voiceover_stream_with_volume, ducked_background],
        "amix",
        inputs=2,
        weights="2 1"  # Voiceover weighted higher than background
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
