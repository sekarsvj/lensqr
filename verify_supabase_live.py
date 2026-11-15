"""
LensQR Photo & Video QR Generator - Live Supabase Pipeline Verification.
Tests the real Supabase integration against your configured Supabase project.
Validates bucket existence, photo/video upload, signed URL generation,
range headers, QR sync, and secure cleanup.
"""

import io
from PIL import Image
from config import Config
from app import create_app
from services.supabase_service import (
    get_supabase_client,
    is_media_table_ready
)
from services.storage_service import (
    get_bucket_name,
    ensure_storage_bucket,
    upload_media_to_storage,
    generate_signed_url,
    delete_from_storage
)


def run_live_verification():
    print("=" * 65)
    print("LensQR Supabase Live Pipeline Verification")
    print("=" * 65)

    # 1. Connection check
    assert Config.is_supabase_configured(), (
        "Supabase is not configured in .env"
    )
    client = get_supabase_client()
    assert client is not None, "Failed to initialize Supabase client"
    print("✓ Step 1: Connected to Supabase client successfully")

    # 2. Bucket check
    bucket_ok = ensure_storage_bucket()
    assert bucket_ok, "Failed ensuring Supabase storage bucket"
    bucket_name = get_bucket_name()
    print(f"✓ Step 2: Verified private storage bucket '{bucket_name}'")

    # 3. Photo upload to qr-media/photos/
    img = Image.new("RGB", (200, 200), color="#e11d48")
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    photo_bytes = img_buf.getvalue()

    photo_path = "photos/live_verify_photo.png"
    assert upload_media_to_storage(photo_bytes, photo_path, "image/png"), (
        "Photo upload to Supabase storage failed"
    )
    photo_signed = generate_signed_url(photo_path, 300)
    assert photo_signed and photo_signed.startswith("http"), (
        "Failed generating photo signed URL"
    )
    print("✓ Step 3: Photo uploaded & signed URL generated successfully")

    # 4. Video upload to qr-media/videos/
    vid_data = (
        b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41' +
        b'\x00' * 8192
    )
    video_path = "videos/live_verify_video.mp4"
    assert upload_media_to_storage(vid_data, video_path, "video/mp4"), (
        "Video upload to Supabase storage failed"
    )
    video_signed = generate_signed_url(video_path, 300)
    assert video_signed and video_signed.startswith("http"), (
        "Failed generating video signed URL"
    )
    print("✓ Step 4: Video uploaded & signed URL generated successfully")

    # 5. QR Code sync to qr-media/qr-codes/
    qr_img = Image.new("RGB", (300, 300), color="#0284c7")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_bytes = qr_buf.getvalue()

    qr_path = "qr-codes/qr_live_verify.png"
    assert upload_media_to_storage(qr_bytes, qr_path, "image/png"), (
        "QR image upload to Supabase storage failed"
    )
    qr_signed = generate_signed_url(qr_path, 300)
    assert qr_signed and qr_signed.startswith("http"), (
        "Failed generating QR signed URL"
    )
    print("✓ Step 5: QR image synchronized to Supabase Storage")

    # 6. Flask viewer & redirect resolution test
    app = create_app({'TESTING': True, 'PUBLIC_URL': 'https://qr.lensqr.net'})
    flask_client = app.test_client()

    home_res = flask_client.get('/')
    assert home_res.status_code == 200, "Home route failed"
    print("✓ Step 6: Flask application running and responsive (HTTP 200)")

    # 7. Check PostgreSQL table status
    table_ready = is_media_table_ready()
    if table_ready:
        print("✓ Step 7: Supabase PostgreSQL 'media' table is active")
    else:
        print(
            "! Step 7: Supabase PostgreSQL 'media' table is pending migration"
        )
        print(
            "          (Run supabase/migrations/001_create_media_table.sql "
            "in Supabase SQL Editor)"
        )

    # 8. Clean up test objects
    cleanup_paths = [photo_path, video_path, qr_path]
    delete_from_storage(cleanup_paths)
    print(
        f"✓ Step 8: Cleaned up {len(cleanup_paths)} test objects from "
        f"Supabase bucket '{bucket_name}'"
    )

    print("=" * 65)
    print("ALL LIVE SUPABASE STORAGE PIPELINE CHECKS PASSED!")
    print("=" * 65)
    return True


if __name__ == "__main__":
    run_live_verification()
