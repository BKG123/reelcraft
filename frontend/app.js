// Configuration
const API_BASE_URL = window.location.origin;
const WS_URL = `ws://${window.location.host}/ws`;

// DOM Elements
const articleUrlInput = document.getElementById('article-url');
const generateBtn = document.getElementById('generate-btn');
const progressContainer = document.getElementById('progress-container');
const progressText = document.getElementById('progress-text');
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

// Connect to WebSocket
function connectWebSocket() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'progress') {
            updateProgress(data.message);
        } else if (data.type === 'connection') {
            console.log(data.message);
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

// Initialize WebSocket connection
connectWebSocket();

// Update progress display
function updateProgress(message) {
    progressText.textContent = message;

    // Animate progress bar
    const currentWidth = parseInt(progressFill.style.width) || 0;
    const newWidth = Math.min(currentWidth + 15, 90);
    progressFill.style.width = `${newWidth}%`;
}

// Reset UI to initial state
function resetUI() {
    progressContainer.classList.add('hidden');
    resultContainer.classList.add('hidden');
    errorContainer.classList.add('hidden');
    progressFill.style.width = '0%';
    articleUrlInput.value = '';
    generateBtn.disabled = false;
}

// Show error
function showError(message) {
    errorMessage.textContent = message;
    errorContainer.classList.remove('hidden');
    progressContainer.classList.add('hidden');
    generateBtn.disabled = false;
}

// Show result
function showResult(videoPath) {
    progressFill.style.width = '100%';
    setTimeout(() => {
        progressContainer.classList.add('hidden');
        resultContainer.classList.remove('hidden');
        resultVideo.src = `${API_BASE_URL}/${videoPath}`;
        downloadBtn.onclick = () => downloadVideo(videoPath);
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
        progressFill.style.width = '10%';
        progressText.textContent = 'Starting video generation...';
        generateBtn.disabled = true;

        // Make API request
        const response = await fetch(`${API_BASE_URL}/api/generate-video`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to generate video');
        }

        // Show result
        showResult(data.video_path);

        // Refresh video list
        loadVideos();

    } catch (error) {
        console.error('Error:', error);
        showError(error.message || 'An error occurred while generating the video');
    }
}

// Download video
function downloadVideo(videoPath) {
    const fileName = videoPath.split('/').pop();
    const link = document.createElement('a');
    link.href = `${API_BASE_URL}/${videoPath}`;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Format file size
function formatFileSize(mb) {
    return `${mb} MB`;
}

// Format date
function formatDate(timestamp) {
    const date = new Date(timestamp * 1000);
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
                <video src="${API_BASE_URL}/${video.path}" controls></video>
                <div class="video-card-info">
                    <h4>${video.filename}</h4>
                    <div class="video-card-meta">
                        <div>${formatDate(video.created_at)}</div>
                        <div>${formatFileSize(video.size_mb)}</div>
                    </div>
                    <div class="video-card-actions">
                        <button class="btn btn-secondary" onclick="downloadVideo('${video.path}')">
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
