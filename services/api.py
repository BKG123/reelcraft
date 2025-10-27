from pathlib import Path
from typing import Optional
import json
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from pipeline import pipeline
from config.directories import OUTPUT_FOLDER
from database import init_db, get_session, async_session, Job, Video, JobStatus
from job_manager import job_manager, JobProgress
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ReelCraft API",
    description="API for generating short-form videos from articles",
    version="2.0.0",
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    await init_db()
    logger.info("Database initialized")

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
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    id: str
    status: str
    progress: int
    progress_message: str
    error_message: Optional[str] = None
    video_id: Optional[int] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class VideoResponse(BaseModel):
    id: int
    title: str
    source_url: str
    file_path: Optional[str] = None
    duration: Optional[float] = None
    size_mb: Optional[float] = None
    created_at: str


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


async def video_generation_job(job_id: str, progress_callback, url: str):
    """
    Background job for video generation.

    Args:
        job_id: Job ID
        progress_callback: Progress callback function
        url: Article URL to process
    """
    # Broadcast to WebSocket connections
    await broadcast_progress(f"Starting video generation for: {url}")

    # Run pipeline with progress tracking
    result = await pipeline(url, progress_callback=progress_callback)

    # Calculate file size
    video_path = Path(result["output_video"])
    size_mb = video_path.stat().st_size / (1024 * 1024) if video_path.exists() else None

    # Save video to database
    async with async_session() as session:
        video = Video(
            title=result["title"],
            source_url=url,
            file_path=str(video_path.relative_to(Path.cwd())),
            size_mb=round(size_mb, 2) if size_mb else None,
            script_json=json.dumps(result["script"])
        )
        session.add(video)
        await session.commit()
        await session.refresh(video)

        # Update job with video_id
        result_db = await session.execute(select(Job).where(Job.id == job_id))
        job = result_db.scalar_one_or_none()
        if job:
            job.video_id = video.id
            await session.commit()

        await broadcast_progress(f"Video generation completed! Video ID: {video.id}")

    return result


@app.post("/api/generate-video", response_model=VideoGenerationResponse)
async def generate_video(request: VideoGenerationRequest):
    """
    Start a background job to generate a video from an article URL.

    Returns job_id for tracking progress.

    - **url**: The URL of the article to convert into a video
    """
    try:
        url = str(request.url)
        logger.info(f"Creating video generation job for URL: {url}")

        # Create background job
        job_id = await job_manager.create_job(
            video_generation_job,
            url=url
        )

        return {
            "job_id": job_id,
            "status": "pending",
            "message": f"Video generation job created. Use job_id to track progress."
        }

    except Exception as e:
        logger.error(f"Error creating video generation job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a video generation job.

    - **job_id**: The job ID returned from /api/generate-video
    """
    job_status = await job_manager.get_job_status(job_id)

    if not job_status:
        raise HTTPException(status_code=404, detail="Job not found")

    return job_status


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """
    Cancel a running job.

    - **job_id**: The job ID to cancel
    """
    cancelled = await job_manager.cancel_job(job_id)

    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail="Job not found or already completed"
        )

    return {"status": "cancelled", "message": f"Job {job_id} cancelled"}


@app.get("/api/jobs")
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    List all jobs with optional filtering.

    - **status**: Filter by status (pending, processing, completed, failed, cancelled)
    - **limit**: Maximum number of jobs to return (default: 50)
    - **offset**: Offset for pagination (default: 0)
    """
    try:
        job_status_enum = None
        if status:
            try:
                job_status_enum = JobStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be one of: {[s.value for s in JobStatus]}"
                )

        jobs = await job_manager.list_jobs(
            status=job_status_enum,
            limit=limit,
            offset=offset
        )

        return {"jobs": jobs, "count": len(jobs)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos", response_model=dict)
async def list_videos(limit: int = 50, offset: int = 0):
    """
    List all generated videos from database.

    - **limit**: Maximum number of videos to return (default: 50)
    - **offset**: Offset for pagination (default: 0)
    """
    try:
        async with async_session() as session:
            query = select(Video).order_by(Video.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(query)
            videos = result.scalars().all()

            return {
                "videos": [video.to_dict() for video in videos],
                "count": len(videos)
            }

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
    WebSocket endpoint for real-time progress updates.

    Supports job-specific tracking by sending {"subscribe": "job_id"}
    """
    await websocket.accept()
    active_connections.append(websocket)
    subscribed_job_id: Optional[str] = None
    job_callback = None

    try:
        await websocket.send_json(
            {"type": "connection", "message": "Connected to ReelCraft API"}
        )

        # Handle incoming messages
        while True:
            data = await websocket.receive_json()

            # Handle job subscription
            if isinstance(data, dict) and "subscribe" in data:
                job_id = data["subscribe"]

                # Unsubscribe from previous job if any
                if subscribed_job_id and job_callback:
                    await job_manager.unregister_progress_callback(
                        subscribed_job_id, job_callback
                    )

                # Create callback for this job
                async def send_job_progress(progress: JobProgress):
                    try:
                        await websocket.send_json({
                            "type": "job_progress",
                            "job_id": job_id,
                            "progress": progress.progress,
                            "message": progress.message
                        })
                    except Exception as e:
                        logger.error(f"Error sending job progress: {e}")

                job_callback = send_job_progress
                subscribed_job_id = job_id

                # Register callback with job manager
                await job_manager.register_progress_callback(job_id, job_callback)

                await websocket.send_json({
                    "type": "subscribed",
                    "job_id": job_id,
                    "message": f"Subscribed to job {job_id}"
                })

                # Send current job status
                job_status = await job_manager.get_job_status(job_id)
                if job_status:
                    await websocket.send_json({
                        "type": "job_status",
                        "job_id": job_id,
                        "status": job_status
                    })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cleanup
        if subscribed_job_id and job_callback:
            await job_manager.unregister_progress_callback(
                subscribed_job_id, job_callback
            )
        if websocket in active_connections:
            active_connections.remove(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
