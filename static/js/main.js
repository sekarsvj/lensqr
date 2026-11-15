/**
 * LensQR Photo & Video QR Generator - Core Client Application
 * Strictly Vanilla JavaScript (No Node.js, npm, or external JS frameworks)
 */

// Global State
let selectedPhotoFile = null;
let selectedVideoFile = null;
let pendingDeleteMediaId = null;
let pendingDeleteToken = null;

// Helper: Get CSRF Token from meta tag
function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

// Helper: Format bytes to human readable format
function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Helper: Toast Notifications
function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let iconSvg = '';
    if (type === 'success') {
        iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="18" height="18"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    } else if (type === 'error') {
        iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="18" height="18"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
    } else {
        iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="18" height="18"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `${iconSvg}<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 250);
    }, duration);
}

// Local Storage Manager for Generated QR Codes
const LOCAL_STORAGE_KEY = 'lensqr_qr_history';
const LEGACY_STORAGE_KEY = 'coralgenz_qr_history';

function getLocalHistory() {
    try {
        const stored = localStorage.getItem(LOCAL_STORAGE_KEY) ||
                       localStorage.getItem(LEGACY_STORAGE_KEY);
        return stored ? JSON.parse(stored) : [];
    } catch (e) {
        return [];
    }
}

function saveMediaToLocalStorage(item) {
    try {
        let history = getLocalHistory();
        history = history.filter(h => h.mediaId !== item.mediaId);
        history.unshift(item);
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(history));
        updateNavBadge();
    } catch (e) {
        console.error('Failed to save to local storage', e);
    }
}

function removeFromLocalStorage(mediaId) {
    try {
        let history = getLocalHistory();
        history = history.filter(h => h.mediaId !== mediaId);
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(history));
        updateNavBadge();
    } catch (e) {
        console.error('Failed to remove from local storage', e);
    }
}

function updateNavBadge() {
    const badge = document.getElementById('myCodesBadge');
    if (!badge) return;
    const history = getLocalHistory();
    if (history.length > 0) {
        badge.textContent = history.length;
        badge.style.display = 'inline-block';
    } else {
        badge.style.display = 'none';
    }
}

// Mode Switcher (Photo vs Video)
function initModeSwitcher() {
    const tabPhoto = document.getElementById('tabPhoto');
    const tabVideo = document.getElementById('tabVideo');
    const panelPhoto = document.getElementById('panelPhoto');
    const panelVideo = document.getElementById('panelVideo');

    if (!tabPhoto || !tabVideo) return;

    function switchMode(mode) {
        if (mode === 'photo') {
            tabPhoto.classList.add('active');
            tabVideo.classList.remove('active');
            panelPhoto.style.display = 'block';
            panelVideo.style.display = 'none';
            window.location.hash = 'photo-section';
        } else {
            tabVideo.classList.add('active');
            tabPhoto.classList.remove('active');
            panelVideo.style.display = 'block';
            panelPhoto.style.display = 'none';
            window.location.hash = 'video-section';
        }
    }

    tabPhoto.addEventListener('click', () => switchMode('photo'));
    tabVideo.addEventListener('click', () => switchMode('video'));

    if (window.location.hash === '#video-section') {
        switchMode('video');
    }
}

// Single Photo Upload Management
function initPhotoUpload() {
    const dropzone = document.getElementById('photoDropzone');
    const fileInput = document.getElementById('photoFileInput');
    const browseBtn = document.getElementById('photoBrowseBtn');
    const previewCard = document.getElementById('photoPreviewCard');
    const previewImg = document.getElementById('photoPreviewElement');
    const photoFileName = document.getElementById('photoFileName');
    const photoFileSize = document.getElementById('photoFileSize');
    const removeBtn = document.getElementById('removePhotoBtn');
    const replaceBtn = document.getElementById('replacePhotoBtn');
    const submitBtn = document.getElementById('submitPhotoBtn');
    const form = document.getElementById('photoUploadForm');

    if (!dropzone || !fileInput || !form) return;

    browseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        fileInput.click();
    });

    if (replaceBtn) {
        replaceBtn.addEventListener('click', () => fileInput.click());
    }

    if (removeBtn) {
        removeBtn.addEventListener('click', clearPhotoSelection);
    }

    // Drag & Drop
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handlePhotoFile(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handlePhotoFile(e.target.files[0]);
        }
    });

    function handlePhotoFile(file) {
        const validExtensions = ['jpg', 'jpeg', 'png', 'webp'];
        const maxPhotoSize = 25 * 1024 * 1024; // 25MB
        const ext = file.name.split('.').pop().toLowerCase();

        if (!validExtensions.includes(ext)) {
            showToast('Unsupported format. Only JPG, PNG, and WEBP photographs are allowed.', 'error');
            return;
        }

        if (file.size > maxPhotoSize) {
            showToast('Photograph exceeds maximum size of 25MB.', 'error');
            return;
        }

        selectedPhotoFile = file;
        photoFileName.textContent = file.name;
        photoFileSize.textContent = formatBytes(file.size);

        if (previewImg.src && previewImg.src.startsWith('blob:')) {
            URL.revokeObjectURL(previewImg.src);
        }
        previewImg.src = URL.createObjectURL(file);
        previewCard.style.display = 'block';
        dropzone.style.display = 'none';
        submitBtn.disabled = false;
    }

    function clearPhotoSelection() {
        if (previewImg.src && previewImg.src.startsWith('blob:')) {
            URL.revokeObjectURL(previewImg.src);
            previewImg.src = '';
        }
        selectedPhotoFile = null;
        fileInput.value = '';
        previewCard.style.display = 'none';
        dropzone.style.display = 'block';
        submitBtn.disabled = true;
    }

    // Photo Form Submission via XHR for upload progress
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        if (!selectedPhotoFile) {
            showToast('Please select a photograph.', 'error');
            return;
        }

        const formData = new FormData(form);
        formData.set('file', selectedPhotoFile);

        const progressWrapper = document.getElementById('photoProgressWrapper');
        const progressFill = document.getElementById('photoProgressFill');
        const progressPercent = document.getElementById('photoProgressPercent');
        const progressStatus = document.getElementById('photoProgressStatus');

        progressWrapper.style.display = 'block';
        progressStatus.textContent = 'Uploading photograph & generating QR...';
        submitBtn.disabled = true;
        submitBtn.querySelector('span').textContent = 'Uploading...';

        const xhr = new XMLHttpRequest();
        xhr.open('POST', form.action, true);
        xhr.setRequestHeader('X-CSRFToken', getCsrfToken());

        xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                progressFill.style.width = `${percent}%`;
                progressPercent.textContent = `${percent}%`;
                if (percent === 100) {
                    progressStatus.textContent = 'Generating print-ready QR code...';
                }
            }
        };

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const res = JSON.parse(xhr.responseText);
                    if (res.success) {
                        saveMediaToLocalStorage({
                            mediaId: res.media_id,
                            creatorToken: res.creator_token,
                            title: res.title,
                            originalName: selectedPhotoFile.name,
                            mediaType: 'photo',
                            sizeFormatted: formatBytes(selectedPhotoFile.size),
                            createdAt: new Date().toISOString(),
                            qrUrl: res.qr_url,
                            mediaUrl: res.media_url
                        });
                        window.location.href = res.result_url;
                    } else {
                        showToast(res.error || 'Photo upload failed.', 'error');
                        resetPhotoUploadUi();
                    }
                } catch (err) {
                    showToast('Server response could not be parsed.', 'error');
                    resetPhotoUploadUi();
                }
            } else {
                try {
                    const errRes = JSON.parse(xhr.responseText);
                    showToast(errRes.error || `Upload rejected (${xhr.status}).`, 'error');
                } catch (e) {
                    showToast(`Upload failed with status ${xhr.status}.`, 'error');
                }
                resetPhotoUploadUi();
            }
        };

        xhr.onerror = () => {
            showToast('Network connection error during upload.', 'error');
            resetPhotoUploadUi();
        };

        xhr.send(formData);
    });

    function resetPhotoUploadUi() {
        const progressWrapper = document.getElementById('photoProgressWrapper');
        if (progressWrapper) progressWrapper.style.display = 'none';
        submitBtn.disabled = false;
        submitBtn.querySelector('span').textContent = 'Generate Photo QR Code';
    }
}

// Single Video Upload Management
function initVideoUpload() {
    const dropzone = document.getElementById('videoDropzone');
    const fileInput = document.getElementById('videoFileInput');
    const browseBtn = document.getElementById('videoBrowseBtn');
    const previewCard = document.getElementById('videoPreviewCard');
    const previewPlayer = document.getElementById('videoPreviewElement');
    const videoFileName = document.getElementById('videoFileName');
    const videoFileSize = document.getElementById('videoFileSize');
    const removeBtn = document.getElementById('removeVideoBtn');
    const replaceBtn = document.getElementById('replaceVideoBtn');
    const submitBtn = document.getElementById('submitVideoBtn');
    const form = document.getElementById('videoUploadForm');

    if (!dropzone || !fileInput || !form) return;

    browseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        fileInput.click();
    });

    if (replaceBtn) {
        replaceBtn.addEventListener('click', () => fileInput.click());
    }

    if (removeBtn) {
        removeBtn.addEventListener('click', clearVideoSelection);
    }

    // Drag & Drop
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleVideoFile(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleVideoFile(e.target.files[0]);
        }
    });

    function handleVideoFile(file) {
        const validExtensions = ['mp4', 'mov', 'webm'];
        const maxVideoSize = 100 * 1024 * 1024; // 100MB
        const ext = file.name.split('.').pop().toLowerCase();

        if (!validExtensions.includes(ext)) {
            showToast('Invalid format. Only MP4, MOV, and WebM videos are supported.', 'error');
            return;
        }

        if (file.size > maxVideoSize) {
            showToast('Video exceeds maximum size of 100MB.', 'error');
            return;
        }

        selectedVideoFile = file;
        videoFileName.textContent = file.name;
        videoFileSize.textContent = formatBytes(file.size);

        if (previewPlayer.src && previewPlayer.src.startsWith('blob:')) {
            URL.revokeObjectURL(previewPlayer.src);
        }
        previewPlayer.src = URL.createObjectURL(file);
        previewCard.style.display = 'block';
        dropzone.style.display = 'none';
        submitBtn.disabled = false;
    }

    function clearVideoSelection() {
        if (previewPlayer.src && previewPlayer.src.startsWith('blob:')) {
            URL.revokeObjectURL(previewPlayer.src);
            previewPlayer.src = '';
        }
        selectedVideoFile = null;
        fileInput.value = '';
        previewCard.style.display = 'none';
        dropzone.style.display = 'block';
        submitBtn.disabled = true;
    }

    // Video Form Submission via XHR
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        if (!selectedVideoFile) {
            showToast('Please select a video file.', 'error');
            return;
        }

        const formData = new FormData(form);
        formData.set('file', selectedVideoFile);

        const progressWrapper = document.getElementById('videoProgressWrapper');
        const progressFill = document.getElementById('videoProgressFill');
        const progressPercent = document.getElementById('videoProgressPercent');
        const progressStatus = document.getElementById('videoProgressStatus');

        progressWrapper.style.display = 'block';
        progressStatus.textContent = 'Uploading video & generating QR code...';
        submitBtn.disabled = true;
        submitBtn.querySelector('span').textContent = 'Uploading...';

        const xhr = new XMLHttpRequest();
        xhr.open('POST', form.action, true);
        xhr.setRequestHeader('X-CSRFToken', getCsrfToken());

        xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                progressFill.style.width = `${percent}%`;
                progressPercent.textContent = `${percent}%`;
                if (percent === 100) {
                    progressStatus.textContent = 'Generating print-ready QR code...';
                }
            }
        };

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const res = JSON.parse(xhr.responseText);
                    if (res.success) {
                        saveMediaToLocalStorage({
                            mediaId: res.media_id,
                            creatorToken: res.creator_token,
                            title: res.title,
                            originalName: selectedVideoFile.name,
                            mediaType: 'video',
                            sizeFormatted: formatBytes(selectedVideoFile.size),
                            createdAt: new Date().toISOString(),
                            qrUrl: res.qr_url,
                            mediaUrl: res.media_url
                        });
                        window.location.href = res.result_url;
                    } else {
                        showToast(res.error || 'Video upload failed.', 'error');
                        resetVideoUploadUi();
                    }
                } catch (err) {
                    showToast('Server response could not be parsed.', 'error');
                    resetVideoUploadUi();
                }
            } else {
                try {
                    const errRes = JSON.parse(xhr.responseText);
                    showToast(errRes.error || `Upload failed (${xhr.status}).`, 'error');
                } catch (e) {
                    showToast(`Upload failed with status ${xhr.status}.`, 'error');
                }
                resetVideoUploadUi();
            }
        };

        xhr.onerror = () => {
            showToast('Network error during video upload.', 'error');
            resetVideoUploadUi();
        };

        xhr.send(formData);
    });

    function resetVideoUploadUi() {
        const progressWrapper = document.getElementById('videoProgressWrapper');
        if (progressWrapper) progressWrapper.style.display = 'none';
        submitBtn.disabled = false;
        submitBtn.querySelector('span').textContent = 'Generate Video QR Code';
    }
}

// Result Page Helpers: Copy URL & QR Regeneration
function initResultPage() {
    const copyBtn = document.getElementById('copyUrlBtn');
    const shareInput = document.getElementById('shareUrlInput');
    const stylePicker = document.getElementById('resultStylePicker');
    const qrImage = document.getElementById('resultQrImage');
    const loadingOverlay = document.getElementById('qrLoadingOverlay');

    if (copyBtn && shareInput) {
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(shareInput.value).then(() => {
                const originalText = copyBtn.querySelector('.copy-text').textContent;
                copyBtn.querySelector('.copy-text').textContent = 'Copied!';
                copyBtn.classList.add('btn-primary');
                copyBtn.classList.remove('btn-secondary');
                showToast('Media URL copied to clipboard!', 'success');

                setTimeout(() => {
                    copyBtn.querySelector('.copy-text').textContent = originalText;
                    copyBtn.classList.remove('btn-primary');
                    copyBtn.classList.add('btn-secondary');
                }, 2000);
            }).catch(() => {
                shareInput.select();
                document.execCommand('copy');
                showToast('URL copied!', 'success');
            });
        });
    }

    if (stylePicker && qrImage) {
        const mediaId = stylePicker.getAttribute('data-media-id');
        const stylePills = stylePicker.querySelectorAll('.style-pill');

        stylePills.forEach(pill => {
            pill.addEventListener('click', () => {
                const newStyle = pill.getAttribute('data-style');
                if (pill.classList.contains('active')) return;

                stylePills.forEach(p => p.classList.remove('active'));
                pill.classList.add('active');

                if (loadingOverlay) loadingOverlay.style.display = 'flex';

                fetch('/generate-qr', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        media_id: mediaId,
                        qr_style: newStyle
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const freshUrl = `${data.qr_url}?t=${new Date().getTime()}`;
                        qrImage.src = freshUrl;
                        showToast(`QR palette updated to "${newStyle}"`, 'success');
                    } else {
                        showToast(data.error || 'Failed to update style.', 'error');
                    }
                })
                .catch(() => {
                    showToast('Failed to update QR style.', 'error');
                })
                .finally(() => {
                    if (loadingOverlay) loadingOverlay.style.display = 'none';
                });
            });
        });
    }
}

// My Codes Page Renderer & Deletion Handler
function renderMyCodes() {
    const grid = document.getElementById('myCodesGrid');
    const emptyState = document.getElementById('emptyStateCard');
    if (!grid || !emptyState) return;

    const history = getLocalHistory();
    grid.innerHTML = '';

    if (history.length === 0) {
        grid.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    grid.style.display = 'grid';
    emptyState.style.display = 'none';

    history.forEach(item => {
        const card = document.createElement('div');
        card.className = 'code-card';
        card.id = `card-${item.mediaId}`;

        const isPhoto = item.mediaType === 'photo';
        const typeLabel = isPhoto ? 'Photo' : 'Video';
        const createdDate = item.createdAt ? new Date(item.createdAt).toLocaleDateString(undefined, {
            month: 'short', day: 'numeric', year: 'numeric'
        }) : 'Recently';

        card.innerHTML = `
            <div class="code-card-top">
                <div class="code-card-qr-thumb">
                    <img src="${item.qrUrl}" alt="QR Thumbnail">
                </div>
                <div class="code-card-info">
                    <span class="code-card-badge">${typeLabel}</span>
                    <h3 class="code-card-title">${item.title || item.originalName || typeLabel}</h3>
                    <span class="code-card-date">${createdDate} • ${item.sizeFormatted || ''}</span>
                </div>
            </div>
            <div class="code-card-body">
                <div class="code-card-actions">
                    <a href="/m/${item.mediaId}" target="_blank" rel="noopener" class="btn btn-secondary btn-xs">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                        View Media
                    </a>
                    <a href="/download-qr/${item.mediaId}" download class="btn btn-secondary btn-xs">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                        Get QR
                    </a>
                </div>
            </div>
            <div class="code-card-footer">
                <span class="code-card-id">ID: ${item.mediaId}</span>
                <button type="button" class="btn btn-secondary btn-xs danger-text delete-media-btn" data-id="${item.mediaId}" data-title="${item.title || item.originalName || typeLabel}" data-token="${item.creatorToken}">
                    Delete
                </button>
            </div>
        `;

        grid.appendChild(card);
    });

    // Attach delete listeners
    const deleteButtons = grid.querySelectorAll('.delete-media-btn');
    deleteButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const mediaId = btn.getAttribute('data-id');
            const title = btn.getAttribute('data-title');
            const token = btn.getAttribute('data-token');
            openDeleteModal(mediaId, title, token);
        });
    });
}

function openDeleteModal(mediaId, title, token) {
    const modal = document.getElementById('deleteModal');
    const titleEl = document.getElementById('deleteMediaTitle');
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    const cancelBtn = document.getElementById('cancelDeleteBtn');

    if (!modal) return;

    pendingDeleteMediaId = mediaId;
    pendingDeleteToken = token;
    if (titleEl) titleEl.textContent = `"${title}"`;

    modal.style.display = 'flex';

    const closeHandler = () => {
        modal.style.display = 'none';
        pendingDeleteMediaId = null;
        pendingDeleteToken = null;
    };

    cancelBtn.onclick = closeHandler;

    confirmBtn.onclick = () => {
        if (!pendingDeleteMediaId) return;

        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Deleting...';

        fetch(`/api/media/${pendingDeleteMediaId}/delete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Creator-Token': pendingDeleteToken || '',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                creator_token: pendingDeleteToken
            })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                removeFromLocalStorage(pendingDeleteMediaId);
                showToast('Media and QR code deleted permanently.', 'success');
                closeHandler();
                renderMyCodes();
            } else {
                showToast(data.error || 'Failed to delete media.', 'error');
            }
        })
        .catch(() => {
            showToast('Network error while deleting media.', 'error');
        })
        .finally(() => {
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Delete Permanently';
        });
    };
}

// Global DOM Ready Initialization
document.addEventListener('DOMContentLoaded', () => {
    updateNavBadge();
    initModeSwitcher();
    initPhotoUpload();
    initVideoUpload();
    initResultPage();
});
