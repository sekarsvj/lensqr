"""
LensQR Photo & Video QR Generator - Batch QR Code Regeneration Tool.
Regenerates all existing QR codes to point to a production or LAN URL
without modifying or re-uploading the original media files.
"""

import argparse
import sys
from dotenv import load_dotenv

load_dotenv()

from config import Config, resolve_public_base_url  # noqa: E402
from services.media_service import regenerate_all_qr_codes  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Batch regenerate QR codes with effective public URL."
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Target base public URL (e.g. https://qr.lensqr.net)"
    )
    args = parser.parse_args()

    target_base = args.url or resolve_public_base_url()

    print("=" * 65)
    print("LensQR: Batch QR Code Regeneration Tool")
    print(f"Target Public Base URL: {target_base}")
    print("=" * 65)

    if "localhost" in target_base or "127.0.0.1" in target_base:
        print("! WARNING: Target URL contains loopback localhost / 127.0.0.1.")
        print("  Mobile devices scanning these QR codes will not be able")
        print("  to connect unless using a LAN IP or public domain.")

    res = regenerate_all_qr_codes(new_base_url=target_base)

    print(f"Total media records found:  {res['total_found']}")
    print(f"Successfully regenerated:   {res['regenerated_count']}")
    if res['errors']:
        print("Errors encountered:")
        for err in res['errors']:
            print(f"  - {err}")
    else:
        print("All existing media files and IDs were safely preserved!")
    print("=" * 65)

    return 0 if not res['errors'] else 1


if __name__ == "__main__":
    sys.exit(main())

