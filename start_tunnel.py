"""
LensQR Photo & Video QR Generator - Cloudflare Tunnel Standalone Starter.
Runs Cloudflare Tunnel, extracts the assigned trycloudflare HTTPS domain,
and optionally updates .env and regenerates existing QR codes.
"""

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from dotenv import load_dotenv

PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))
os.chdir(PROJECT_DIR)
load_dotenv(os.path.join(PROJECT_DIR, '.env'))


def find_cloudflared() -> str:
    local_cf = os.path.join(PROJECT_DIR, 'cloudflared.exe')
    if os.path.isfile(local_cf):
        return local_cf
    import shutil
    return shutil.which('cloudflared') or ""


def main():
    parser = argparse.ArgumentParser(
        description="Start Cloudflare Tunnel to expose local Flask port 5000."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get('PORT', 5000)),
        help="Local port that Flask is running on (default: 5000)"
    )
    parser.add_argument(
        "--regen",
        action="store_true",
        help="Automatically regenerate existing QR codes with the tunnel URL"
    )
    parser.add_argument(
        "--save-env",
        action="store_true",
        help="Save the assigned Cloudflare Tunnel URL to .env file"
    )
    args = parser.parse_args()

    cf_exe = find_cloudflared()
    if not cf_exe:
        print("ERROR: cloudflared executable not found!")
        print("Please place cloudflared.exe in this folder or install it.")
        sys.exit(1)

    print("=" * 65)
    print("Starting Cloudflare Tunnel on http://127.0.0.1:%s..." % args.port)
    print("=" * 65)

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
    url_pattern = re.compile(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com')

    start_time = time.time()
    for line in iter(cf_proc.stdout.readline, ''):
        if 'trycloudflare.com' in line or 'Registered tunnel connection' in line:
            match = url_pattern.search(line)
            if match:
                tunnel_url = match.group(0)
                break
        if time.time() - start_time > 30:
            break

    if not tunnel_url:
        print("Could not retrieve Cloudflare Tunnel URL within 30 seconds.")
        cf_proc.terminate()
        sys.exit(1)

    print("\n" + "=" * 65)
    print("  CLOUDFLARE TUNNEL ESTABLISHED SUCCESSFULLY!")
    print(f"  * Public HTTPS URL:    {tunnel_url}")
    print(f"  * Forwarding traffic:  http://127.0.0.1:{args.port}")
    print(f"  * QR Codes Should Use: {tunnel_url}")
    print("=" * 65)
    print("\nTo make your QR codes use this URL:")
    print(f"1. Set in .env:        PUBLIC_URL={tunnel_url}")
    print(f"2. Regenerate QR:      python regenerate_qr_codes.py --url {tunnel_url}\n")

    if args.save_env:
        from regenerate_qr_codes import update_env_public_url
        update_env_public_url(tunnel_url)

    if args.regen:
        print("Regenerating all existing QR codes with new tunnel URL...")
        from services.media_service import regenerate_all_qr_codes
        res = regenerate_all_qr_codes(new_base_url=tunnel_url)
        print(f"-> Successfully regenerated {res['regenerated_count']} QR codes.")

    print("\nTunnel is active. Press Ctrl+C to stop.\n" + "=" * 65)

    def cleanup(signum=None, frame=None):
        print("\nStopping Cloudflare Tunnel...")
        try:
            cf_proc.terminate()
            cf_proc.wait(timeout=3)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        for line in iter(cf_proc.stdout.readline, ''):
            pass
    except KeyboardInterrupt:
        cleanup()
    finally:
        cleanup()


if __name__ == '__main__':
    main()
