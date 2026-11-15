"""
LensQR Photo & Video QR Generator - Supabase Storage Service.
Manages private bucket operations, uploads for photos, videos, and QR codes,
server-side signed URL generation, and storage deletion.
"""

import io
import logging
from typing import Optional, List, Union
from config import Config
from services.supabase_service import get_supabase_client

logger = logging.getLogger(__name__)


def get_bucket_name() -> str:
    """Return the configured Supabase storage bucket name."""
    return Config.SUPABASE_STORAGE_BUCKET


def ensure_storage_bucket() -> bool:
    """
    Ensure the target private storage bucket exists in Supabase.
    Creates the bucket if missing.
    """
    client = get_supabase_client()
    if not client:
        return False

    bucket_name = get_bucket_name()
    try:
        buckets = client.storage.list_buckets()
        existing_names = [b.name for b in buckets]
        if bucket_name not in existing_names:
            client.storage.create_bucket(
                bucket_name, options={"public": False}
            )
            logger.info(f"Created private Supabase bucket: {bucket_name}")
        return True
    except Exception as e:
        logger.error(
            f"Error ensuring Supabase storage bucket {bucket_name}: {e}"
        )
        return False


def upload_media_to_storage(
    file_content: Union[bytes, io.BytesIO],
    storage_path: str,
    mime_type: str = "application/octet-stream"
) -> bool:
    """
    Upload media binary (photo or video) to private Supabase storage.
    """
    client = get_supabase_client()
    if not client:
        return False

    bucket_name = get_bucket_name()
    if isinstance(file_content, io.BytesIO):
        file_content.seek(0)
        data = file_content.read()
    else:
        data = file_content

    try:
        client.storage.from_(bucket_name).upload(
            path=storage_path,
            file=data,
            file_options={
                "content-type": mime_type,
                "upsert": "true"
            }
        )
        logger.info(
            f"Uploaded media to Supabase: {bucket_name}/{storage_path}"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed uploading {storage_path} to Supabase bucket "
            f"{bucket_name}: {e}"
        )
        return False


def upload_qr_to_storage(
    qr_content: Union[bytes, io.BytesIO],
    qr_storage_path: str
) -> bool:
    """
    Upload generated QR code PNG image to private Supabase storage.
    """
    return upload_media_to_storage(
        file_content=qr_content,
        storage_path=qr_storage_path,
        mime_type="image/png"
    )


def generate_signed_url(
    storage_path: str,
    expires_in: Optional[int] = None
) -> Optional[str]:
    """
    Generate a server-side short-lived signed URL for private media viewing
    or video streaming.
    """
    if not storage_path:
        return None

    client = get_supabase_client()
    if not client:
        return None

    bucket_name = get_bucket_name()
    expiry = expires_in or Config.SIGNED_URL_EXPIRY

    try:
        res = client.storage.from_(bucket_name).create_signed_url(
            storage_path, expiry
        )
        if isinstance(res, dict):
            return res.get("signedURL") or res.get("signedUrl")
        return getattr(res, "signed_url", None)
    except Exception as e:
        logger.error(
            f"Failed to create signed URL for {storage_path} in "
            f"{bucket_name}: {e}"
        )
        return None


def download_from_storage(storage_path: str) -> Optional[bytes]:
    """
    Download raw bytes of a file from the private Supabase storage bucket.
    """
    if not storage_path:
        return None

    client = get_supabase_client()
    if not client:
        return None

    bucket_name = get_bucket_name()
    try:
        return client.storage.from_(bucket_name).download(storage_path)
    except Exception as e:
        logger.error(
            f"Failed to download {storage_path} from {bucket_name}: {e}"
        )
        return None


def delete_from_storage(paths: Union[str, List[str]]) -> bool:
    """
    Delete one or more objects from the private Supabase storage bucket.
    """
    if not paths:
        return True

    client = get_supabase_client()
    if not client:
        return False

    bucket_name = get_bucket_name()
    path_list = [paths] if isinstance(paths, str) else paths

    try:
        client.storage.from_(bucket_name).remove(path_list)
        logger.info(
            f"Deleted {len(path_list)} objects from Supabase bucket "
            f"{bucket_name}"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed deleting objects from {bucket_name}: {e}"
        )
        return False
