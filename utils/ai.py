import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
import wave

load_dotenv()

DIR = "assets/temp"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


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
