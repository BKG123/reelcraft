# Storage & Cleanup Setup Guide

## Overview

ReelCraft generates temporary files during video generation:
- **Audio files** (~500KB each × 7-15 files = ~5-7 MB/video)
- **Images** (~2 MB each × 7-15 files = ~20 MB/video)
- **Raw videos** (~8 MB each × 7-15 files = ~80 MB/video)
- **Final video** (~40 MB each)

**Total: ~150 MB per video generated!**

## Solution: Automatic Cleanup + Cloud Storage

### ✅ Automatic Cleanup (Already Implemented)

After each successful video generation, temporary assets are automatically cleaned up:

```
Generation Complete
    ↓
Save final video to database
    ↓
Upload to cloud (if enabled)
    ↓
Delete temp files:
    - audio/*.wav (removed)
    - images/*.jpg (removed)
    - videos/*.mp4 (removed)
    - outputs/*.mp4 (kept locally or in cloud)
```

**Result:** ~110 MB saved per video!

### 🌩️ Cloud Storage Setup (Optional but Recommended)

#### Why Use Cloud Storage?

- ✅ Free CDN (fast video delivery globally)
- ✅ No local disk space issues
- ✅ Unlimited bandwidth (with Cloudflare R2)
- ✅ Videos survive server restarts/crashes
- ✅ Easy to scale

#### Option 1: Cloudflare R2 (Recommended - FREE)

**Step 1: Create Cloudflare Account**
1. Go to https://dash.cloudflare.com/sign-up
2. Sign up (free)

**Step 2: Enable R2**
1. In dashboard, click "R2" in sidebar
2. Click "Create bucket"
3. Name it: `reelcraft-videos`
4. Region: Automatic (or nearest to you)
5. Click "Create bucket"

**Step 3: Get API Credentials**
1. Go to R2 → Manage R2 API Tokens
2. Click "Create API Token"
3. Permissions: "Object Read & Write"
4. Apply to: Specific bucket → `reelcraft-videos`
5. Click "Create API Token"
6. Copy the credentials shown

**Step 4: Configure ReelCraft**

Add to your `.env` file:

```env
# Enable R2
R2_ENABLED=true

# Your R2 credentials (from step 3)
R2_ENDPOINT_URL=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_access_key_from_step_3
R2_SECRET_ACCESS_KEY=your_secret_key_from_step_3
R2_BUCKET_NAME=reelcraft-videos

# Public URL (R2.dev subdomain)
R2_PUBLIC_URL=https://pub-YOUR_ACCOUNT_ID.r2.dev/reelcraft-videos
```

**Step 5: Install boto3**

```bash
uv add boto3
```

**Step 6: Restart Server**

```bash
# Stop current server (Ctrl+C)
uv run python main.py
```

**Step 7: Test**

Generate a video - it should upload to R2 automatically!

Check in Cloudflare dashboard → R2 → reelcraft-videos → you should see:
```
videos/1/supercharge_your_coding_agents.mp4
```

#### Option 2: Keep Local Storage (Default)

If you don't want to set up cloud storage yet:

1. Leave `R2_ENABLED=false` in `.env`
2. Videos stored locally in `assets/temp/outputs/`
3. Temp assets still cleaned up automatically
4. Need to manage disk space manually

**Local Storage Management:**

```bash
# Check storage usage
du -sh assets/temp/*

# Clean old videos (older than 7 days)
python -c "from services.cleanup import cleanup_old_assets; cleanup_old_assets(7)"

# Get storage stats
python -c "from services.cleanup import get_storage_stats; print(get_storage_stats())"
```

## What Gets Cleaned Up?

### After Each Generation (Automatic):

✅ **Cleaned:**
- `assets/temp/audio/video_title_*.wav` - Voice-over files
- `assets/temp/images/video_title_*.jpg` - Downloaded images
- `assets/temp/videos/video_title_*.mp4` - Downloaded video clips

❌ **Kept:**
- `assets/temp/outputs/video_title.mp4` - Final video (unless uploaded to cloud)
- Database record with metadata

### Manual Cleanup Commands:

```python
# In Python shell or script:
from services.cleanup import *

# Clean specific video's assets
cleanup_generation_assets("My Video Title")

# Clean all assets older than 7 days
cleanup_old_assets(days=7)

# Clean failed generation (including partial output)
cleanup_failed_generation("Failed Video Title")

# Get storage statistics
stats = get_storage_stats()
print(f"Total storage: {stats['total']['size_mb']} MB")
print(f"Total files: {stats['total']['files']}")
```

## Cost Comparison

### Example: 100 videos/month, 40MB each

| Provider | Storage Cost | Bandwidth Cost | Total/Month |
|----------|--------------|----------------|-------------|
| **Cloudflare R2** | $0 (under 10GB free) | $0 (unlimited free!) | **$0** ✅ |
| **Local** | $0 | $0 | **$0** (but uses disk) |
| **Backblaze B2** | $0 | ~$1.50 | **$1.50** |
| **AWS S3** | $0.12 | ~$15 | **~$15** ❌ |

## Troubleshooting

### Videos not uploading to R2?

```bash
# Check logs
tail -f reelcraft.log | grep "R2"

# Common issues:
# 1. boto3 not installed: uv add boto3
# 2. Wrong credentials: double-check .env
# 3. Bucket doesn't exist: create in dashboard
# 4. R2_ENABLED not set to "true"
```

### Running out of disk space?

```bash
# Check current usage
du -sh assets/temp/*

# Clean old temp files
python -c "from services.cleanup import cleanup_old_assets; cleanup_old_assets(days=1)"

# Emergency: clean everything
rm -rf assets/temp/audio/* assets/temp/images/* assets/temp/videos/*
# (Final videos in outputs/ are preserved)
```

### Want to migrate existing videos to cloud?

```python
# Create migration script
import asyncio
from pathlib import Path
from services.database import async_session, Video
from services.storage import storage_manager
from sqlalchemy import select

async def migrate_videos():
    async with async_session() as session:
        result = await session.execute(select(Video))
        videos = result.scalars().all()

        for video in videos:
            local_path = Path(video.file_path)
            if local_path.exists():
                print(f"Uploading video {video.id}...")
                url = await storage_manager.upload_video(str(local_path), video.id)
                if url:
                    video.file_path = url
                    await session.commit()
                    print(f"✓ Uploaded: {url}")

asyncio.run(migrate_videos())
```

## Monitoring Storage

### API Endpoint (Coming Soon):

```
GET /api/storage/stats

Response:
{
  "audio": {"files": 0, "size_mb": 0.0},
  "images": {"files": 0, "size_mb": 0.0},
  "videos": {"files": 0, "size_mb": 0.0},
  "outputs": {"files": 5, "size_mb": 200.0},
  "total": {"files": 5, "size_mb": 200.0}
}
```

## Best Practices

1. ✅ **Enable automatic cleanup** (default, already done)
2. ✅ **Use cloud storage** for production (R2 recommended)
3. ✅ **Set up monitoring** to track storage usage
4. ✅ **Implement retention policy** (e.g., delete videos older than 90 days)
5. ✅ **Backup database** regularly (contains video metadata)

## Next Steps

1. Set up Cloudflare R2 (5 minutes)
2. Test with one video generation
3. Verify upload in R2 dashboard
4. Enjoy unlimited free video hosting! 🎉
