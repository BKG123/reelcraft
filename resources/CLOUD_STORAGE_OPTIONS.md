# Cloud Storage Options for ReelCraft Videos

## Free Options Comparison

### 1. **Cloudflare R2** ⭐ RECOMMENDED
- **Free Tier**: 10 GB storage, 1 million Class A operations/month
- **Bandwidth**: FREE egress (no data transfer costs!)
- **API**: S3-compatible
- **Speed**: Global CDN, very fast
- **Cost after free**: $0.015/GB/month storage
- **Why best**: Zero egress fees + global CDN

### 2. **Backblaze B2**
- **Free Tier**: 10 GB storage, 1 GB/day download
- **Bandwidth**: First 3x storage is free egress
- **API**: S3-compatible
- **Cost**: $0.005/GB/month storage, $0.01/GB egress after free tier
- **Why good**: Cheapest storage, generous free tier

### 3. **AWS S3** (with CloudFront)
- **Free Tier**: 5 GB storage (12 months), 20,000 GET requests
- **Bandwidth**: 50 GB/month via CloudFront (12 months)
- **API**: Native S3
- **Cost**: $0.023/GB/month after free tier
- **Why okay**: Limited free tier, gets expensive

### 4. **Google Cloud Storage**
- **Free Tier**: 5 GB storage (always free for US regions)
- **Bandwidth**: 1 GB/month egress to Americas
- **API**: GCS API
- **Cost**: $0.020/GB/month storage
- **Why okay**: Limited bandwidth

### 5. **Supabase Storage**
- **Free Tier**: 1 GB storage, 2 GB bandwidth/month
- **Speed**: Edge network
- **API**: Simple REST API
- **Why limited**: Small free tier

## Recommendation: Cloudflare R2

**Pros:**
- ✅ S3-compatible API (easy integration)
- ✅ FREE egress (unlimited video streaming!)
- ✅ Global CDN built-in
- ✅ 10 GB free storage
- ✅ Fast performance
- ✅ Easy setup

**Cons:**
- ⚠️ Requires Cloudflare account
- ⚠️ Newer service (but stable)

## Implementation Plan

### Step 1: Setup R2
```bash
# 1. Create Cloudflare account (free)
# 2. Go to R2 dashboard
# 3. Create bucket: "reelcraft-videos"
# 4. Generate API credentials
```

### Step 2: Install Dependencies
```bash
uv add boto3  # S3-compatible client
```

### Step 3: Environment Variables
```env
# Cloudflare R2
R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=reelcraft-videos
R2_PUBLIC_URL=https://videos.yourdomain.com  # Custom domain or R2.dev URL
```

### Step 4: Upload After Generation
```python
# After video is generated:
1. Upload to R2
2. Get public URL
3. Store URL in database
4. Delete local file (optional)
5. Serve video from R2 URL
```

## Cost Estimation

### Scenario: 100 videos/month, 50 MB each

**Cloudflare R2:**
- Storage: 5 GB used
- Cost: $0 (under 10 GB free tier)
- Bandwidth: Unlimited views
- **Total: $0/month** ✅

**Backblaze B2:**
- Storage: 5 GB used
- Cost: $0 (under 10 GB free tier)
- Bandwidth: ~150 GB/month (100 videos × 30 views × 50 MB)
- Cost: $1.50 egress
- **Total: ~$1.50/month**

**AWS S3 + CloudFront:**
- Storage: 5 GB
- Cost: $0.12/month
- Bandwidth: 150 GB (after 50 GB free)
- Cost: $10-15/month
- **Total: ~$15/month** ❌

## Alternative: Keep Local + Cleanup

If you don't want cloud storage yet:
1. ✅ Automatic cleanup of temp assets (audio, images, raw videos)
2. ✅ Keep only final output videos locally
3. ✅ Implement old video cleanup (e.g., delete videos older than 30 days)
4. ⚠️ Limited by local disk space
5. ⚠️ No CDN, slower for users far from server
