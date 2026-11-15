import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Central configuration for Photo & Video QR Code Generator."""
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.environ.get(
        'SECRET_KEY',
        'lensqr-secret-dev-key-change-in-production-8f92a3bc')
    BRAND_NAME = os.environ.get('BRAND_NAME', 'LensQR')

    # Storage directories
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    JSON_STORAGE_PATH = os.path.join(DATA_DIR, 'media.json')
    UPLOAD_FOLDER_PHOTOS = os.path.join(BASE_DIR, 'uploads', 'photos')
    UPLOAD_FOLDER_VIDEOS = os.path.join(BASE_DIR, 'uploads', 'videos')
    QR_FOLDER = os.path.join(BASE_DIR, 'qr_codes')

    # Upload limits (MB and bytes)
    MAX_PHOTO_MB = int(os.environ.get('MAX_PHOTO_MB', 25))
    MAX_VIDEO_MB = int(os.environ.get('MAX_VIDEO_MB', 100))
    MAX_PHOTO_SIZE = MAX_PHOTO_MB * 1024 * 1024
    MAX_VIDEO_SIZE = MAX_VIDEO_MB * 1024 * 1024
    MAX_CONTENT_LENGTH = (MAX_VIDEO_MB + 15) * 1024 * 1024

    # Permitted extensions
    ALLOWED_PHOTO_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm'}

    # Public domain for QR encoding (Leave empty for localhost fallback)
    PUBLIC_URL = os.environ.get(
        'PUBLIC_URL', os.environ.get(
            'SERVER_URL', '')).rstrip('/')
