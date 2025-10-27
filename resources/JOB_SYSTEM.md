# Background Job System Documentation

## Overview

ReelCraft now uses an **asyncio-based background job system** with **SQLite database** for persistent storage and tracking. This allows video generation to run asynchronously without blocking API requests.

## Architecture

### Components

1. **Database Layer** (`database.py`)
   - SQLAlchemy async ORM with SQLite backend
   - Two main tables: `jobs` and `videos`
   - Automatic database initialization on startup

2. **Job Manager** (`job_manager.py`)
   - Manages background tasks using asyncio
   - Tracks job status and progress
   - Supports job cancellation
   - Progress callbacks for real-time updates

3. **Pipeline** (`pipeline.py`)
   - Updated to support progress callbacks
   - Reports progress at each stage (5%, 10%, 25%, 50%, 75%, 85%, 95%, 100%)

4. **API** (`api.py`)
   - Job-based workflow instead of synchronous processing
   - New endpoints for job management
   - WebSocket support for real-time job tracking

## Database Schema

### Jobs Table
```sql
CREATE TABLE jobs (
    id VARCHAR PRIMARY KEY,           -- UUID
    status VARCHAR NOT NULL,          -- pending, processing, completed, failed, cancelled
    progress INTEGER DEFAULT 0,        -- 0-100
    progress_message VARCHAR,
    error_message TEXT,
    created_at DATETIME NOT NULL,
    started_at DATETIME,
    completed_at DATETIME,
    video_id INTEGER FOREIGN KEY       -- Links to videos table
);
```

### Videos Table
```sql
CREATE TABLE videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR NOT NULL,
    source_url TEXT NOT NULL,
    file_path VARCHAR,
    duration FLOAT,
    size_mb FLOAT,
    script_json TEXT,                  -- JSON string of the generated script
    created_at DATETIME NOT NULL
);
```

## API Endpoints

### Video Generation

#### POST `/api/generate-video`
Create a new video generation job.

**Request:**
```json
{
  "url": "https://example.com/article"
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Video generation job created. Use job_id to track progress."
}
```

### Job Management

#### GET `/api/jobs/{job_id}`
Get status of a specific job.

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45,
  "progress_message": "Downloading visual assets...",
  "error_message": null,
  "video_id": null,
  "created_at": "2025-10-27T10:30:00",
  "started_at": "2025-10-27T10:30:01",
  "completed_at": null
}
```

#### GET `/api/jobs`
List all jobs with optional filtering.

**Query Parameters:**
- `status` (optional): Filter by status (`pending`, `processing`, `completed`, `failed`, `cancelled`)
- `limit` (default: 50): Maximum number of jobs to return
- `offset` (default: 0): Pagination offset

**Response:**
```json
{
  "jobs": [...],
  "count": 25
}
```

#### POST `/api/jobs/{job_id}/cancel`
Cancel a running job.

**Response:**
```json
{
  "status": "cancelled",
  "message": "Job 550e8400-e29b-41d4-a716-446655440000 cancelled"
}
```

### Video Management

#### GET `/api/videos`
List all generated videos from database.

**Query Parameters:**
- `limit` (default: 50): Maximum number of videos to return
- `offset` (default: 0): Pagination offset

**Response:**
```json
{
  "videos": [
    {
      "id": 1,
      "title": "Amazing AI Discovery",
      "source_url": "https://example.com/article",
      "file_path": "assets/temp/outputs/amazing_ai_discovery.mp4",
      "duration": null,
      "size_mb": 12.5,
      "created_at": "2025-10-27T10:35:00"
    }
  ],
  "count": 1
}
```

#### GET `/api/videos/{video_name}`
Download or stream a specific video file.

## WebSocket Protocol

### Connection
Connect to `ws://localhost:8000/ws`

### Subscribe to Job Updates
Send a message to subscribe to job progress:
```json
{
  "subscribe": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Message Types

#### Connection Confirmation
```json
{
  "type": "connection",
  "message": "Connected to ReelCraft API"
}
```

#### Subscription Confirmation
```json
{
  "type": "subscribed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Subscribed to job ..."
}
```

#### Job Progress Update
```json
{
  "type": "job_progress",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "progress": 45,
  "message": "Downloading visual assets..."
}
```

#### Job Status Update
```json
{
  "type": "job_status",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": {
    "id": "...",
    "status": "completed",
    "progress": 100,
    "video_id": 5
  }
}
```

## Progress Stages

The video generation pipeline reports progress at these stages:

| Progress | Stage |
|----------|-------|
| 5% | Extracting article content |
| 10% | Article content extracted |
| 15% | Generating video script |
| 25% | Script generated with N scenes |
| 30% | Generating voice-over audio |
| 50% | Audio generation completed |
| 55% | Downloading visual assets |
| 75% | Assets downloaded successfully |
| 80% | Composing video |
| 85% | Editing video with FFmpeg |
| 95% | Finalizing video |
| 100% | Video created successfully |

## Frontend Integration

The frontend has been updated to work with the job-based API:

1. **Job Creation**: POST to `/api/generate-video` returns a `job_id`
2. **WebSocket Subscription**: Subscribe to job updates via WebSocket
3. **Polling Fallback**: Poll `/api/jobs/{job_id}` every second as backup
4. **Progress Updates**: Real-time progress bar updates from WebSocket
5. **Completion Handling**: Fetch video details when job completes

## Usage Examples

### Python Client

```python
import asyncio
from job_manager import job_manager
from pipeline import pipeline

async def generate_video_job(job_id, progress_callback, url):
    """Video generation job."""
    result = await pipeline(url, progress_callback=progress_callback)
    return result

async def main():
    # Create job
    job_id = await job_manager.create_job(
        generate_video_job,
        url="https://example.com/article"
    )

    print(f"Job created: {job_id}")

    # Check status
    while True:
        status = await job_manager.get_job_status(job_id)
        print(f"Status: {status['status']} - {status['progress']}%")

        if status['status'] in ['completed', 'failed', 'cancelled']:
            break

        await asyncio.sleep(1)

asyncio.run(main())
```

### JavaScript Client

```javascript
// Create job
const response = await fetch('/api/generate-video', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: 'https://example.com/article' })
});

const { job_id } = await response.json();

// Subscribe to updates
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onopen = () => {
  ws.send(JSON.stringify({ subscribe: job_id }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'job_progress') {
    console.log(`Progress: ${data.progress}% - ${data.message}`);
  }

  if (data.type === 'job_status' && data.status.status === 'completed') {
    console.log('Video completed!', data.status.video_id);
  }
};
```

## Benefits Over Previous System

### Before (Synchronous)
- ❌ API requests blocked until video generated (30-60 seconds)
- ❌ No way to track multiple generations
- ❌ Lost progress if client disconnected
- ❌ No job history or metadata storage
- ❌ Difficult to scale

### After (Asynchronous with Jobs)
- ✅ Instant API response with job ID
- ✅ Track multiple concurrent generations
- ✅ Reconnect to job progress anytime
- ✅ Full job history in database
- ✅ Easy to scale horizontally
- ✅ Job cancellation support
- ✅ Better error handling and recovery
- ✅ Persistent storage of video metadata

## Testing

Run the test suite:
```bash
uv run python test_job_system.py
```

This tests:
- Job creation and execution
- Progress callbacks
- Database operations
- Job cancellation

## Dependencies

New dependencies added:
- `sqlalchemy>=2.0.0` - ORM for database
- `aiosqlite>=0.19.0` - Async SQLite driver
- `greenlet>=3.0.0` - Required by SQLAlchemy async

## Database File

The SQLite database is stored at:
```
./reelcraft.db
```

To inspect the database:
```bash
sqlite3 reelcraft.db
.tables
SELECT * FROM jobs;
SELECT * FROM videos;
```

## Future Enhancements

Potential improvements:
1. Add Redis for distributed job queue (multi-server support)
2. Implement job priority levels
3. Add scheduled/recurring jobs
4. Job retry logic with exponential backoff
5. Job dependencies (chain jobs together)
6. Email notifications on completion
7. Export job metrics to monitoring tools
8. Video thumbnail generation
9. Automatic old job cleanup
10. Job history analytics dashboard
