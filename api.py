from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from pipeline import pipeline
from config.directories import OUTPUT_FOLDER
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ReelCraft API",
    description="API for generating short-form videos from articles",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="frontend"), name="static")


class VideoGenerationRequest(BaseModel):
    url: HttpUrl

    class Config:
        json_schema_extra = {"example": {"url": "https://example.com/article"}}


class VideoGenerationResponse(BaseModel):
    status: str
    message: str
    video_path: Optional[str] = None
    script: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str
    message: str


# Store active WebSocket connections
active_connections: list[WebSocket] = []


async def broadcast_progress(message: str):
    """Broadcast progress updates to all connected WebSocket clients"""
    for connection in active_connections:
        try:
            await connection.send_json({"type": "progress", "message": message})
        except Exception as e:
            logger.error(f"Error broadcasting to websocket: {e}")


@app.get("/", response_class=FileResponse)
async def root():
    """Serve the frontend HTML"""
    return FileResponse("frontend/index.html")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "ReelCraft API is running"}


@app.post("/api/generate-video", response_model=VideoGenerationResponse)
async def generate_video(request: VideoGenerationRequest):
    """
    Generate a video from an article URL

    - **url**: The URL of the article to convert into a video
    """
    try:
        url = str(request.url)
        logger.info(f"Starting video generation for URL: {url}")
        await broadcast_progress(f"Starting video generation for: {url}")

        # Run the pipeline
        await broadcast_progress("Extracting article content...")
        await pipeline(url)

        await broadcast_progress("Video generation completed!")

        # Find the most recent video file in the output folder
        output_folder = Path(OUTPUT_FOLDER)
        video_files = list(output_folder.glob("*.mp4"))

        if not video_files:
            raise HTTPException(
                status_code=500, detail="Video file not found after generation"
            )

        # Get the most recently created video
        latest_video = max(video_files, key=lambda p: p.stat().st_mtime)

        return {
            "status": "success",
            "message": "Video generated successfully",
            "video_path": str(latest_video.relative_to(output_folder.parent.parent)),
        }

    except Exception as e:
        logger.error(f"Error generating video: {str(e)}")
        await broadcast_progress(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos")
async def list_videos():
    """
    List all generated videos
    """
    try:
        output_folder = Path(OUTPUT_FOLDER)
        if not output_folder.exists():
            return {"videos": []}

        video_files = list(output_folder.glob("*.mp4"))
        videos = [
            {
                "filename": video.name,
                "path": str(video.relative_to(output_folder.parent.parent)),
                "created_at": video.stat().st_mtime,
                "size_mb": round(video.stat().st_size / (1024 * 1024), 2),
            }
            for video in sorted(
                video_files, key=lambda p: p.stat().st_mtime, reverse=True
            )
        ]

        return {"videos": videos}

    except Exception as e:
        logger.error(f"Error listing videos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos/{video_name}")
async def get_video(video_name: str):
    """
    Download or stream a generated video
    """
    try:
        output_folder = Path(OUTPUT_FOLDER)
        video_path = output_folder / video_name

        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video not found")

        return FileResponse(video_path, media_type="video/mp4", filename=video_name)

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Video not found")
    except Exception as e:
        logger.error(f"Error retrieving video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time progress updates
    """
    await websocket.accept()
    active_connections.append(websocket)

    try:
        await websocket.send_json(
            {"type": "connection", "message": "Connected to ReelCraft API"}
        )

        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Echo back or handle commands if needed
            await websocket.send_json({"type": "echo", "message": f"Received: {data}"})

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
