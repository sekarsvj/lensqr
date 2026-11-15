"""
LensQR Photo & Video QR Generator - Supabase Data Migration Tool.
Migrates existing local JSON metadata, uploaded photos/videos, and QR codes
to private Supabase Storage ('qr-media') and Supabase PostgreSQL ('media').
Preserves all legacy IDs and is safely repeatable.
"""

import json
import logging
import os
import sys
from dotenv import load_dotenv

from config import Config
from services.storage_service import (
    ensure_storage_bucket,
    upload_media_to_storage,
    upload_qr_to_storage,
    generate_signed_url
)
from services.supabase_service import (
    get_supabase_client,
    is_media_table_ready,
    save_media_to_db
)

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("migration")


def run_migration() -> bool:
    """Execute repeatable migration of local files and metadata to Supabase."""
    print("=" * 65)
    print("LensQR Supabase Migration: Files & Metadata")
    print("=" * 65)

    if not Config.is_supabase_configured():
        logger.error(
            "Supabase is not configured in .env. "
            "Please configure SUPABASE_URL and SUPABASE_SECRET_KEY."
        )
        return False

    client = get_supabase_client()
    if not client:
        logger.error("Could not initialize Supabase client.")
        return False

    # 1. Ensure private storage bucket exists
    if not ensure_storage_bucket():
        logger.error(
            f"Failed to access bucket: {Config.SUPABASE_STORAGE_BUCKET}"
        )
        return False
    print(
        f"✓ Supabase private bucket verified: {Config.SUPABASE_STORAGE_BUCKET}"
    )

    # 2. Check table status
    table_ready = is_media_table_ready()
    if table_ready:
        print("✓ Supabase PostgreSQL 'media' table is active and ready.")
    else:
        print("! Notice: Supabase PostgreSQL 'media' table not yet created.")
        print(
            "  Execute 'supabase/migrations/001_create_media_table.sql' "
            "in the Supabase SQL Editor to enable DB persistence."
        )

    # 3. Read existing JSON metadata
    json_path = Config.JSON_STORAGE_PATH
    if not os.path.exists(json_path):
        print(f"No existing metadata file at {json_path}. Nothing to migrate.")
        return True

    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse {json_path}: {e}")
            return False

    records = data.get("media", [])
    print(f"Found {len(records)} existing media records to migrate.\n")

    migrated_count = 0
    errors = 0

    for idx, rec in enumerate(records, start=1):
        media_id = rec.get("id")
        media_type = rec.get("type", "photo")
        filename = rec.get("filename")
        qr_filename = rec.get("qr_filename")

        print(
            f"[{idx}/{len(records)}] Migrating record ID: "
            f"{media_id} ({media_type})"
        )

        # Determine local and remote paths
        local_folder = (
            Config.UPLOAD_FOLDER_PHOTOS if media_type == "photo"
            else Config.UPLOAD_FOLDER_VIDEOS
        )
        local_file_path = (
            os.path.join(local_folder, filename) if filename else None
        )
        subfolder = "photos" if media_type == "photo" else "videos"
        remote_storage_path = f"{subfolder}/{filename}" if filename else None

        # Upload media file to Supabase Storage
        if local_file_path and os.path.isfile(local_file_path):
            with open(local_file_path, 'rb') as f:
                content = f.read()
            mime_type = rec.get("mime_type", "application/octet-stream")
            if upload_media_to_storage(
                content, remote_storage_path, mime_type
            ):
                test_url = generate_signed_url(remote_storage_path, 60)
                if test_url:
                    print(
                        f"  ✓ Uploaded & verified: {remote_storage_path}"
                    )
                else:
                    print(
                        f"  ! Signed URL failed: {remote_storage_path}"
                    )
            else:
                print(f"  ✗ Failed uploading {local_file_path}")
                errors += 1
        else:
            print(f"  ! Local media file missing: {local_file_path}")

        # Upload QR code image to Supabase Storage
        local_qr_path = (
            os.path.join(Config.QR_FOLDER, qr_filename)
            if qr_filename else None
        )
        remote_qr_path = f"qr-codes/{qr_filename}" if qr_filename else None

        if local_qr_path and os.path.isfile(local_qr_path):
            with open(local_qr_path, 'rb') as f:
                qr_content = f.read()
            if upload_qr_to_storage(qr_content, remote_qr_path):
                print(f"  ✓ Uploaded & verified QR: {remote_qr_path}")
            else:
                print(f"  ✗ Failed uploading QR {local_qr_path}")
                errors += 1

        # Synchronize metadata record to Supabase DB if table exists
        rec["storage_path"] = remote_storage_path
        rec["qr_code_path"] = remote_qr_path
        if table_ready:
            db_res = save_media_to_db(rec)
            if db_res:
                print(
                    f"  ✓ Metadata inserted to Supabase: {media_id}"
                )
            else:
                print(
                    f"  ✗ Failed metadata insert: {media_id}"
                )
                errors += 1

        migrated_count += 1

    print("\n" + "=" * 65)
    print(
        f"Migration finished: {migrated_count} records processed, "
        f"{errors} errors."
    )
    print("=" * 65)
    return errors == 0


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
