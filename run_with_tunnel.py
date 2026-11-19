"""
LensQR Photo & Video QR Generator - Cloudflare Tunnel & Flask Runner.
Runs Flask on 0.0.0.0:5000 and exposes it globally via Cloudflare Tunnel (cloudflared),
enabling users from Punjab, mobile networks, and anywhere in the world to access
media by scanning generated QR codes.
"""

import argparse
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dotenv import load_dotenv

# Ensure we're in the project directory
# Ensure unbuffered output so logs appear immediately
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))
os.chdir(PROJECT_DIR)
load_dotenv(os.path.join(PROJECT_DIR, '.env'))


def kill_stale_cloudflared():
    """Terminate any lingering cloudflared processes to prevent tunnel collisions."""
    try:
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/F', '/IM', 'cloudflared.exe'], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(['pkill', '-f', 'cloudflared'], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def find_cloudflared() -> str:
    """Find cloudflared executable in local directory or system PATH."""
    local_cf = os.path.join(PROJECT_DIR, 'cloudflared.exe')
    if os.path.isfile(local_cf):
        return local_cf

    # Check PATH
    import shutil
    path_cf = shutil.which('cloudflared')
    if path_cf:
        return path_cf

    return ""


def main():
    parser = argparse.ArgumentParser(
        description="Run LensQR Flask application with Cloudflare Tunnel."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get('PORT', 5000)),
        help="Local port to bind Flask (default: 5000)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get('HOST', '0.0.0.0'),
        help="Local host to bind Flask (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--no-regen",
        action="store_true",
        help="Skip automatic batch regeneration of existing QR codes"
    )
    parser.add_argument(
        "--save-env",
        action="store_true",
        help="Save the assigned Cloudflare Tunnel URL to .env file"
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open the default web browser"
    )
    args = parser.parse_args()

    cf_exe = find_cloudflared()
    if not cf_exe:
        print("=" * 65)
        print("ERROR: cloudflared executable not found!")
        print("Please place cloudflared.exe in this directory or install it:")
        print("  winget install --id Cloudflare.cloudflared")
        print("Or download directly from:")
        print("  https://github.com/cloudflare/cloudflared/releases/latest")
        print("=" * 65)
        sys.exit(1)

    print("=" * 65)
    print("  LensQR - Starting Cloudflare Tunnel & Flask Server")
    print(f"  * Local Binding:  {args.host}:{args.port}")
    print(f"  * Using binary:   {cf_exe}")
    print("=" * 65)
    
    # Terminate any leftover instances before spawning fresh tunnel
    kill_stale_cloudflared()
    print("Starting Cloudflare Tunnel...")

    # Start cloudflared process
    cf_cmd = [cf_exe, "tunnel", "--url", f"http://127.0.0.1:{args.port}"]
    cf_proc = subprocess.Popen(
        cf_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding='utf-8',
        errors='replace'
    )

    tunnel_url = None
    tunnel_registered = threading.Event()
    url_pattern = re.compile(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com')

    # Continuously drain cloudflared output in thread so pipe never buffers or stalls
    def read_cf():
        nonlocal tunnel_url
        for line in iter(cf_proc.stdout.readline, ''):
            if not tunnel_url:
                m = url_pattern.search(line)
                if m:
                    tunnel_url = m.group(0)
            if 'Registered tunnel connection' in line:
                tunnel_registered.set()

    t_reader = threading.Thread(target=read_cf, daemon=True)
    t_reader.start()

    # Wait up to 25 seconds for tunnel URL and registration
    start_time = time.time()
    while time.time() - start_time < 25:
        if tunnel_url and tunnel_registered.is_set():
            break
        time.sleep(0.5)

    if not tunnel_url:
        print("Error: Could not retrieve Cloudflare Tunnel URL within 25 seconds.", flush=True)
        cf_proc.terminate()
        sys.exit(1)

    # Set PUBLIC_URL in current process environment
    os.environ['PUBLIC_URL'] = tunnel_url
    os.environ['HOST'] = args.host
    os.environ['PORT'] = str(args.port)

    # Always save the active tunnel URL to .env and environment
    from regenerate_qr_codes import update_env_public_url
    update_env_public_url(tunnel_url)

    lan_ip = "127.0.0.1"
    try:
        from config import get_lan_ip
        lan_ip = get_lan_ip()
    except Exception:
        pass

    print("\n" + "=" * 65)
    print("  LENSQR IS LIVE & GLOBALLY ACCESSIBLE VIA CLOUDFLARE TUNNEL!")
    print(f"  * Public HTTPS URL:    {tunnel_url}")
    print(f"  * Local PC Access:     http://127.0.0.1:{args.port}")
    if lan_ip and lan_ip != "127.0.0.1":
        print(f"  * Same Wi-Fi Access:   http://{lan_ip}:{args.port}")
    print(f"  * Mobile & Worldwide:  Users anywhere can scan & view!")
    print("=" * 65 + "\n")

    # Pre-import Flask app in main thread to avoid concurrent import issues
    from app import app
    from services.media_service import regenerate_all_qr_codes

    # Asynchronously regenerate existing QR codes in background so Flask starts immediately
    if not args.no_regen:
        def regen_async():
            try:
                print("Background sync: regenerating existing QR codes with public tunnel URL...", flush=True)
                res = regenerate_all_qr_codes(new_base_url=tunnel_url)
                print(f"-> Successfully synchronized {res['regenerated_count']} QR codes to {tunnel_url}", flush=True)
            except Exception as e:
                print(f"Notice: background QR sync error: {e}", flush=True)

        threading.Thread(target=regen_async, daemon=True).start()

    # Automatically open local browser unless opted out
    if not args.no_browser:
        def open_browser():
            time.sleep(1.2)
            try:
                import webbrowser
                webbrowser.open(f"http://127.0.0.1:{args.port}")
            except Exception:
                pass

        threading.Thread(target=open_browser, daemon=True).start()

    # Forward remaining cloudflared output in background daemon thread
    def stream_cf():
        for l in iter(cf_proc.stdout.readline, ''):
            pass

    t = threading.Thread(target=stream_cf, daemon=True)
    t.start()

    # Clean shutdown handler
    def cleanup(signum=None, frame=None):
        print("\nShutting down Cloudflare Tunnel and Flask...")
        try:
            cf_proc.terminate()
            cf_proc.wait(timeout=3)
        except Exception:
            try:
                cf_proc.kill()
            except Exception:
                pass
        kill_stale_cloudflared()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Launch Flask application
    try:
        from app import app
        # Ensure debug mode is False for public tunnel security
        app.run(host=args.host, port=args.port, debug=False)
    except KeyboardInterrupt:
        cleanup()
    finally:
        cleanup()


if __name__ == '__main__':
    main()
