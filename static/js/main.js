/**
 * LensQR Photo & Video QR Generator - Core Client Application
 * Strictly Vanilla JavaScript (No Node.js, npm, or external JS frameworks)
 */

// Global State
let selectedPhotoFile = null;
let selectedVideoFile = null;
let selectedDocumentFile = null;
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

// Mode Switcher (Photo vs Video vs Document vs URL)
function initModeSwitcher() {
    const tabPhoto = document.getElementById('tabPhoto');
    const tabVideo = document.getElementById('tabVideo');
    const tabDocument = document.getElementById('tabDocument');
    const tabUrl = document.getElementById('tabUrl');
    const panelPhoto = document.getElementById('panelPhoto');
    const panelVideo = document.getElementById('panelVideo');
    const panelDocument = document.getElementById('panelDocument');
    const panelUrl = document.getElementById('panelUrl');

    if (!tabPhoto || !tabVideo) return;

    function switchMode(mode) {
        tabPhoto.classList.remove('active');
        tabVideo.classList.remove('active');
        if (tabDocument) tabDocument.classList.remove('active');
        if (tabUrl) tabUrl.classList.remove('active');

        panelPhoto.style.display = 'none';
        panelVideo.style.display = 'none';
        if (panelDocument) panelDocument.style.display = 'none';
        if (panelUrl) panelUrl.style.display = 'none';

        if (mode === 'photo') {
            tabPhoto.classList.add('active');
            panelPhoto.style.display = 'block';
            window.location.hash = 'photo-section';
        } else if (mode === 'video') {
            tabVideo.classList.add('active');
            panelVideo.style.display = 'block';
            window.location.hash = 'video-section';
        } else if (mode === 'document' && panelDocument) {
            tabDocument.classList.add('active');
            panelDocument.style.display = 'block';
            window.location.hash = 'document-section';
        } else if (mode === 'url' && panelUrl) {
            tabUrl.classList.add('active');
            panelUrl.style.display = 'block';
            window.location.hash = 'url-section';
        }
    }

    tabPhoto.addEventListener('click', () => switchMode('photo'));
    tabVideo.addEventListener('click', () => switchMode('video'));
    if (tabDocument) {
        tabDocument.addEventListener('click', () => switchMode('document'));
    }
    if (tabUrl) {
        tabUrl.addEventListener('click', () => switchMode('url'));
    }

    if (window.location.hash === '#video-section') {
        switchMode('video');
    } else if (window.location.hash === '#document-section') {
        switchMode('document');
    } else if (window.location.hash === '#url-section') {
        switchMode('url');
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
        const isVideo = item.mediaType === 'video';
        const isDoc = item.mediaType === 'document';
        const isUrl = item.mediaType === 'url';
        let typeLabel = 'Photo';
        if (isVideo) typeLabel = 'Video';
        else if (isDoc) typeLabel = 'Document';
        else if (isUrl) typeLabel = 'Link';

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
                        ${isUrl ? 'Open Link' : 'View Media'}
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

// Document Upload Management (PDF, Word, Excel, PPT, Text, etc.)
function initDocumentUpload() {
    const dropzone = document.getElementById('documentDropzone');
    const fileInput = document.getElementById('documentFileInput');
    const browseBtn = document.getElementById('documentBrowseBtn');
    const previewCard = document.getElementById('documentPreviewCard');
    const fileNameEl = document.getElementById('documentFileName');
    const fileSizeEl = document.getElementById('documentFileSize');
    const extBadgeEl = document.getElementById('documentExtBadge');
    const iconWrapper = document.getElementById('docTypeIconWrapper');
    const removeBtn = document.getElementById('removeDocumentBtn');
    const submitBtn = document.getElementById('submitDocumentBtn');
    const form = document.getElementById('documentUploadForm');
    const progressWrap = document.getElementById('documentProgressWrap');
    const progressBar = document.getElementById('documentProgressBar');
    const progressStatus = document.getElementById('documentProgressStatus');
    const progressPercent = document.getElementById('documentProgressPercent');
    const stylePicker = document.getElementById('documentStylePicker');
    const styleInput = document.getElementById('documentQrStyle');

    if (!form || !fileInput) return;

    // Document Color Theme Picker
    if (stylePicker && styleInput) {
        stylePicker.addEventListener('click', (e) => {
            const pill = e.target.closest('.style-pill');
            if (!pill) return;
            stylePicker.querySelectorAll('.style-pill').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            styleInput.value = pill.getAttribute('data-style');
        });
    }

    if (browseBtn) {
        browseBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileInput.click();
        });
    }

    if (dropzone) {
        dropzone.addEventListener('click', (e) => {
            if (e.target.tagName !== 'BUTTON') {
                fileInput.click();
            }
        });

        ['dragenter', 'dragover'].forEach(evt => {
            dropzone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add('drag-active');
            });
        });

        ['dragleave', 'drop'].forEach(evt => {
            dropzone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove('drag-active');
            });
        });

        dropzone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                handleDocumentSelection(files[0]);
            }
        });
    }

    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length > 0) {
            handleDocumentSelection(fileInput.files[0]);
        }
    });

    function getDocIconSvg(ext) {
        if (ext === 'pdf') {
            return `<svg viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2" width="36" height="36"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="9" y1="13" x2="15" y2="13"></line><line x1="9" y1="17" x2="13" y2="17"></line></svg>`;
        } else if (['doc', 'docx'].includes(ext)) {
            return `<svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2" width="36" height="36"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>`;
        } else if (['xls', 'xlsx', 'csv'].includes(ext)) {
            return `<svg viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" width="36" height="36"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><rect x="8" y="12" width="8" height="6"></rect></svg>`;
        } else if (['ppt', 'pptx'].includes(ext)) {
            return `<svg viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" width="36" height="36"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><circle cx="12" cy="14" r="3"></circle></svg>`;
        } else if (['zip', 'tar', 'gz', '7z', 'rar'].includes(ext)) {
            return `<svg viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" stroke-width="2" width="36" height="36"><path d="M21 8v13H3V8"></path><path d="M1 3h22v5H1z"></path><path d="M10 12h4"></path></svg>`;
        }
        return `<svg viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" width="36" height="36"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line></svg>`;
    }

    function handleDocumentSelection(file) {
        if (!file) return;

        const ext = file.name.split('.').pop().toLowerCase();
        const maxLimitBytes = 50 * 1024 * 1024; // 50MB

        if (file.size > maxLimitBytes) {
            showToast('Document file exceeds the 50MB size limit.', 'error');
            return;
        }

        selectedDocumentFile = file;
        fileNameEl.textContent = file.name;
        fileSizeEl.textContent = formatBytes(file.size);
        extBadgeEl.textContent = ext.toUpperCase();
        if (iconWrapper) {
            iconWrapper.innerHTML = getDocIconSvg(ext);
        }

        dropzone.style.display = 'none';
        previewCard.style.display = 'block';
        submitBtn.disabled = false;

        const titleInput = document.getElementById('documentTitle');
        if (titleInput && !titleInput.value.trim()) {
            titleInput.value = file.name.replace(/\.[^/.]+$/, "");
        }
    }

    if (removeBtn) {
        removeBtn.addEventListener('click', () => {
            selectedDocumentFile = null;
            fileInput.value = '';
            previewCard.style.display = 'none';
            dropzone.style.display = 'block';
            submitBtn.disabled = true;
        });
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        if (!selectedDocumentFile) {
            showToast('Please select a document file first.', 'error');
            return;
        }

        const formData = new FormData(form);
        formData.set('file', selectedDocumentFile);

        submitBtn.disabled = true;
        submitBtn.innerHTML = `<div class="spinner-sm"></div><span>Uploading Document...</span>`;
        if (progressWrap) progressWrap.style.display = 'block';

        const xhr = new XMLHttpRequest();
        xhr.open('POST', form.action, true);
        xhr.setRequestHeader('X-CSRFToken', getCsrfToken());

        xhr.upload.onprogress = (evt) => {
            if (evt.lengthComputable) {
                const percent = Math.round((evt.loaded / evt.total) * 100);
                if (progressBar) progressBar.style.width = percent + '%';
                if (progressPercent) progressPercent.textContent = percent + '%';
                if (progressStatus) {
                    progressStatus.textContent = percent < 100
                        ? `Uploading document (${formatBytes(evt.loaded)} / ${formatBytes(evt.total)})...`
                        : 'Generating QR code & syncing storage...';
                }
            }
        };

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const data = JSON.parse(xhr.responseText);
                    if (data.success) {
                        saveMediaToLocalStorage({
                            mediaId: data.media_id,
                            title: data.title,
                            mediaType: 'document',
                            mediaUrl: data.media_url,
                            qrUrl: data.qr_url,
                            resultUrl: data.result_url,
                            creatorToken: data.creator_token,
                            createdAt: new Date().toISOString()
                        });
                        showToast('Document QR Code generated successfully!', 'success');
                        window.location.href = data.result_url;
                    } else {
                        showToast(data.error || 'Upload failed.', 'error');
                        resetSubmit();
                    }
                } catch (err) {
                    showToast('Failed to parse server response.', 'error');
                    resetSubmit();
                }
            } else {
                try {
                    const data = JSON.parse(xhr.responseText);
                    showToast(data.error || `Upload failed with status ${xhr.status}`, 'error');
                } catch {
                    showToast(`Server returned status ${xhr.status}`, 'error');
                }
                resetSubmit();
            }
        };

        xhr.onerror = () => {
            showToast('Network error during upload.', 'error');
            resetSubmit();
        };

        function resetSubmit() {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="20" height="20">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                <span>Generate Document QR Code</span>
            `;
            if (progressWrap) progressWrap.style.display = 'none';
        }

        xhr.send(formData);
    });
}

// URL to QR Upload & Generation Handler
function initUrlUpload() {
    const form = document.getElementById('urlUploadForm');
    const urlInput = document.getElementById('urlInput');
    const submitBtn = document.getElementById('submitUrlBtn');
    const progressWrap = document.getElementById('urlProgressWrap');
    const progressBar = document.getElementById('urlProgressBar');
    const progressPercent = document.getElementById('urlProgressPercent');
    const progressStatus = document.getElementById('urlProgressStatus');
    const stylePicker = document.getElementById('urlStylePicker');
    const styleHidden = document.getElementById('urlQrStyle');

    if (!form || !urlInput) return;

    // Palette pill switcher
    if (stylePicker && styleHidden) {
        const pills = stylePicker.querySelectorAll('.style-pill');
        pills.forEach(pill => {
            pill.addEventListener('click', () => {
                pills.forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                styleHidden.value = pill.getAttribute('data-style');
            });
        });
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const rawUrl = urlInput.value.trim();
        if (!rawUrl) {
            showToast('Please enter a website link or URL.', 'error');
            urlInput.focus();
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = `<div class="spinner-sm"></div><span>Generating QR Code...</span>`;
        if (progressWrap) {
            progressWrap.style.display = 'block';
            if (progressBar) progressBar.style.width = '45%';
            if (progressPercent) progressPercent.textContent = '45%';
            if (progressStatus) progressStatus.textContent = 'Creating link record & styling QR...';
        }

        const formData = new FormData(form);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', form.action, true);
        xhr.setRequestHeader('X-CSRFToken', getCsrfToken());

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const data = JSON.parse(xhr.responseText);
                    if (data.success) {
                        if (progressBar) progressBar.style.width = '100%';
                        if (progressPercent) progressPercent.textContent = '100%';
                        if (progressStatus) progressStatus.textContent = 'QR Code generated!';

                        saveMediaToLocalStorage({
                            mediaId: data.media_id,
                            title: data.title || rawUrl,
                            mediaType: 'url',
                            targetUrl: data.target_url || rawUrl,
                            mediaUrl: data.media_url,
                            qrUrl: data.qr_url,
                            resultUrl: data.result_url,
                            creatorToken: data.creator_token,
                            sizeFormatted: 'Web Link',
                            createdAt: new Date().toISOString()
                        });

                        showToast('Link QR Code generated successfully!', 'success');
                        window.location.href = data.result_url;
                    } else {
                        showToast(data.error || 'Failed to generate QR code.', 'error');
                        resetSubmit();
                    }
                } catch (err) {
                    showToast('Failed to parse server response.', 'error');
                    resetSubmit();
                }
            } else {
                try {
                    const data = JSON.parse(xhr.responseText);
                    showToast(data.error || `Request failed with status ${xhr.status}`, 'error');
                } catch {
                    showToast(`Server returned status ${xhr.status}`, 'error');
                }
                resetSubmit();
            }
        };

        xhr.onerror = () => {
            showToast('Network error while generating QR code.', 'error');
            resetSubmit();
        };

        function resetSubmit() {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="20" height="20">
                    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                </svg>
                <span>Generate Link QR Code</span>
            `;
            if (progressWrap) progressWrap.style.display = 'none';
        }

        xhr.send(formData);
    });
}

// Global DOM Ready Initialization
document.addEventListener('DOMContentLoaded', () => {
    updateNavBadge();
    initModeSwitcher();
    initPhotoUpload();
    initVideoUpload();
    initDocumentUpload();
    initUrlUpload();
    initResultPage();
});
