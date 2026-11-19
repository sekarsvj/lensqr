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

    IS_VERCEL = bool(os.environ.get('VERCEL'))

    # Storage directories (On Vercel serverless, root is read-only so use /tmp)
    if IS_VERCEL:
        DATA_DIR = '/tmp/data'
        UPLOAD_FOLDER_PHOTOS = '/tmp/uploads/photos'
        UPLOAD_FOLDER_VIDEOS = '/tmp/uploads/videos'
        UPLOAD_FOLDER_DOCUMENTS = '/tmp/uploads/documents'
        QR_FOLDER = '/tmp/qr_codes'
    else:
        DATA_DIR = os.path.join(BASE_DIR, 'data')
        UPLOAD_FOLDER_PHOTOS = os.path.join(BASE_DIR, 'uploads', 'photos')
        UPLOAD_FOLDER_VIDEOS = os.path.join(BASE_DIR, 'uploads', 'videos')
        UPLOAD_FOLDER_DOCUMENTS = os.path.join(BASE_DIR, 'uploads', 'documents')
        QR_FOLDER = os.path.join(BASE_DIR, 'qr_codes')

    JSON_STORAGE_PATH = os.path.join(DATA_DIR, 'media.json')

    # Upload limits (MB and bytes)
    MAX_PHOTO_MB = int(os.environ.get('MAX_PHOTO_MB', 25))
    MAX_VIDEO_MB = int(os.environ.get('MAX_VIDEO_MB', 100))
    MAX_DOCUMENT_MB = int(os.environ.get('MAX_DOCUMENT_MB', 50))
    MAX_PHOTO_SIZE = MAX_PHOTO_MB * 1024 * 1024
    MAX_VIDEO_SIZE = MAX_VIDEO_MB * 1024 * 1024
    MAX_DOCUMENT_SIZE = MAX_DOCUMENT_MB * 1024 * 1024
    MAX_CONTENT_LENGTH = (max(MAX_VIDEO_MB, MAX_DOCUMENT_MB, MAX_PHOTO_MB) + 15) * 1024 * 1024

    # Permitted extensions
    ALLOWED_PHOTO_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm'}
    ALLOWED_DOCUMENT_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'txt', 'rtf', 'csv', 'tsv', 'odt', 'ods', 'odp',
        'epub', 'zip', 'tar', 'gz', '7z', 'rar', 'json', 'xml', 'md'
    }

    # Host & Port configuration (0.0.0.0:5000 for local & tunnel accessibility)
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    # Public domain for QR encoding (Supports Cloudflare Tunnel, custom domains, Render, etc.)
    # Priority: PUBLIC_URL env -> VERCEL_URL -> RENDER_EXTERNAL_URL -> DEV_PUBLIC_URL -> SERVER_URL
    _vercel_url = os.environ.get('VERCEL_URL', '').strip().rstrip('/')
    if _vercel_url and not _vercel_url.startswith('http'):
        _vercel_url = f"https://{_vercel_url}"

    PUBLIC_URL = (
        os.environ.get('PUBLIC_URL') or
        _vercel_url or
        os.environ.get('RENDER_EXTERNAL_URL') or
        os.environ.get('DEV_PUBLIC_URL') or
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


def is_loopback(url_or_host: str) -> bool:
    """Check if a URL or host string refers to local loopback (localhost/127.0.0.1)."""
    if not url_or_host:
        return False
    lower = url_or_host.lower()
    return (
        'localhost' in lower or
        '127.0.0.1' in lower or
        '0.0.0.0' in lower or
        '::1' in lower
    )


def resolve_public_base_url(request=None) -> str:
    """
    Determine the effective public URL for QR code generation.
    Strictly prefers public HTTPS URLs (e.g. Cloudflare Tunnel, custom domains)
    and avoids loopback (localhost / 127.0.0.1) so users scanning from other
    locations (e.g. Punjab, cellular devices) can access media.
    """
    # 1. Explicit PUBLIC_URL (from environment or Config)
    env_public = (
        os.environ.get('PUBLIC_URL') or
        getattr(Config, 'PUBLIC_URL', '') or ''
    ).strip().rstrip('/')
    if env_public:
        if not is_loopback(env_public):
            return env_public
        else:
            print(
                f"! WARNING: PUBLIC_URL '{env_public}' is a loopback address. "
                "QR codes will not be accessible externally. "
                "Please configure a Cloudflare Tunnel or public domain."
            )

    # 2. Vercel automatic HTTPS domain
    vercel_raw = os.environ.get('VERCEL_URL', '').strip().rstrip('/')
    if vercel_raw:
        if not vercel_raw.startswith('http'):
            vercel_raw = f"https://{vercel_raw}"
        if not is_loopback(vercel_raw):
            return vercel_raw

    # 3. Render automatic HTTPS domain
    render_url = os.environ.get('RENDER_EXTERNAL_URL', '').strip().rstrip('/')
    if render_url and not is_loopback(render_url):
        return render_url

    # 3. Dedicated local development URL / tunnel (e.g., Cloudflare Tunnel / Ngrok)
    dev_public = (
        os.environ.get('DEV_PUBLIC_URL') or
        os.environ.get('TUNNEL_URL') or
        os.environ.get('CLOUDFLARE_TUNNEL_URL', '')
    ).strip().rstrip('/')
    if dev_public and not is_loopback(dev_public):
        return dev_public

    # 4. SERVER_URL fallback
    server_url = os.environ.get('SERVER_URL', '').strip().rstrip('/')
    if server_url and not is_loopback(server_url):
        return server_url

    port = str(getattr(Config, 'PORT', os.environ.get('PORT', '5000')))

    # 5. Check request host if provided (e.g. access through Cloudflare Tunnel or reverse proxy)
    if request is not None:
        try:
            host_name = request.host.split(':')[0].lower()
            if not is_loopback(host_name):
                # When ProxyFix is enabled, request.host_url reflects HTTPS and external tunnel domain
                return request.host_url.rstrip('/')
            if ':' in request.host:
                port = request.host.split(':')[1]
        except Exception:
            pass

    # 6. Fallback: Auto-detect LAN IP for mobile scanning on the same local network
    lan_ip = get_lan_ip()
    port_suffix = f":{port}" if port and port not in ['80', '443'] else ""
    return f"http://{lan_ip}{port_suffix}"
