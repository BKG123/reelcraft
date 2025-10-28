from pathlib import Path
from typing import Optional
import json
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from services.pipeline import pipeline
from config.directories import OUTPUT_FOLDER
from services.database import init_db, async_session, Job, Video, JobStatus, StorageLocation
from services.job_manager import job_manager, JobProgress
from services.cleanup import cleanup_generation_assets
from services.storage import storage_manager
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
    if not video_path.is_absolute():
        video_path = Path.cwd() / video_path

    size_mb = video_path.stat().st_size / (1024 * 1024) if video_path.exists() else None

    # Create video entry and optionally upload to cloud
    video = None
    async with async_session() as session:
        # Determine file path based on cloud storage availability
        if storage_manager.is_enabled():
            await broadcast_progress("Uploading video to cloud storage...")
            try:
                # Create video entry with placeholder
                video = Video(
                    title=result["title"],
                    source_url=url,
                    file_path="uploading...",
                    size_mb=round(size_mb, 2) if size_mb else None,
                    script_json=json.dumps(result["script"]),
                )
                session.add(video)
                await session.commit()
                await session.refresh(video)

                # Upload to cloud
                cloud_url = await storage_manager.upload_video(str(video_path), video.id)

                if cloud_url:
                    logger.info(f"Video uploaded to cloud: {cloud_url}")
                    video.file_path = cloud_url
                    video.storage_location = StorageLocation.CLOUD
                    await broadcast_progress("Video uploaded to cloud storage")
                else:
                    # Cloud upload failed, use local path
                    logger.warning("Cloud upload failed, falling back to local path")
                    try:
                        relative_path = video_path.relative_to(Path.cwd())
                        video.file_path = str(relative_path)
                    except ValueError:
                        video.file_path = str(video_path)
                    video.storage_location = StorageLocation.LOCAL

                await session.commit()
                await session.refresh(video)

            except Exception as e:
                logger.error(f"Error during cloud upload: {e}")
                # If video wasn't created, we'll create it below with local path
                if not video:
                    raise

        # If cloud storage not enabled, create video with local path
        if not video:
            try:
                relative_path = video_path.relative_to(Path.cwd())
                file_path_str = str(relative_path)
            except ValueError:
                file_path_str = str(video_path)
                logger.warning(f"Could not make path relative, storing absolute: {file_path_str}")

            video = Video(
                title=result["title"],
                source_url=url,
                file_path=file_path_str,
                storage_location=StorageLocation.LOCAL,
                size_mb=round(size_mb, 2) if size_mb else None,
                script_json=json.dumps(result["script"]),
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

    # Clean up temporary assets after successful generation
    try:
        await broadcast_progress("Cleaning up temporary files...")
        cleaned_count, cleaned_size = cleanup_generation_assets(result["title"])
        cleaned_mb = cleaned_size / (1024 * 1024)
        logger.info(f"Cleaned up {cleaned_count} files ({cleaned_mb:.2f} MB)")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        # Don't fail the job if cleanup fails

    return result


@app.post("/api/generate-video", response_model=VideoGenerationResponse)
async def generate_video(request: VideoGenerationRequest):
    """
    Start a background job to generate a video from an article URL.

    If the URL has already been processed, returns the existing video
    instead of creating a new job.

    Returns job_id for tracking progress or existing video info.

    - **url**: The URL of the article to convert into a video
    """
    try:
        url = str(request.url)
        logger.info(f"Request for video generation from URL: {url}")

        # Check if we already have a video for this URL
        async with async_session() as session:
            result = await session.execute(
                select(Video)
                .where(Video.source_url == url)
                .order_by(Video.created_at.desc())
            )
            existing_video = result.scalar_one_or_none()

            if existing_video:
                logger.info(
                    f"Found existing video (ID: {existing_video.id}) for URL: {url}"
                )

                # Create a "fake" completed job entry for consistency
                job = Job(
                    id=str(uuid.uuid4()),
                    status=JobStatus.COMPLETED,
                    progress=100,
                    progress_message=f"Video already exists (reused from cache)",
                    video_id=existing_video.id,
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                )
                session.add(job)
                await session.commit()

                return {
                    "job_id": job.id,
                    "status": "completed",
                    "message": f"Video already exists for this URL. Reusing existing video (ID: {existing_video.id})",
                }

        # URL not found, create new background job
        logger.info(f"Creating new video generation job for URL: {url}")
        job_id = await job_manager.create_job(video_generation_job, url=url)

        return {
            "job_id": job_id,
            "status": "pending",
            "message": f"Video generation job created. Use job_id to track progress.",
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
            status_code=404, detail="Job not found or already completed"
        )

    return {"status": "cancelled", "message": f"Job {job_id} cancelled"}


@app.get("/api/jobs")
async def list_jobs(status: Optional[str] = None, limit: int = 50, offset: int = 0):
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
                    detail=f"Invalid status. Must be one of: {[s.value for s in JobStatus]}",
                )

        jobs = await job_manager.list_jobs(
            status=job_status_enum, limit=limit, offset=offset
        )

        return {"jobs": jobs, "count": len(jobs)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos", response_model=dict)
async def list_videos(
    limit: int = 50,
    offset: int = 0,
    storage_location: Optional[str] = None
):
    """
    List all generated videos from database.

    - **limit**: Maximum number of videos to return (default: 50)
    - **offset**: Offset for pagination (default: 0)
    - **storage_location**: Filter by storage location ("local" or "cloud")
    """
    try:
        async with async_session() as session:
            query = select(Video).order_by(Video.created_at.desc())

            # Filter by storage location if specified
            if storage_location:
                try:
                    location_enum = StorageLocation(storage_location.lower())
                    query = query.where(Video.storage_location == location_enum)
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid storage_location. Must be 'local' or 'cloud'"
                    )

            query = query.limit(limit).offset(offset)
            result = await session.execute(query)
            videos = result.scalars().all()

            return {
                "videos": [video.to_dict() for video in videos],
                "count": len(videos),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing videos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos/{video_id}/file")
async def get_video_by_id(video_id: int):
    """
    Download or stream a video by its database ID.

    If the video is stored in cloud storage (URL starts with http/https),
    redirects to the cloud URL. Otherwise serves the local file.
    """
    try:
        async with async_session() as session:
            result = await session.execute(select(Video).where(Video.id == video_id))
            video = result.scalar_one_or_none()

            if not video or not video.file_path:
                raise HTTPException(status_code=404, detail="Video not found")

            # Check if file_path is a cloud URL (starts with http:// or https://)
            if video.file_path.startswith(("http://", "https://")):
                # Redirect to cloud storage URL
                return RedirectResponse(url=video.file_path)

            # Local file - convert relative path to absolute
            video_path = Path(video.file_path)
            if not video_path.is_absolute():
                video_path = Path.cwd() / video_path

            if not video_path.exists():
                raise HTTPException(
                    status_code=404, detail="Video file not found on disk"
                )

            return FileResponse(
                video_path, media_type="video/mp4", filename=video_path.name
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos/{video_name}")
async def get_video(video_name: str):
    """
    Download or stream a generated video by filename (legacy endpoint)
    """
    try:
        output_folder = Path(OUTPUT_FOLDER)
        video_path = output_folder / video_name

        # Security check: ensure the path is within OUTPUT_FOLDER
        try:
            video_path = video_path.resolve()
            output_folder = output_folder.resolve()
            video_path.relative_to(output_folder)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")

        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video not found")

        return FileResponse(video_path, media_type="video/mp4", filename=video_name)

    except HTTPException:
        raise
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
                        await websocket.send_json(
                            {
                                "type": "job_progress",
                                "job_id": job_id,
                                "progress": progress.progress,
                                "message": progress.message,
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error sending job progress: {e}")

                job_callback = send_job_progress
                subscribed_job_id = job_id

                # Register callback with job manager
                await job_manager.register_progress_callback(job_id, job_callback)

                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "job_id": job_id,
                        "message": f"Subscribed to job {job_id}",
                    }
                )

                # Send current job status
                job_status = await job_manager.get_job_status(job_id)
                if job_status:
                    await websocket.send_json(
                        {"type": "job_status", "job_id": job_id, "status": job_status}
                    )

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
