"""
LensQR Photo & Video QR Generator - Batch QR Code Regeneration Tool.
Regenerates all existing QR codes to point to a production, Cloudflare Tunnel,
or LAN URL without modifying or re-uploading the original media files.
"""

import argparse
import os
import re
import sys
from dotenv import load_dotenv

load_dotenv()

from config import Config, resolve_public_base_url, is_loopback  # noqa: E402
from services.media_service import regenerate_all_qr_codes  # noqa: E402


def update_env_public_url(new_url: str):
    """Safely update or add PUBLIC_URL in .env file."""
    env_path = os.path.join(Config.BASE_DIR, '.env')
    if not os.path.isfile(env_path):
        return

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if re.search(r'^PUBLIC_URL=', content, flags=re.MULTILINE):
            new_content = re.sub(
                r'^PUBLIC_URL=.*$',
                f'PUBLIC_URL={new_url}',
                content,
                flags=re.MULTILINE
            )
        else:
            new_content = content + f"\nPUBLIC_URL={new_url}\n"

        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated .env with PUBLIC_URL={new_url}")
    except Exception as e:
        print(f"Notice: Could not update .env: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch regenerate QR codes with effective public URL."
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Target base public URL (e.g. https://xxx.trycloudflare.com)"
    )
    parser.add_argument(
        "--save-env",
        action="store_true",
        help="Save the specified target URL into .env as PUBLIC_URL"
    )
    args = parser.parse_args()

    if args.url:
        os.environ['PUBLIC_URL'] = args.url.strip().rstrip('/')
        if args.save_env:
            update_env_public_url(args.url.strip().rstrip('/'))

    target_base = (args.url or resolve_public_base_url()).strip().rstrip('/')

    print("=" * 65)
    print("LensQR: Batch QR Code Regeneration Tool")
    print(f"Target Public Base URL: {target_base}")
    print("=" * 65)

    if is_loopback(target_base):
        print("! WARNING: Target URL contains loopback localhost / 127.0.0.1.")
        print("  People scanning these QR codes from other locations (e.g. Punjab)")
        print("  will NOT be able to connect! Expose via Cloudflare Tunnel:")
        print("    python run_with_tunnel.py")
        print("=" * 65)

    res = regenerate_all_qr_codes(new_base_url=target_base)

    print(f"Total media records found:  {res['total_found']}")
    print(f"Successfully regenerated:   {res['regenerated_count']}")
    
    if res.get('regenerated_ids'):
        print("\nRegenerated Media Items:")
        for mid in res['regenerated_ids']:
            print(f"  * {mid} -> {target_base}/m/{mid}")

    if res['errors']:
        print("\nErrors encountered:")
        for err in res['errors']:
            print(f"  - {err}")
    else:
        print("\nAll existing media files and IDs were safely preserved!")
    print("=" * 65)

    return 0 if not res['errors'] else 1


if __name__ == "__main__":
    sys.exit(main())

