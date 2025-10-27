// Configuration
const API_BASE_URL = window.location.origin;
const WS_URL = `ws://${window.location.host}/ws`;

// DOM Elements
const articleUrlInput = document.getElementById('article-url');
const generateBtn = document.getElementById('generate-btn');
const progressContainer = document.getElementById('progress-container');
const progressText = document.getElementById('progress-text');
const progressPercentage = document.getElementById('progress-percentage');
const progressFill = document.querySelector('.progress-fill');
const resultContainer = document.getElementById('result-container');
const resultVideo = document.getElementById('result-video');
const downloadBtn = document.getElementById('download-btn');
const generateAnotherBtn = document.getElementById('generate-another-btn');
const errorContainer = document.getElementById('error-container');
const errorMessage = document.querySelector('.error-message');
const tryAgainBtn = document.getElementById('try-again-btn');
const videoList = document.getElementById('video-list');

// WebSocket connection
let ws = null;
let currentJobId = null;

// Connect to WebSocket
function connectWebSocket() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        console.log('WebSocket connected');

        // Re-subscribe to job if there was one active
        if (currentJobId) {
            subscribeToJob(currentJobId);
        }
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'connection') {
            console.log(data.message);
        } else if (data.type === 'progress') {
            updateProgress(data.message, 50);
        } else if (data.type === 'job_progress') {
            updateProgress(data.message, data.progress);
        } else if (data.type === 'subscribed') {
            console.log(data.message);
        } else if (data.type === 'job_status') {
            handleJobStatus(data.status);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected. Reconnecting...');
        setTimeout(connectWebSocket, 3000);
    };
}

// Subscribe to job updates
function subscribeToJob(jobId) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ subscribe: jobId }));
        currentJobId = jobId;
    }
}

// Initialize WebSocket connection
connectWebSocket();

// Update progress display
function updateProgress(message, progress = null) {
    progressText.textContent = message;

    const percentageSpan = progressPercentage.querySelector('span');

    if (progress !== null) {
        progressFill.style.width = `${progress}%`;
        if (percentageSpan) {
            percentageSpan.textContent = `${progress}%`;
        }
    } else {
        // Animate progress bar incrementally
        const currentWidth = parseInt(progressFill.style.width) || 0;
        const newWidth = Math.min(currentWidth + 15, 90);
        progressFill.style.width = `${newWidth}%`;
        if (percentageSpan) {
            percentageSpan.textContent = `${newWidth}%`;
        }
    }
}

// Handle job status updates
async function handleJobStatus(status) {
    if (status.status === 'completed' && status.video_id) {
        // Show result using video ID
        showResult(status.video_id);
        loadVideos();
        currentJobId = null;
    } else if (status.status === 'failed') {
        // More user-friendly error messages
        let errorMsg = status.error_message || 'Video generation failed';

        // Check for common errors and provide helpful messages
        if (errorMsg.includes('Server disconnected') || errorMsg.includes('ServerDisconnectedError')) {
            errorMsg = 'Connection to AI service was interrupted. This might be due to high load. Please try again.';
        } else if (errorMsg.includes('rate limit') || errorMsg.includes('quota')) {
            errorMsg = 'API rate limit reached. Please wait a moment and try again.';
        } else if (errorMsg.includes('timeout')) {
            errorMsg = 'Request timed out. Please check your internet connection and try again.';
        }

        showError(errorMsg);
        currentJobId = null;
    } else if (status.status === 'cancelled') {
        showError('Job was cancelled');
        currentJobId = null;
    }
}

// Fetch video by ID
async function fetchVideoById(videoId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/videos`);
        const data = await response.json();
        return data.videos.find(v => v.id === videoId);
    } catch (error) {
        console.error('Error fetching video:', error);
        return null;
    }
}

// Poll job status
async function pollJobStatus(jobId) {
    const maxAttempts = 180; // 3 minutes with 1 second interval
    let attempts = 0;

    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
            const status = await response.json();

            if (status.status === 'completed') {
                clearInterval(pollInterval);
                await handleJobStatus(status);
            } else if (status.status === 'failed' || status.status === 'cancelled') {
                clearInterval(pollInterval);
                await handleJobStatus(status);
            }

            attempts++;
            if (attempts >= maxAttempts) {
                clearInterval(pollInterval);
                showError('Job timed out. Please check job status manually.');
            }
        } catch (error) {
            console.error('Error polling job status:', error);
        }
    }, 1000);
}

// Reset UI to initial state
function resetUI() {
    progressContainer.classList.add('hidden');
    resultContainer.classList.add('hidden');
    errorContainer.classList.add('hidden');
    progressFill.style.width = '0%';
    const percentageSpan = progressPercentage.querySelector('span');
    if (percentageSpan) {
        percentageSpan.textContent = '0%';
    }
    articleUrlInput.value = '';
    generateBtn.disabled = false;
    currentJobId = null;
}

// Show error
function showError(message) {
    errorMessage.textContent = message;
    errorContainer.classList.remove('hidden');
    progressContainer.classList.add('hidden');
    generateBtn.disabled = false;
}

// Show result
function showResult(videoId) {
    progressFill.style.width = '100%';
    setTimeout(() => {
        progressContainer.classList.add('hidden');
        resultContainer.classList.remove('hidden');
        resultVideo.src = `${API_BASE_URL}/api/videos/${videoId}/file`;
        downloadBtn.onclick = () => downloadVideo(videoId);
        generateBtn.disabled = false;
    }, 500);
}

// Generate video
async function generateVideo() {
    const url = articleUrlInput.value.trim();

    if (!url) {
        showError('Please enter a valid article URL');
        return;
    }

    try {
        // Reset UI
        errorContainer.classList.add('hidden');
        resultContainer.classList.add('hidden');
        progressContainer.classList.remove('hidden');
        progressFill.style.width = '5%';
        progressText.textContent = 'Creating video generation job...';
        generateBtn.disabled = true;

        // Make API request to create job
        const response = await fetch(`${API_BASE_URL}/api/generate-video`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to create video generation job');
        }

        const jobId = data.job_id;

        // Check if video already exists (instant completion)
        if (data.status === 'completed') {
            progressFill.style.width = '100%';
            const percentageSpan = progressPercentage.querySelector('span');
            if (percentageSpan) {
                percentageSpan.textContent = '100%';
            }
            progressText.textContent = '✨ Video already exists! Loading from cache...';

            // Get the job status to find video_id
            const statusResponse = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
            const jobStatus = await statusResponse.json();

            if (jobStatus.video_id) {
                // Small delay for UX (show the cache message)
                setTimeout(() => {
                    showResult(jobStatus.video_id);
                    loadVideos();
                }, 1000);
            }
        } else {
            // New video generation
            // Subscribe to job updates via WebSocket
            subscribeToJob(jobId);

            // Also poll for updates as fallback
            pollJobStatus(jobId);

            progressText.textContent = 'Job created. Waiting for processing...';
        }

    } catch (error) {
        console.error('Error:', error);
        showError(error.message || 'An error occurred while generating the video');
    }
}

// Download video
function downloadVideo(videoId) {
    const link = document.createElement('a');
    link.href = `${API_BASE_URL}/api/videos/${videoId}/file`;
    link.download = '';  // Let server set filename
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Format file size
function formatFileSize(mb) {
    return `${mb} MB`;
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Load videos
async function loadVideos() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/videos`);
        const data = await response.json();

        if (data.videos.length === 0) {
            videoList.innerHTML = '<p class="loading">No videos yet. Generate your first video!</p>';
            return;
        }

        videoList.innerHTML = data.videos.map(video => `
            <div class="video-card">
                <video src="${API_BASE_URL}/api/videos/${video.id}/file" controls></video>
                <div class="video-card-info">
                    <h4>${video.title}</h4>
                    <div class="video-card-meta">
                        <div>${formatDate(video.created_at)}</div>
                        <div>${video.size_mb ? formatFileSize(video.size_mb) : 'N/A'}</div>
                    </div>
                    <div class="video-card-actions">
                        <button class="btn btn-secondary" onclick="downloadVideo(${video.id})">
                            Download
                        </button>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading videos:', error);
        videoList.innerHTML = '<p class="loading">Error loading videos</p>';
    }
}

// Event listeners
generateBtn.addEventListener('click', generateVideo);
generateAnotherBtn.addEventListener('click', resetUI);
tryAgainBtn.addEventListener('click', resetUI);

articleUrlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        generateVideo();
    }
});

// Load videos on page load
document.addEventListener('DOMContentLoaded', () => {
    loadVideos();
});
