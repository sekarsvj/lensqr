import os
import socket
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

    # Public domain for QR encoding (Supports separate dev & prod URLs)
    # Checks PUBLIC_URL, RENDER_EXTERNAL_URL (Render HTTPS), and SERVER_URL
    PUBLIC_URL = (
        os.environ.get('PUBLIC_URL') or
        os.environ.get('RENDER_EXTERNAL_URL') or
        os.environ.get('SERVER_URL', '')
    ).rstrip('/')
    DEV_PUBLIC_URL = os.environ.get('DEV_PUBLIC_URL', '').rstrip('/')
    RENDER_EXTERNAL_URL = os.environ.get(
        'RENDER_EXTERNAL_URL', ''
    ).rstrip('/')

    # Supabase Configuration
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
    SUPABASE_KEY = (
        os.environ.get('SUPABASE_SECRET_KEY') or
        os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or
        os.environ.get('SUPABASE_PUBLISHABLE_KEY') or
        os.environ.get('SUPABASE_ANON_KEY') or ''
    )
    SUPABASE_STORAGE_BUCKET = os.environ.get(
        'SUPABASE_STORAGE_BUCKET', 'qr-media'
    )
    SIGNED_URL_EXPIRY = int(os.environ.get('SIGNED_URL_EXPIRY', 3600))

    @classmethod
    def is_supabase_configured(cls):
        """Check if Supabase credentials are configured."""
        return bool(cls.SUPABASE_URL and cls.SUPABASE_KEY)


def get_lan_ip() -> str:
    """
    Detect machine's primary local network IP (e.g. 192.168.1.50)
    for mobile device LAN scanning.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass

    try:
        host_ip = socket.gethostbyname(socket.gethostname())
        if host_ip and not host_ip.startswith('127.'):
            return host_ip
    except Exception:
        pass

    return '127.0.0.1'


def resolve_public_base_url(request=None) -> str:
    """
    Determine the effective public URL for QR code generation.
    Never returns localhost or 127.0.0.1 if an external or LAN URL can be
    resolved.
    """
    # 1. Explicit PUBLIC_URL
    env_public = os.environ.get('PUBLIC_URL', '').strip().rstrip('/')
    if env_public:
        return env_public

    # 2. Render automatic HTTPS domain
    render_url = os.environ.get('RENDER_EXTERNAL_URL', '').strip().rstrip('/')
    if render_url:
        return render_url

    # 3. Dedicated local development URL / tunnel
    dev_public = os.environ.get('DEV_PUBLIC_URL', '').strip().rstrip('/')
    if dev_public:
        return dev_public

    # 4. SERVER_URL fallback
    server_url = os.environ.get('SERVER_URL', '').strip().rstrip('/')
    if server_url:
        return server_url

    port = os.environ.get('PORT', '5000')

    # 5. Check request host if provided
    if request is not None:
        try:
            host_name = request.host.split(':')[0].lower()
            if host_name not in ['localhost', '127.0.0.1', '0.0.0.0']:
                return request.host_url.rstrip('/')
            if ':' in request.host:
                port = request.host.split(':')[1]
        except Exception:
            pass

    # 6. Auto-detect LAN IP for mobile scanning
    lan_ip = get_lan_ip()
    port_suffix = f":{port}" if port and port not in ['80', '443'] else ""
    return f"http://{lan_ip}{port_suffix}"
