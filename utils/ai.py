import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
import wave
import requests
import mimetypes
from langfuse import observe, get_client as get_langfuse_client
from config.langfuse_config import langfuse_config
from config.logger import get_logger

load_dotenv()
logger = get_logger(__name__)
DIR = "assets/temp"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def get_file_mime_type(file_path: str) -> str:
    """
    Get MIME type of a file from its path or extension.

    Args:
        file_path: Path to the file

    Returns:
        MIME type string (e.g., 'image/jpeg') or 'application/octet-stream' if unknown

    Example:
        >>> get_file_mime_type('/path/to/image.jpg')
        'image/jpeg'
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"


# Set up the wave file to save the output:
def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


client = genai.Client(api_key=GEMINI_API_KEY)


def generate_audio_file(content: str, file_name: str):
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=content,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Kore",
                    )
                )
            ),
        ),
    )

    data = response.candidates[0].content.parts[0].inline_data.data

    file_name = DIR + "audio" + f"{file_name}.wav"
    wave_file(file_name, data)
    return file_name


logger = get_logger(__name__)


def _prepare_image_part(image_data: bytes, source: str) -> types.Part:
    """
    Create a Part object from image data.

    Args:
        image_data: Raw image bytes
        source: Source path or URL for MIME type detection

    Returns:
        types.Part object ready for Gemini API
    """
    mime_type = get_file_mime_type(source)
    return types.Part.from_bytes(data=image_data, mime_type=mime_type)


def _prepare_contents(
    user_prompt: str | None,
    image_urls: list[str],
    image_file_path: str | None,
) -> list:
    """
    Prepare contents list with text and images for Gemini API.

    Args:
        user_prompt: Optional user text prompt
        image_urls: List of image URLs to fetch and include
        image_file_path: Optional local image file path

    Returns:
        List of contents (strings and Part objects) for API call
    """
    contents: list = []

    # Add user prompt if provided
    if user_prompt:
        contents.append(user_prompt)

    # Fetch and attach images from URLs
    for url in image_urls:
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()

            # Determine MIME type from headers or URL
            mime_type = resp.headers.get("Content-Type")
            if not mime_type:
                mime_type = get_file_mime_type(url)

            image_part = types.Part.from_bytes(
                data=resp.content,
                mime_type=mime_type,
            )
            contents.append(image_part)
        except Exception as e:
            logger.error(f"Warning: Skipping image {url} due to error: {e}")

    # Attach image from file path if provided
    if image_file_path:
        try:
            with open(image_file_path, "rb") as f:
                image_data = f.read()

            image_part = _prepare_image_part(image_data, image_file_path)
            contents.append(image_part)
        except Exception as e:
            logger.error(
                f"Warning: Skipping image file {image_file_path} due to error: {e}"
            )

    return contents


@observe(name="gemini_llm_call", as_type="generation")
async def gemini_llm_call(
    system_prompt: str,
    user_prompt: str | None,
    model_name: str,
    temperature: float = 0.1,
    json_format: bool = False,
    is_thinking_enabled: bool = True,
    image_urls: list[str] = [],
    image_file_path: str | None = None,
    url_context: None = None,
    **kwargs,
):
    try:
        # Update Langfuse generation with metadata
        if langfuse_config.is_configured:
            try:
                langfuse_client = get_langfuse_client()
                langfuse_client.update_current_generation(
                    name="gemini_llm_call",
                    metadata={
                        "model": model_name,
                        "temperature": temperature,
                        "json_format": json_format,
                        "thinking_enabled": is_thinking_enabled,
                        "has_images": bool(image_urls or image_file_path),
                    },
                )
            except Exception as e:
                logger.debug(f"Failed to update Langfuse context: {e}")
        client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY"),
        )

        response_mime_type = "application/json" if json_format else "text/plain"
        if is_thinking_enabled:
            thinking_budget = kwargs.get("thinking_budget", 1024)
        else:
            thinking_budget = 0

        # Set up tools only when needed and not using JSON format
        tools_config = None
        if not json_format and url_context:
            # For now, skip tools configuration as it requires specific setup
            tools_config = None

        config = types.GenerateContentConfig(
            response_mime_type=response_mime_type,
            temperature=temperature,
            top_p=0.95,
            top_k=64,
            system_instruction=system_prompt,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
            tools=tools_config,
        )

        # Prepare contents with optional images
        contents = _prepare_contents(user_prompt, image_urls, image_file_path)

        # Call the Gemini API with combined contents (images + prompt)
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        # Build messages for logging
        messages = [{"role": "system", "content": system_prompt}]
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})
        if image_urls:
            for url in image_urls:
                messages.append({"role": "user", "content": f"[Attached {url}]"})

        # Extract usage metadata from response
        usage_metadata = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage_metadata = {
                "input": response.usage_metadata.prompt_token_count,
                "output": response.usage_metadata.candidates_token_count,
                "total": response.usage_metadata.total_token_count,
            }
            logger.info(f"Token usage: {usage_metadata}")

        # Update Langfuse with input/output and usage
        if langfuse_config.is_configured:
            try:
                langfuse_client = get_langfuse_client()
                update_params = {
                    "input": {"messages": messages, "config": config.__dict__},
                    "output": response.text,
                    "model": model_name,
                }
                if usage_metadata:
                    update_params["usage_details"] = usage_metadata

                langfuse_client.update_current_generation(**update_params)
            except Exception as e:
                logger.debug(f"Failed to update Langfuse with I/O: {e}")

        print(messages)
        return response.text

    except Exception as e:
        logger.error(f"Error in Gemini LLM call: {e}")
        # Log error to Langfuse
        if langfuse_config.is_configured:
            try:
                langfuse_client = get_langfuse_client()
                langfuse_client.update_current_generation(
                    level="ERROR",
                    status_message=str(e),
                )
            except Exception:
                pass  # Silently fail if Langfuse update fails
        raise
