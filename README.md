# Photo & Video QR Code Generator

A professional, modern, responsive **Photo & Video QR Code Generator** web application built with Python Flask, database-free JSON metadata storage, and local filesystem file storage.

Designed with a clean, minimal SaaS aesthetic, responsive layouts, client-side upload previews with progress indicators, high-resolution QR generation with multiple color themes, unlisted media viewing (with HTML5 video partial-content seeking), and full creator management.

---

## 1. Overview & Architecture

The application supports three types of media sharing:
1. **Photo to QR Code**: Converts a single uploaded photograph (`.jpg`, `.jpeg`, `.png`, `.webp`) into an unlisted public viewing URL and generates a downloadable QR code.
2. **Video to QR Code**: Converts a single uploaded video (`.mp4`, `.mov`, `.webm`) into an unlisted public viewing URL with an HTML5 video player and generates a downloadable QR code.
3. **Document to QR Code**: Converts any uploaded document (`.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`, `.txt`, `.csv`, `.zip`, `.rar`, etc.) into an unlisted viewing URL with interactive PDF inline preview, format-specific document cards, and direct download buttons.

### Core Architecture Highlights
- **Database-Free JSON Metadata Storage**: Uses `data/media.json` to persist metadata records. No SQLite, no PostgreSQL, no MySQL, no SQLAlchemy, and no external database services.
- **Thread-Safe & Atomic Writes**: Updates to the JSON storage use a thread mutex (`threading.Lock()`), write to a temporary file, flush and sync to disk (`os.fsync`), and perform an atomic replace (`os.replace`) to prevent corruption or partial writes.
- **Corrupted File Protection**: If corrupted JSON is detected, the application creates a timestamped emergency backup and alerts the operator, never silently overwriting data with an empty file.
- **Strictly No Node.js / npm**: All frontend interfaces are built with semantic HTML5, modern CSS3 (with CSS variables and ambient lighting), and pure Vanilla JavaScript. All assets are served directly through Flask.
- **Cryptographic Security**: Media identifiers use URL-safe random slugs (`secrets.token_urlsafe`), uploads issue 256-bit creator tokens for authorized deletion, and all state-changing endpoints are protected by CSRF validation.

---

## 2. Project Directory Structure

```text
photo-video-qr/
│
├── app.py                      # Application factory, routes, and security middleware
├── config.py                   # Central configuration & environment loader
├── requirements.txt            # Python package dependencies
├── .env                        # Local environment variables
├── .env.example                # Sample environment template
├── .gitignore                  # Git ignore rules for virtual environments & uploads
├── README.md                   # Comprehensive documentation
│
├── database/
│   └── database.py             # JSON storage engine (thread locking, atomic writes)
│
├── data/
│   └── media.json              # Metadata JSON database
│
├── services/
│   ├── upload_service.py       # Magic bytes inspection, file validation, storage
│   ├── qr_service.py           # qrcode generation, color palettes, regeneration
│   └── media_service.py        # Business orchestration (create, get, list, delete)
│
├── templates/
│   ├── base.html               # Master layout, navigation, brand logo, footer
│   ├── index.html              # Home page: drag-and-drop studio (Photo & Video tabs)
│   ├── result.html             # QR result page: download, copy, preview, style picker
│   ├── viewer.html             # Public unlisted viewer (photo & video player)
│   ├── my_codes.html           # My QR Codes dashboard & creator deletion modal
│   ├── 404.html                # Custom 404 error page (Media Not Found)
│   └── 500.html                # Custom 500 error page (Server Error)
│
├── static/
│   ├── css/
│   │   └── style.css           # Modern SaaS stylesheet with ambient glows & dark mode
│   ├── js/
│   │   └── main.js             # Vanilla JS: drag & drop, XHR progress, local storage
│   └── images/                 # Static brand assets
│
├── uploads/
│   ├── photos/                 # Stored photos (UUID-based server filenames)
│   └── videos/                 # Stored videos (UUID-based server filenames)
│
├── qr_codes/                   # Stored high-resolution generated QR PNG files
│
└── tests/
    ├── test_upload.py          # Upload validation & format acceptance tests
    ├── test_qr.py              # QR generation, themes, and download tests
    ├── test_storage.py         # JSON storage engine & atomic write tests
    └── test_security.py        # CSRF, creator token deletion, and Range request tests
```

---

## 3. Technology Stack

- **Backend Framework**: Python 3.10+ & Flask 3.1+
- **Metadata Storage**: JSON file storage (`data/media.json`) with atomic file replacement
- **QR Generation**: Python `qrcode[pil]`, Pillow (`PIL`)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript (ES6+), Jinja2
- **Production Server**: Gunicorn (for Linux deployment) / Waitress (for Windows)

---

## 4. JSON Storage System

All media metadata is stored in `data/media.json` using the following structure:

```json
{
  "media": [
    {
      "id": "srP2Qh5q1w",
      "creator_token": "7b09df6c21e64627d750d0352be514787a2db1239845...",
      "type": "photo",
      "title": "Sunset Beach",
      "description": "Captured during the summer vacation",
      "original_name": "sunset.jpg",
      "filename": "e912f718c39e4a3b8d1469123847291a.jpg",
      "mime_type": "image/jpeg",
      "size_bytes": 450280,
      "qr_filename": "qr_srP2Qh5q1w_coral.png",
      "qr_style": "coral",
      "access": "unlisted",
      "views_count": 0,
      "created_at": "2026-11-15T02:00:00.000000+00:00"
    }
  ]
}
```

### Safety Features
- **Thread Lock**: All read/write operations acquire an internal process lock (`threading.Lock()`).
- **Atomic Writes**: Writes are saved to a temporary file (`media.json.tmp_<pid>_<thread>`), flushed, synced to disk (`os.fsync`), and atomically moved via `os.replace`.
- **Integrity Validation**: Every record is validated against required fields before writing.
- **Corrupted File Detection**: If the file becomes unparseable, an emergency copy `media.json.corrupted_<timestamp>` is created, preventing accidental overwrites.

---

## 5. Environment Configuration (`.env`)

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Available configuration options:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `SECRET_KEY` | *(Random string)* | Secret key for Flask session cookies and CSRF verification. |
| `BRAND_NAME` | `LensQR` | Branding title displayed across navigation, headers, and metadata. |
| `PUBLIC_URL` | *(Empty)* | Public domain encoded in generated QR codes (e.g. `https://qr.lensqr.net`). If empty, auto-detects from request host. |
| `MAX_PHOTO_MB` | `25` | Maximum upload size for a photograph in Megabytes. |
| `MAX_VIDEO_MB` | `100` | Maximum upload size for a video in Megabytes. |

---

## 6. Local Installation & Global Access via Cloudflare Tunnel

### Why People Scanning from Punjab or Other Locations Cannot Access `localhost`
When Flask runs on your computer at `http://localhost:5000` or `http://127.0.0.1:5000`, that address is a **loopback address** that exists *only inside your computer*.
- A person scanning the QR code from another network (e.g., mobile 4G/5G, home Wi-Fi, or another city like Punjab) will have their phone try to connect to *their own phone's loopback*, which immediately fails with "Server not found" or "Connection refused".
- **Solution**: Cloudflare Tunnel (`cloudflared`) connects your local Flask server to Cloudflare's secure global edge network, creating a public HTTPS URL (e.g. `https://your-tunnel.trycloudflare.com` or custom domain). When `PUBLIC_URL` is set to this address, all generated QR codes can be scanned and opened from anywhere in the world!

---

### Method A: 1-Click Launch (Flask + Cloudflare Tunnel Together)

To launch both Flask (bound to `0.0.0.0:5000`) and Cloudflare Tunnel in one command:

**Double-click `start_with_tunnel.bat`** OR run in PowerShell:
```powershell
python run_with_tunnel.py
```

This will automatically:
1. Start Cloudflare Tunnel and display your assigned public HTTPS URL (e.g. `https://xxxx.trycloudflare.com`).
2. Set `PUBLIC_URL` to that HTTPS address.
3. Automatically regenerate existing QR codes so they point to the live tunnel URL.
4. Start Flask securely on `0.0.0.0:5000` (with `debug=False`).

---

### Method B: Two Separate Terminals (Manual Control)

#### Terminal 1: Start Flask Server
```powershell
# In project folder with virtual environment active
python app.py
```
*Flask binds to `0.0.0.0:5000` with debug mode safely disabled for public traffic.*

#### Terminal 2: Start Cloudflare Tunnel
```powershell
# Using the bundled cloudflared executable:
.\cloudflared.exe tunnel --url http://127.0.0.1:5000

# OR using the Python helper (which displays instructions and can auto-regenerate):
python start_tunnel.py --regen
```

Copy the assigned HTTPS URL from the terminal output (e.g. `https://example-subdomain.trycloudflare.com`):
1. Add it to your `.env` file:
   ```env
   PUBLIC_URL=https://example-subdomain.trycloudflare.com
   ```
2. Regenerate your existing QR codes so they point to this URL:
   ```powershell
   python regenerate_qr_codes.py --url https://example-subdomain.trycloudflare.com --save-env
   ```

---

### Method C: Permanent Custom Domain with Named Cloudflare Tunnel

Quick tunnels (`*.trycloudflare.com`) change URLs each time they are restarted. If you print QR codes on physical items or share them permanently, use a **Named Tunnel** with your own domain (e.g. `https://qr.yourdomain.com`):

1. Login to Cloudflare CLI:
   ```powershell
   .\cloudflared.exe tunnel login
   ```
2. Create your tunnel:
   ```powershell
   .\cloudflared.exe tunnel create lensqr-tunnel
   ```
3. Route DNS to your custom domain:
   ```powershell
   .\cloudflared.exe tunnel route dns lensqr-tunnel qr.yourdomain.com
   ```
4. Configure `~/.cloudflared/config.yml`:
   ```yaml
   tunnel: <Tunnel-UUID>
   credentials-file: C:\Users\<User>\.cloudflared\<Tunnel-UUID>.json
   ingress:
     - hostname: qr.yourdomain.com
       service: http://127.0.0.1:5000
     - service: http_status:404
   ```
5. Run the tunnel:
   ```powershell
   .\cloudflared.exe tunnel run lensqr-tunnel
   ```
6. Set in `.env`:
   ```env
   PUBLIC_URL=https://qr.yourdomain.com
   ```
7. Batch regenerate your QR codes once:
   ```powershell
   python regenerate_qr_codes.py --url https://qr.yourdomain.com --save-env
   ```
*Now your QR codes will never expire and will work permanently worldwide!*

---

### Batch QR Code Regeneration Tool

To regenerate existing QR codes without modifying or re-uploading original media files:
```powershell
python regenerate_qr_codes.py --url https://your-public-url.com --save-env
```
- Preserves all media IDs, file contents, titles, and Supabase metadata.
- Updates QR code PNG images locally and synchronizes them to Supabase Storage (`qr-media` bucket).

---

### Security & Reverse Proxy Hardening
- **Debug Mode**: Flask debug mode is disabled by default (`debug=False`). The Werkzeug interactive debugger and tracebacks are never exposed on public URLs. To enable locally, explicitly set `FLASK_DEBUG=true`.
- **ProxyFix Middleware**: Configured with `x_for=1, x_proto=1, x_host=1, x_port=1` so Flask correctly recognizes HTTPS schemes and hostnames passed by Cloudflare Tunnel.
- **Cookies**: Session cookies automatically use `SameSite=Lax` and `HttpOnly=True` (`Secure=True` on HTTPS).
- **Secrets**: Backend secrets (`SECRET_KEY`, `SUPABASE_SECRET_KEY`) are kept strictly on the backend and never exposed to clients.

---

## 7. Running Automated Tests & Live Verification

### Run Full Unit Test Suite (31 Tests)
```powershell
python -m unittest discover tests -v
```

### Run Live External Cloudflare Tunnel Test
```powershell
python verify_external_tunnel.py
```
*Tests the entire round-trip across Cloudflare's public HTTPS edge, verifying HTTP 200 responses, viewer page rendering, media streaming, and QR accessibility from external networks.*

```powershell
python -m unittest discover -s tests -v
```

Run the live pipeline verification script:
```powershell
python verify_live.py
```

---

## 8. API & Route Documentation

| Route | Method | Description |
| :--- | :--- | :--- |
| `GET /` | `GET` | Homepage with Photo and Video upload studio. |
| `POST /upload/photo` | `POST` | Upload one photograph (`multipart/form-data`: `file`, `title`, `description`, `qr_style`). |
| `POST /upload/video` | `POST` | Upload one video (`multipart/form-data`: `file`, `title`, `description`, `qr_style`). |
| `GET /result/<media_id>` | `GET` | QR result page with download, copy, preview, and palette switcher. |
| `GET /m/<media_id>` | `GET` | Public unlisted media viewer (photograph or HTML5 video). |
| `GET /media-file/<media_id>` | `GET` | Serves binary photo/video with HTTP Range support for seeking. |
| `GET /download-qr/<media_id>`| `GET` | Downloads the QR code PNG as an attachment. |
| `GET /qr-image/<filename>` | `GET` | Serves QR code image from `qr_codes/` directory. |
| `POST /generate-qr` | `POST` | Regenerates QR code with a new color palette without changing the media link. |
| `GET /my-codes` | `GET` | Web dashboard to view and manage previously generated QR codes. |
| `POST /api/media/<media_id>/delete` | `POST` | Permanently deletes media file, QR code, and metadata after creator token validation. |
| `GET /api/media/<media_id>` | `GET` | Returns public media metadata as JSON. |
| `POST /api/admin/regenerate-qr-codes` | `POST` | Batch regenerates all QR codes to a new or effective public URL while preserving media IDs and files. |

---

## 9. QR Code URL Resolution & LAN Accessibility

QR codes generated on desktop browsers must be scannable by mobile devices without failing due to loopback addresses (`127.0.0.1` or `localhost`). LensQR uses an intelligent multi-tier URL resolution engine:

### Resolution Priority Hierarchy
1. **`PUBLIC_URL`**: Explicit custom domain configured in `.env` (e.g. `https://qr.lensqr.net`). Recommended for all production environments.
2. **`RENDER_EXTERNAL_URL`**: Automatically supplied by Render cloud platform (e.g. `https://lensqr.onrender.com`). Ensured with `https://`.
3. **`DEV_PUBLIC_URL`**: Local tunnel or reverse proxy URL (e.g. ngrok or localtunnel: `https://my-tunnel.loca.lt`).
4. **Non-Loopback Host Header**: If the client accesses via LAN IP or public domain, that host is preserved.
5. **Local Network LAN IP (`get_lan_ip()`)**: During local development without `PUBLIC_URL`, Flask binds to `0.0.0.0` and automatically resolves the machine's Wi-Fi / Ethernet LAN IP (e.g. `http://192.168.1.50:5000`). QR codes generated on localhost encode this LAN IP so phones connected to the same Wi-Fi can immediately scan and view media.

### Batch QR Code Regeneration
To update existing QR codes (e.g., when transitioning from local development to production or updating your domain) without re-uploading media:

```bash
# Auto-detects effective URL
python regenerate_qr_codes.py

# Or explicitly specify target production domain:
python regenerate_qr_codes.py --url https://qr.lensqr.net
```
All existing media IDs, titles, descriptions, and uploaded media files are strictly preserved.

---

## 10. Production Deployment Guide

### Deployment on Linux VPS / Cloud (Ubuntu / Debian)

1. **Clone project and setup virtual environment**:
   ```bash
   cd /var/www/photo-video-qr
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt gunicorn
   ```

2. **Configure `.env`**:
   ```ini
   SECRET_KEY=generate-a-strong-random-key-for-production
   BRAND_NAME=LensQR
   PUBLIC_URL=https://qr.lensqr.net
   MAX_PHOTO_MB=25
   MAX_VIDEO_MB=100
   ```

3. **Persistent Directories**:
   Ensure the following directories are writable and persist across deployments:
   - `data/`
   - `uploads/photos/`
   - `uploads/videos/`
   - `qr_codes/`

4. **Systemd Service (`/etc/systemd/system/photo-video-qr.service`)**:
   > Note: Use **1 worker** (`--workers 1`) to preserve in-process thread locking for JSON file operations.
   ```ini
   [Unit]
   Description=Photo & Video QR Generator
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/var/www/photo-video-qr
   EnvironmentFile=/var/www/photo-video-qr/.env
   ExecStart=/var/www/photo-video-qr/.venv/bin/gunicorn --workers 1 --threads 4 --bind 127.0.0.1:5000 app:app

   [Install]
   WantedBy=multi-user.target
   ```

5. **Nginx Reverse Proxy with HTTPS**:
   ```nginx
   server {
       listen 80;
       server_name qr.lensqr.net;
       return 301 https://$host$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name qr.lensqr.net;

       ssl_certificate /etc/letsencrypt/live/qr.lensqr.net/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/qr.lensqr.net/privkey.pem;

       client_max_body_size 120M;

       location /static/ {
           alias /var/www/photo-video-qr/static/;
           expires 30d;
           add_header Cache-Control "public, no-transform";
       }

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

---

## 10. Backup & Recovery Procedure

### Backup
To back up all metadata, uploaded media, and QR codes, run:
```bash
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz data/ uploads/ qr_codes/ .env
```

### Recovery
To restore from a backup:
1. Stop the application service (`sudo systemctl stop photo-video-qr`).
2. Extract the archive into the application root:
   ```bash
   tar -xzf backup_YYYYMMDD_HHMMSS.tar.gz
   ```
3. Restart the service (`sudo systemctl start photo-video-qr`).
