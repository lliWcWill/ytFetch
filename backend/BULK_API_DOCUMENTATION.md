# Bulk API Documentation

This document provides comprehensive documentation for the ytFetch Bulk API endpoints, which enable processing of YouTube playlists and channels for batch transcription operations.

## Overview

The Bulk API allows users to:
- Analyze playlists and channels before processing
- Create bulk transcription jobs with customizable settings
- Monitor job progress in real-time
- Download ZIP files containing all completed transcripts
- Manage job lifecycle (start, cancel, delete)
- List and filter user jobs with pagination

## Authentication

All bulk operations require authentication (except analysis which is optional):

```http
Authorization: Bearer user_id:tier
```

Example:
```http
Authorization: Bearer john_doe:pro
```

For development/testing, you can use anonymous access by omitting the Authorization header, which defaults to free tier limits.

## User Tiers and Limits

| Tier       | Max Videos/Job | Concurrent Jobs | Daily Limit | Rate Limit Delay |
|------------|----------------|-----------------|-------------|-------------------|
| Free       | 5              | 1               | 10          | 5.0s             |
| Basic      | 25             | 2               | 50          | 4.0s             |
| Pro        | 100            | 3               | 200         | 3.0s             |
| Enterprise | 500            | 5               | 1000        | 3.0s             |

## Rate Limiting

The API implements rate limiting to prevent abuse:

- **Analysis**: 10 requests/minute
- **Job Creation**: 5 requests/minute
- **Job Start**: 3 requests/minute
- **Job Cancel**: 5 requests/minute

Rate limit headers are included in responses when slowapi is properly configured.

## API Endpoints

### 1. Analyze Playlist/Channel

Analyze a YouTube playlist or channel to get metadata and check tier compatibility.

**Endpoint:** `POST /api/v1/bulk/analyze`

**Request Body:**
```json
{
  "url": "https://www.youtube.com/playlist?list=PLsyeobzWxl7poL9JTVyndKe62ieoN-MZ3",
  "max_videos": 10
}
```

**Response:**
```json
{
  "url": "https://www.youtube.com/playlist?list=PLsyeobzWxl7poL9JTVyndKe62ieoN-MZ3",
  "source_type": "playlist",
  "title": "Python Tutorial Playlist",
  "description": null,
  "total_videos": 25,
  "analyzed_videos": 10,
  "estimated_duration_hours": 12.5,
  "videos": [
    {
      "video_id": "dQw4w9WgXcQ",
      "title": "Introduction to Python",
      "duration": 1800,
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    }
  ],
  "tier_limits": {
    "max_videos_per_job": 100,
    "max_concurrent_jobs": 3,
    "rate_limit_delay": 3.0,
    "daily_limit": 200
  },
  "can_process_all": true
}
```

**Parameters:**
- `url` (required): YouTube playlist or channel URL
- `max_videos` (optional): Maximum number of videos to analyze

### 2. Create Bulk Job

Create a new bulk transcription job from a playlist or channel.

**Endpoint:** `POST /api/v1/bulk/create`

**Request Body:**
```json
{
  "url": "https://www.youtube.com/playlist?list=PLsyeobzWxl7poL9JTVyndKe62ieoN-MZ3",
  "transcript_method": "unofficial",
  "output_format": "txt",
  "max_videos": 50,
  "webhook_url": "https://example.com/webhook"
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "john_doe",
  "source_url": "https://www.youtube.com/playlist?list=PLsyeobzWxl7poL9JTVyndKe62ieoN-MZ3",
  "transcript_method": "unofficial",
  "output_format": "txt",
  "status": "pending",
  "total_videos": 25,
  "completed_videos": 0,
  "failed_videos": 0,
  "progress_percent": 0.0,
  "user_tier": "pro",
  "webhook_url": "https://example.com/webhook",
  "zip_available": false,
  "estimated_duration_minutes": 1.25,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "tier_limits": {
    "max_videos_per_job": 100,
    "max_concurrent_jobs": 3,
    "rate_limit_delay": 3.0,
    "daily_limit": 200
  }
}
```

**Parameters:**
- `url` (required): YouTube playlist or channel URL
- `transcript_method` (optional): "unofficial", "groq", or "openai" (default: "unofficial")
- `output_format` (optional): "txt", "srt", "vtt", or "json" (default: "txt")
- `max_videos` (optional): Maximum videos to process (respects tier limits)
- `webhook_url` (optional): URL for completion notifications

### 3. Get Job Status

Get detailed status and progress information for a specific job.

**Endpoint:** `GET /api/v1/bulk/jobs/{job_id}`

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "john_doe",
  "source_url": "https://www.youtube.com/playlist?list=PLsyeobzWxl7poL9JTVyndKe62ieoN-MZ3",
  "transcript_method": "unofficial",
  "output_format": "txt",
  "status": "processing",
  "total_videos": 25,
  "completed_videos": 15,
  "failed_videos": 2,
  "pending_videos": 8,
  "processing_videos": 0,
  "retry_videos": 0,
  "progress_percent": 60.0,
  "user_tier": "pro",
  "webhook_url": "https://example.com/webhook",
  "zip_available": false,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:45:00Z",
  "completed_at": null
}
```

### 4. List User Jobs

Get a paginated list of bulk jobs for the authenticated user.

**Endpoint:** `GET /api/v1/bulk/jobs?page=1&per_page=20&status=completed`

**Query Parameters:**
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Items per page, max 100 (default: 20)
- `status` (optional): Filter by job status

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "john_doe",
      "source_url": "https://www.youtube.com/playlist?list=PLsyeobzWxl7poL9JTVyndKe62ieoN-MZ3",
      "transcript_method": "unofficial",
      "output_format": "txt",
      "status": "completed",
      "total_videos": 25,
      "completed_videos": 23,
      "failed_videos": 2,
      "progress_percent": 92.0,
      "user_tier": "pro",
      "zip_available": true,
      "created_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T11:15:00Z"
    }
  ],
  "total_count": 5,
  "page": 1,
  "per_page": 20,
  "has_next": false
}
```

### 5. Start Job Processing

Start processing a bulk job that is in pending status.

**Endpoint:** `POST /api/v1/bulk/jobs/{job_id}/start`

**Response:**
```json
{
  "status": "accepted",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Job processing started successfully",
  "total_videos": 25
}
```

### 6. Cancel Job

Cancel a running or pending bulk job.

**Endpoint:** `POST /api/v1/bulk/jobs/{job_id}/cancel`

**Response:**
```json
{
  "status": "cancelled",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Job cancelled successfully",
  "completed_videos": 15
}
```

### 7. Download Job Results

Download a ZIP file containing all completed transcripts.

**Endpoint:** `GET /api/v1/bulk/jobs/{job_id}/download`

**Response:** Binary ZIP file with appropriate headers:
```http
Content-Type: application/zip
Content-Disposition: attachment; filename=bulk_transcripts_550e8400_20240115_113000.zip
```

The ZIP file contains:
- Individual transcript files named: `{video_title}_{video_id}.{format}`
- All files in the specified output format (txt, srt, vtt, json)

### 8. Delete Job

Delete a bulk job and all associated data permanently.

**Endpoint:** `DELETE /api/v1/bulk/jobs/{job_id}`

**Response:**
```json
{
  "status": "deleted",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Job deleted successfully"
}
```

## Job Status Values

| Status      | Description                                    |
|-------------|------------------------------------------------|
| pending     | Job created but not started                    |
| processing  | Job is actively processing videos              |
| completed   | All videos processed (may include failures)   |
| failed      | Job failed due to critical error              |
| cancelled   | Job was cancelled by user                      |
| paused      | Job processing is temporarily paused          |

## Task Status Values

| Status         | Description                                |
|----------------|--------------------------------------------|
| pending        | Task not yet started                       |
| processing     | Task currently being processed             |
| completed      | Task completed successfully                |
| failed         | Task failed and exceeded retry limit      |
| retry_pending  | Task failed but will be retried           |
| skipped        | Task was skipped (e.g., due to cancellation) |

## Transcript Methods

| Method     | Description                               | Speed | Accuracy |
|------------|-------------------------------------------|-------|----------|
| unofficial | Use existing YouTube captions/subtitles  | Fast  | Variable |
| groq       | AI transcription using Groq API          | Medium| High     |
| openai     | AI transcription using OpenAI Whisper    | Slow  | Highest  |

## Output Formats

| Format | Description                    | File Extension |
|--------|--------------------------------|----------------|
| txt    | Plain text transcript          | .txt           |
| srt    | SubRip subtitle format         | .srt           |
| vtt    | WebVTT subtitle format         | .vtt           |
| json   | JSON with timestamps/metadata  | .json          |

## Error Handling

The API returns standardized error responses:

```json
{
  "error": "rate_limited",
  "message": "Daily video processing limit exceeded for your tier",
  "details": {
    "tier": "free",
    "limit": 10
  },
  "status_code": 403
}
```

### Common Error Codes

| Status | Error Code              | Description                        |
|--------|------------------------|------------------------------------|
| 400    | invalid_url            | URL is not a valid playlist/channel |
| 400    | invalid_method         | Unsupported transcript method     |
| 401    | unauthorized           | Authentication required            |
| 403    | rate_limited           | Rate limit or tier limit exceeded |
| 403    | access_denied          | No access to requested resource    |
| 404    | job_not_found          | Job ID does not exist             |
| 429    | too_many_requests      | Rate limit exceeded               |
| 500    | internal_error         | Server error                      |

## Webhook Notifications

When a webhook URL is provided, the system sends POST requests on job completion:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "john_doe",
  "status": "completed",
  "total_videos": 25,
  "completed_videos": 23,
  "failed_videos": 2,
  "success_rate": 92.0,
  "zip_available": true,
  "completed_at": "2024-01-15T11:15:00Z"
}
```

## Code Examples

### Python Example

```python
import aiohttp
import asyncio

async def create_and_process_job():
    headers = {"Authorization": "Bearer user123:pro"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        # Create job
        job_data = {
            "url": "https://www.youtube.com/playlist?list=PLsyeobzWxl7poL9JTVyndKe62ieoN-MZ3",
            "transcript_method": "unofficial",
            "output_format": "txt",
            "max_videos": 10
        }
        
        async with session.post("http://localhost:8000/api/v1/bulk/create", json=job_data) as resp:
            job = await resp.json()
            job_id = job["job_id"]
        
        # Start processing
        async with session.post(f"http://localhost:8000/api/v1/bulk/jobs/{job_id}/start") as resp:
            start_result = await resp.json()
        
        # Monitor progress
        while True:
            async with session.get(f"http://localhost:8000/api/v1/bulk/jobs/{job_id}") as resp:
                status = await resp.json()
                
                print(f"Progress: {status['progress_percent']:.1f}%")
                
                if status['status'] == 'completed':
                    break
                
                await asyncio.sleep(10)
        
        # Download results
        if status['zip_available']:
            async with session.get(f"http://localhost:8000/api/v1/bulk/jobs/{job_id}/download") as resp:
                with open(f"results_{job_id}.zip", "wb") as f:
                    f.write(await resp.read())

asyncio.run(create_and_process_job())
```

### JavaScript Example

```javascript
const API_BASE = 'http://localhost:8000/api/v1/bulk';
const headers = {
    'Authorization': 'Bearer user123:pro',
    'Content-Type': 'application/json'
};

async function createAndProcessJob() {
    // Create job
    const jobResponse = await fetch(`${API_BASE}/create`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
            url: 'https://www.youtube.com/playlist?list=PLsyeobzWxl7poL9JTVyndKe62ieoN-MZ3',
            transcript_method: 'unofficial',
            output_format: 'txt',
            max_videos: 10
        })
    });
    
    const job = await jobResponse.json();
    const jobId = job.job_id;
    
    // Start processing
    await fetch(`${API_BASE}/jobs/${jobId}/start`, {
        method: 'POST',
        headers
    });
    
    // Monitor progress
    while (true) {
        const statusResponse = await fetch(`${API_BASE}/jobs/${jobId}`, { headers });
        const status = await statusResponse.json();
        
        console.log(`Progress: ${status.progress_percent.toFixed(1)}%`);
        
        if (status.status === 'completed') {
            break;
        }
        
        await new Promise(resolve => setTimeout(resolve, 10000));
    }
    
    // Download results
    if (status.zip_available) {
        const downloadResponse = await fetch(`${API_BASE}/jobs/${jobId}/download`, { headers });
        const blob = await downloadResponse.blob();
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `results_${jobId}.zip`;
        a.click();
    }
}
```

## Integration Notes

1. **Database Requirements**: The bulk API requires Supabase tables for job and task management
2. **Rate Limiting**: Implement slowapi middleware for production rate limiting
3. **Authentication**: Replace the placeholder auth system with your actual user management
4. **File Storage**: ZIP files are stored in the configured temp directory
5. **Background Processing**: Jobs run as async background tasks
6. **Error Recovery**: Failed tasks are automatically retried up to configured limits

## Performance Considerations

1. **Concurrent Jobs**: Limited by user tier to prevent resource exhaustion
2. **Rate Limiting**: Delays between video processing to respect YouTube's ToS
3. **Memory Usage**: Large playlists may require significant memory for metadata
4. **Storage**: ZIP files consume disk space and should be cleaned up periodically
5. **Network**: Multiple concurrent downloads may impact bandwidth

## Security Considerations

1. **Authentication**: Implement proper JWT or session-based authentication
2. **Authorization**: Verify user ownership of jobs before allowing access
3. **Rate Limiting**: Prevent abuse with both endpoint and user-based limits
4. **Input Validation**: All URLs and parameters are validated
5. **File Access**: ZIP downloads verify job ownership before serving files