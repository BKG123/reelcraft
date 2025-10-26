# ReelCraft

**Automatically transform articles into engaging short-form videos (Reels/TikToks) using AI.**

ReelCraft is an automated video generation pipeline that converts web articles into 30-60 second social media videos. It uses Google's Gemini AI for script generation and text-to-speech, Pexels for stock media, and FFmpeg for video editing.

---

## Features

- **Automatic Script Generation**: Converts articles into engaging, fast-paced scripts optimized for short-form video
- **AI-Powered Voice Over**: Generates natural-sounding voice narration using Gemini TTS
- **Smart Asset Selection**: Automatically finds and downloads relevant images/videos from Pexels
- **Professional Video Editing**: Combines visual assets, voice-over, and background music into polished videos
- **Parallel Processing**: Efficiently generates audio and downloads assets concurrently
- **Langfuse Integration**: Track and monitor AI model calls and performance

---

## How It Works

```
Article URL -> Script Generation -> Audio Generation -> Asset Download -> Video Editing -> Final Video
```

1. **Content Extraction**: Fetches article content using FireCrawl
2. **Script Generation**: Gemini AI converts the article into 7-15 scene scripts with visual keywords
3. **Audio Generation**: Parallel generation of voice-over for each scene
4. **Asset Download**: Concurrent download of images/videos from Pexels based on keywords
5. **Video Composition**: FFmpeg stitches assets together with audio, background music, and effects

---

## Installation

### Prerequisites

- Python 3.11 or higher
- FFmpeg installed on your system
- Virtual environment tool (venv or uv)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd reelcraft
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**

   Using uv (recommended):
   ```bash
   uv sync
   ```

   Or using pip:
   ```bash
   pip install -e .
   ```

4. **Set up environment variables**

   Create a `.env` file in the project root:
   ```bash
   # Required
   GEMINI_API_KEY=your_gemini_api_key_here
   PEXELS_API_KEY=your_pexels_api_key_here
   FIRECRAWL_API_KEY=your_firecrawl_api_key_here

   # Optional - for monitoring
   LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
   LANGFUSE_SECRET_KEY=your_langfuse_secret_key
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```

### API Keys

- **Gemini API**: Get your key at [Google AI Studio](https://makersuite.google.com/app/apikey)
- **Pexels API**: Get your key at [Pexels API](https://www.pexels.com/api/)
- **FireCrawl API**: Get your key at [FireCrawl](https://firecrawl.dev/)
- **Langfuse** (Optional): Get your keys at [Langfuse](https://langfuse.com/)

---

## Usage

### Web Interface (Recommended)

The easiest way to use ReelCraft is through the web interface:

1. **Start the server**
   ```bash
   # Using uv
   uv run python main.py

   # Or with activated venv
   python main.py
   ```

2. **Open your browser**

   Navigate to [http://localhost:8000](http://localhost:8000)

3. **Generate videos**
   - Enter an article URL
   - Click "Generate Video"
   - Watch real-time progress updates
   - Preview and download your video

The web interface provides:
- Real-time progress tracking via WebSocket
- Video preview and download
- Gallery of all generated videos
- Modern, responsive design

For detailed API documentation, visit [http://localhost:8000/docs](http://localhost:8000/docs) when the server is running, or see [API.md](API.md).

### Programmatic Usage

You can also use ReelCraft programmatically:

```python
import asyncio
from pipeline import pipeline

# Generate a video from an article URL
asyncio.run(pipeline("https://example.com/article"))
```

### Advanced Usage

```python
from pipeline import pipeline, generate_assets
from utils.video_editing import script_to_asset_details, video_editing_pipeline
import asyncio
import json

async def custom_pipeline():
    # Step 1: Get article and generate script
    article_url = "https://example.com/article"

    # ... (rest of pipeline logic)

    # Step 2: Add custom background music
    asset_details = await script_to_asset_details(
        script,
        background_music_path="path/to/music.mp3"
    )

    # Step 3: Generate video
    await video_editing_pipeline(asset_details)

asyncio.run(custom_pipeline())
```

### Running from Command Line

```bash
# Using uv
uv run python -c "import asyncio; from pipeline import pipeline; asyncio.run(pipeline('YOUR_ARTICLE_URL'))"

# Or with activated venv
python -c "import asyncio; from pipeline import pipeline; asyncio.run(pipeline('YOUR_ARTICLE_URL'))"
```

---

## Project Structure

```
reelcraft/
├── pipeline.py              # Main video generation pipeline
├── main.py                  # Entry point
├── config/
│   ├── directories.py       # Asset folder paths
│   ├── prompts.py          # AI prompt templates
│   ├── logger.py           # Logging configuration
│   └── langfuse_config.py  # Langfuse monitoring setup
├── utils/
│   ├── ai.py               # Gemini AI integration (LLM + TTS)
│   ├── assets.py           # Pexels asset download
│   ├── fire_crawl.py       # Article content extraction
│   ├── video_editing.py    # FFmpeg video composition
│   └── http_client.py      # HTTP utilities
├── mocks/
│   └── mock.py             # Sample data for testing
└── assets/
    └── temp/
        ├── audio/          # Generated voice-overs
        ├── videos/         # Downloaded video assets
        ├── images/         # Downloaded image assets
        └── outputs/        # Final generated videos
```

---

## Configuration

### Directories

Edit [config/directories.py](config/directories.py) to change asset locations:

```python
AUDIO_DIR = "assets/temp/audio"
VIDEO_DIR = "assets/temp/videos"
IMAGE_DIR = "assets/temp/images"
OUTPUT_FOLDER = Path("assets/temp/outputs")
```

### Script Generation

Customize the script generation prompt in [config/prompts.py](config/prompts.py) to adjust:
- Video tone and style
- Scene count (7-15 scenes)
- Script length (30-60 seconds)
- Asset keyword generation

### Audio Settings

Adjust voice settings in [utils/ai.py](utils/ai.py):

```python
# Change voice
voice_name="Kore"  # Available voices: Kore, Aoede, Charon, Fenrir, etc.

# Adjust concurrency (avoid rate limits)
AUDIO_GENERATION_SEMAPHORE = asyncio.Semaphore(3)  # Max 3 concurrent requests
```

### Video Settings

Modify video parameters in [utils/video_editing.py](utils/video_editing.py):

```python
fps = 25              # Frame rate
asset_width = 720     # Video width (portrait: 720x1280)
asset_height = 1280   # Video height

# Audio mixing volumes
background_volume = 0.2  # Background music volume
voiceover_volume = 2.0   # Voice-over volume
```

---

## Pipeline Details

### Script Structure

Each generated script contains:

```json
{
  "title": "Video Title",
  "scenes": [
    {
      "scene_number": 1,
      "script": "Scene narration text",
      "asset_keywords": ["keyword1", "keyword2", "keyword3"],
      "asset_type": "image/video",
      "audio_file_path": "path/to/audio.wav",
      "duration": 5.2,
      "asset_file_path": "path/to/visual.mp4"
    }
  ]
}
```

### Processing Flow

1. **Content Extraction** ([utils/fire_crawl.py](utils/fire_crawl.py))
   - Fetches article markdown using FireCrawl API

2. **Script Generation** ([utils/ai.py](utils/ai.py) + [config/prompts.py](config/prompts.py))
   - Gemini AI generates 7-15 scenes with narration and asset keywords

3. **Audio Generation** ([pipeline.py:38-50](pipeline.py#L38-L50))
   - Parallel TTS generation for all scenes (max 3 concurrent)
   - Calculates audio duration for each scene

4. **Asset Download** ([pipeline.py:70-112](pipeline.py#L70-L112))
   - Parallel download of images/videos from Pexels
   - Handles "image/video" asset types intelligently

5. **Video Composition** ([utils/video_editing.py](utils/video_editing.py))
   - Combines all audio files sequentially
   - Stitches visual assets with effects (zoom/pan for images)
   - Adjusts audio tempo to match video duration
   - Mixes voice-over with background music
   - Exports final video

---

## Monitoring with Langfuse

If Langfuse is configured, the pipeline automatically tracks:
- LLM API calls and token usage
- Generation parameters and responses
- Error tracking and debugging

View traces at your Langfuse dashboard.

---

## Troubleshooting

### FFmpeg Not Found

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

### Rate Limit Errors

Adjust the semaphore limit in [utils/ai.py](utils/ai.py):

```python
AUDIO_GENERATION_SEMAPHORE = asyncio.Semaphore(2)  # Reduce concurrent requests
```

### No Assets Found

- Check your Pexels API key
- Try more generic keywords in the script
- Verify internet connection

### Audio/Video Sync Issues

The pipeline automatically adjusts audio tempo (0.5x - 2x) to match video duration. If issues persist:
- Check scene duration calculations
- Verify FFmpeg installation
- Review audio file integrity

---

## Dependencies

Core dependencies:
- `ffmpeg-python` - Video editing
- `pydub` - Audio processing
- `google-genai` - Gemini AI (LLM + TTS)
- `firecrawl-py` - Article extraction
- `httpx` - Async HTTP client
- `requests` - Pexels API
- `fastapi` - Web framework and API
- `uvicorn` - ASGI server
- `langfuse` - Monitoring (optional)
- `python-dotenv` - Environment configuration

---

## Limitations

- **Video Duration**: Currently optimized for 30-60 second videos
- **Rate Limits**: Free tier APIs have request limits (use semaphores)
- **Asset Quality**: Dependent on Pexels search results
- **Gemini TTS Voices**: Limited to available prebuilt voices
- **FFmpeg Dependencies**: Requires system FFmpeg installation

---

## Roadmap

- [x] Web UI for easier usage (FastAPI + WebSocket)
- [ ] Subtitle generation support
- [ ] Custom font and styling options
- [ ] Multiple aspect ratios (square, landscape)
- [ ] Direct social media upload integration
- [ ] Batch processing multiple articles
- [ ] Custom background music library

---

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## License

[Add your license here]

---

## Acknowledgments

- Google Gemini AI for LLM and TTS capabilities
- Pexels for stock media API
- FireCrawl for article extraction
- FFmpeg for video processing
