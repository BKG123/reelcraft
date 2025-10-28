# Storage Location Guide

This document explains how video storage is managed in ReelCraft, including local and cloud storage options.

## Overview

ReelCraft now tracks where videos are stored (local vs cloud) and allows filtering by storage location.

## Database Schema

The `videos` table includes a `storage_location` field:

```sql
storage_location TEXT NOT NULL DEFAULT 'LOCAL'  -- Values: 'LOCAL' or 'CLOUD'
```

### Storage Location Enum

```python
class StorageLocation(enum.Enum):
    LOCAL = "local"  # Video stored in local filesystem
    CLOUD = "cloud"  # Video stored in cloud (R2, S3, etc.)
```

## Configuration

### Local Storage Only

Set in your `.env` file:

```bash
R2_ENABLED=false
```

With this setting:
- Videos are stored in `assets/temp/outputs/`
- Database records have `storage_location='LOCAL'`
- Videos are served via `/api/videos/{video_id}/file` endpoint

### Cloud Storage (Cloudflare R2)

Set in your `.env` file:

```bash
R2_ENABLED=true
R2_ENDPOINT_URL=https://your-account-id.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your-access-key
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET_NAME=reelcraft-videos
R2_PUBLIC_URL=https://videos.yourdomain.com  # Optional custom domain
```

With this setting:
- Videos are uploaded to Cloudflare R2 after generation
- Database records have `storage_location='CLOUD'`
- Videos are served by redirecting to the cloud URL

## API Endpoints

### List All Videos

```bash
GET /api/videos
```

### Filter Videos by Storage Location

```bash
# Get only local videos
GET /api/videos?storage_location=local

# Get only cloud videos
GET /api/videos?storage_location=cloud
```

### Get Video File

```bash
GET /api/videos/{video_id}/file
```

This endpoint automatically:
- Returns the local file if `storage_location='LOCAL'`
- Redirects to cloud URL if `storage_location='CLOUD'`

## Database Management

### Migration Script

To add the `storage_location` field to an existing database:

```bash
python scripts/migrate_add_storage_location.py
```

This script:
1. Adds the `storage_location` column
2. Sets it to `'CLOUD'` for videos with URLs starting with `http://` or `https://`
3. Sets it to `'LOCAL'` for all other videos

### Fix Storage Location Case

If you need to fix the case (lowercase to uppercase):

```bash
python scripts/fix_storage_case.py
```

### Add Existing Videos

To add videos from the outputs folder to the database:

```bash
python scripts/add_existing_video.py
```

## Current Database State

```
Total videos: 3
- LOCAL: 1 video
- CLOUD: 2 videos
```

### Videos in Database

1. **ID: 1** - "Unlock Your Coding Superpowers with Claude Code!" (CLOUD)
2. **ID: 2** - "Unlock Your AI Coding Agent's Full Potential!" (CLOUD)
3. **ID: 3** - "How ChatGPT Actually Works (The Simple Explanation)" (LOCAL)
   - Source: https://medium.com/data-science-at-microsoft/how-large-language-models-work-91c362f5b78f
   - File: `assets/temp/outputs/how_chatgpt_actually_works_(the_simple_explanation).mp4`
   - Size: 12.22 MB
   - Duration: 91.61 seconds

## Testing

Test storage filtering with:

```bash
PYTHONPATH=/Users/bejayketanguin/Documents/Projects/reelcraft .venv/bin/python scripts/test_storage_filter.py
```

## Implementation Details

### Video Creation Flow

1. **Generate Video** - Pipeline creates video in `assets/temp/outputs/`
2. **Cloud Upload** (if enabled):
   - Upload to R2
   - Set `storage_location='CLOUD'`
   - Store cloud URL in `file_path`
3. **Local Storage** (if cloud disabled or upload fails):
   - Set `storage_location='LOCAL'`
   - Store relative path in `file_path`
4. **Database Entry** - Save video metadata with storage location

### Storage Manager

The `StorageManager` class ([services/storage.py](services/storage.py)) handles:

- Checking if cloud storage is enabled: `storage_manager.is_enabled()`
- Uploading videos: `await storage_manager.upload_video(local_path, video_id)`
- Deleting videos: `await storage_manager.delete_video(object_key)`
- Generating video URLs: `storage_manager.get_video_url(video_id, filename)`

### API Integration

The API ([services/api.py](services/api.py)) automatically:

1. Sets `storage_location` when creating video records
2. Filters videos by storage location in the list endpoint
3. Serves local files or redirects to cloud URLs based on storage location

## Querying Videos

### Using SQLAlchemy

```python
from services.database import async_session, Video, StorageLocation
from sqlalchemy import select

# Get all local videos
async with async_session() as session:
    result = await session.execute(
        select(Video)
        .where(Video.storage_location == StorageLocation.LOCAL)
        .order_by(Video.created_at.desc())
    )
    local_videos = result.scalars().all()
```

### Using SQL

```sql
-- Get all local videos
SELECT * FROM videos WHERE storage_location = 'LOCAL';

-- Get all cloud videos
SELECT * FROM videos WHERE storage_location = 'CLOUD';

-- Summary
SELECT storage_location, COUNT(*) FROM videos GROUP BY storage_location;
```

## Best Practices

1. **Development**: Use `R2_ENABLED=false` for local development
2. **Production**: Use `R2_ENABLED=true` with proper cloud credentials
3. **Filtering**: Use `?storage_location=local` to get only locally stored videos for recent testing
4. **Migration**: Always run migration scripts before deploying schema changes
5. **Cleanup**: Use storage location to identify which files can be safely deleted from local storage
