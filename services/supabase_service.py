"""
LensQR Photo & Video QR Generator - Supabase Client & Database Service.
Handles Supabase client initialization, connection verification,
and PostgreSQL metadata operations for the 'media' table.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from config import Config

logger = logging.getLogger(__name__)

# Global client cache
_supabase_client = None


def get_supabase_client():
    """
    Initialize or return the cached official Supabase Python client.
    Uses backend service credentials (SUPABASE_KEY).
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not Config.is_supabase_configured():
        logger.warning(
            "Supabase credentials are not configured. Running in local mode."
        )
        return None

    try:
        from supabase import create_client
        _supabase_client = create_client(
            Config.SUPABASE_URL,
            Config.SUPABASE_KEY
        )
        logger.info("Supabase client initialized successfully.")
        return _supabase_client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None


def is_supabase_available() -> bool:
    """Return True if Supabase client is configured and initialized."""
    return get_supabase_client() is not None


def is_media_table_ready() -> bool:
    """
    Check if the 'media' table is available and queryable in Supabase.
    Returns False if table has not yet been migrated.
    """
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("media").select("id").limit(1).execute()
        return True
    except Exception as e:
        logger.debug(f"Media table not ready in Supabase: {e}")
        return False


def _normalize_db_record(row: Any) -> Dict[str, Any]:
    """
    Convert a Supabase DB row into a standardized media dictionary,
    preserving both legacy and modern column aliases for backward
    compatibility.
    """
    if not isinstance(row, dict):
        return {}

    media_type = row.get("media_type") or row.get("type") or "photo"
    storage_path = (
        row.get("storage_path") or row.get("filename") or ""
    )
    if storage_path.startswith("links/") or row.get("mime_type") == "text/uri-list":
        media_type = "url"
    elif storage_path.startswith("documents/") or (row.get("mime_type") and not row.get("mime_type").startswith(("image/", "video/"))):
        media_type = "document"
    local_filename = os.path.basename(storage_path) if storage_path else ""
    original_name = (
        row.get("original_filename") or row.get("original_name") or ""
    )
    file_size = int(row.get("file_size") or row.get("size_bytes") or 0)
    qr_path = row.get("qr_code_path") or row.get("qr_filename") or ""
    qr_filename = os.path.basename(qr_path) if qr_path else ""

    return {
        "id": row.get("id"),
        "type": media_type,
        "media_type": media_type,
        "title": row.get("title") or (
            "Photo" if media_type == "photo" else ("Video" if media_type == "video" else ("Web Link" if media_type == "url" else "Document"))
        ),
        "target_url": row.get("target_url") or (original_name if media_type == "url" else ""),
        "description": row.get("description") or "",
        "original_name": original_name,
        "original_filename": original_name,
        "filename": local_filename,
        "storage_path": storage_path,
        "mime_type": row.get("mime_type") or "",
        "size_bytes": file_size,
        "file_size": file_size,
        "qr_filename": qr_filename,
        "qr_code_path": qr_path,
        "qr_style": row.get("qr_style") or "classic",
        "creator_token": row.get("creator_token") or "",
        "access": row.get("access") or "unlisted",
        "views_count": int(row.get("views_count") or 0),
        "is_active": row.get("is_active", True),
        "created_at": row.get("created_at") or ""
    }


def save_media_to_db(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Persist or update a media record in Supabase PostgreSQL 'media' table.
    Returns normalized record on success or None on failure.
    """
    client = get_supabase_client()
    if not client:
        return None

    media_type = record.get("media_type") or record.get("type") or "photo"
    storage_path = record.get("storage_path") or record.get("filename") or ""
    orig_name = (
        record.get("original_filename") or record.get("original_name") or ""
    )
    size = int(record.get("file_size") or record.get("size_bytes") or 0)
    qr_path = record.get("qr_code_path") or record.get("qr_filename") or ""

    row_data = {
        "id": record["id"],
        "media_type": media_type,
        "title": record.get("title", ""),
        "description": record.get("description", ""),
        "original_filename": orig_name,
        "storage_path": storage_path,
        "mime_type": record.get("mime_type", ""),
        "file_size": size,
        "qr_code_path": qr_path,
        "qr_style": record.get("qr_style", "classic"),
        "creator_token": record.get("creator_token", ""),
        "access": record.get("access", "unlisted"),
        "views_count": int(record.get("views_count", 0)),
        "is_active": bool(record.get("is_active", True))
    }

    if record.get("created_at"):
        row_data["created_at"] = record["created_at"]

    try:
        res = client.table("media").upsert(row_data).execute()
        if res.data and len(res.data) > 0:
            return _normalize_db_record(res.data[0])
        return _normalize_db_record(row_data)
    except Exception as e:
        err_msg = str(e)
        if "media_media_type_check" in err_msg and media_type in ("document", "url"):
            logger.warning(
                f"Remote Supabase DB has legacy media_type constraint. "
                f"Saving {media_type} with DB-fallback media_type='photo' and storage_path."
            )
            try:
                fallback_data = dict(row_data)
                fallback_data["media_type"] = "photo"
                res = client.table("media").upsert(fallback_data).execute()
                if res.data and len(res.data) > 0:
                    norm = _normalize_db_record(res.data[0])
                    norm["type"] = media_type
                    norm["media_type"] = media_type
                    return norm
                norm = _normalize_db_record(fallback_data)
                norm["type"] = media_type
                norm["media_type"] = media_type
                return norm
            except Exception as inner_e:
                logger.error(f"Fallback save to Supabase also failed: {inner_e}")
                return None
                return norm
            except Exception as inner_e:
                logger.error(f"Fallback save to Supabase also failed: {inner_e}")
                return None
        logger.error(
            f"Failed to save media {record.get('id')} to Supabase: {e}"
        )
        return None


def get_media_from_db(media_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve an active media record from Supabase PostgreSQL by unique ID.
    Returns normalized dictionary or None if not found or inactive.
    """
    if not media_id:
        return None

    client = get_supabase_client()
    if not client:
        return None

    try:
        res = (
            client.table("media")
            .select("*")
            .eq("id", media_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return _normalize_db_record(res.data[0])
        return None
    except Exception as e:
        logger.error(f"Error fetching media {media_id} from Supabase DB: {e}")
        return None


def list_media_from_db(limit: int = 100) -> List[Dict[str, Any]]:
    """
    List recent active media records from Supabase PostgreSQL.
    """
    client = get_supabase_client()
    if not client:
        return []

    try:
        res = (
            client.table("media")
            .select("*")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [_normalize_db_record(r) for r in (res.data or [])]
    except Exception as e:
        logger.error(f"Error listing media from Supabase DB: {e}")
        return []


def delete_media_from_db(media_id: str) -> bool:
    """
    Soft-delete a record in Supabase PostgreSQL by setting is_active=False.
    """
    if not media_id:
        return False

    client = get_supabase_client()
    if not client:
        return False

    try:
        res = (
            client.table("media")
            .update({"is_active": False})
            .eq("id", media_id)
            .execute()
        )
        return bool(res.data)
    except Exception as e:
        logger.error(f"Error deleting media {media_id} from Supabase DB: {e}")
        return False


def update_media_qr_style_in_db(
    media_id: str, new_style: str, qr_code_path: str
) -> Optional[Dict[str, Any]]:
    """
    Update QR palette and QR code object path in Supabase PostgreSQL.
    """
    client = get_supabase_client()
    if not client:
        return None

    try:
        res = (
            client.table("media")
            .update({
                "qr_style": new_style,
                "qr_code_path": qr_code_path
            })
            .eq("id", media_id)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return _normalize_db_record(res.data[0])
        return None
    except Exception as e:
        logger.error(f"Failed to update QR style for {media_id} in DB: {e}")
        return None
