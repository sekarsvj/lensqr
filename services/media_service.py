"""
LensQR Photo & Video QR Generator - Media Orchestration Service.
Orchestrates uploads, Supabase PostgreSQL metadata persistence,
Supabase Storage synchronization, QR code generation, and secure deletion.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from database.database import (
    save_media as save_local_media,
    get_media as get_local_media,
    delete_media as delete_local_media,
    format_file_size
)
from services.upload_service import (
    generate_creator_token,
    save_uploaded_file,
    delete_uploaded_file
)
from services.qr_service import generate_qr_code, delete_qr_file
from services.supabase_service import (
    is_supabase_available,
    save_media_to_db,
    get_media_from_db,
    delete_media_from_db,
    update_media_qr_style_in_db
)
from services.storage_service import generate_signed_url


def create_media(
    file_storage,
    media_type: str,
    title: str,
    description: str,
    qr_style: str,
    public_base_url: str
) -> Dict[str, Any]:
    """
    Validate and save uploaded media file to private storage,
    generate a high-resolution QR code, and persist metadata
    to Supabase PostgreSQL (with local JSON sync).
    """
    if media_type not in ['photo', 'video', 'document']:
        raise ValueError("Invalid media type. Must be 'photo', 'video', or 'document'.")

    # Validate and save binary file (local + Supabase Storage)
    file_info = save_uploaded_file(file_storage, media_type)

    # Generate UUID identifier for new media uploads
    media_id = str(uuid.uuid4())
    creator_token = generate_creator_token()

    # Target URL encoded in QR code pointing to Flask viewer
    target_url = f"{public_base_url}/m/{media_id}"

    # Generate QR code and sync to Supabase Storage
    qr_filename = generate_qr_code(target_url, media_id, style=qr_style)
    qr_storage_path = f"qr-codes/{qr_filename}"

    if media_type == 'photo':
        default_title = 'Photo'
    elif media_type == 'video':
        default_title = 'Video'
    else:
        default_title = file_info.get('original_name', 'Document')
    media_title = title.strip() if title else default_title

    # Construct unified metadata record
    record = {
        'id': media_id,
        'creator_token': creator_token,
        'type': media_type,
        'media_type': media_type,
        'title': media_title,
        'description': description.strip() if description else '',
        'original_name': file_info['original_name'],
        'original_filename': file_info['original_name'],
        'filename': file_info['filename'],
        'storage_path': file_info.get(
            'storage_path', f"{media_type}s/{file_info['filename']}"
        ),
        'mime_type': file_info['mime_type'],
        'size_bytes': file_info['file_size'],
        'file_size': file_info['file_size'],
        'qr_filename': qr_filename,
        'qr_code_path': qr_storage_path,
        'qr_style': qr_style,
        'access': 'unlisted',
        'views_count': 0,
        'is_active': True,
        'created_at': datetime.now(timezone.utc).isoformat()
    }

    # Persist to Supabase PostgreSQL if available
    if is_supabase_available():
        db_res = save_media_to_db(record)
        if db_res:
            record.update(db_res)

    # Maintain local JSON storage as backup/cache
    try:
        save_local_media(record)
    except Exception as e:
        print(f"Notice: Local JSON sync skipped: {e}")

    return record


def get_media(media_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve media metadata by ID. Queries Supabase PostgreSQL first,
    falling back to local JSON storage if necessary.
    """
    if not media_id:
        return None

    # Try Supabase PostgreSQL first
    if is_supabase_available():
        record = get_media_from_db(media_id)
        if record:
            return record

    # Fallback to local JSON storage
    return get_local_media(media_id)


def update_media_qr_style(
    media_id: str, new_style: str, public_base_url: str
) -> Dict[str, Any]:
    """
    Regenerate QR code with a new color palette without changing the media
    link. Synchronizes new QR image to Supabase Storage and updates metadata.
    """
    record = get_media(media_id)
    if not record:
        raise ValueError("Media record not found.")

    old_qr_filename = record.get('qr_filename')
    target_url = f"{public_base_url}/m/{media_id}"

    # Generate new QR code PNG
    new_qr_filename = generate_qr_code(target_url, media_id, style=new_style)
    new_qr_path = f"qr-codes/{new_qr_filename}"

    # Clean up old QR file if filename changed
    if old_qr_filename and old_qr_filename != new_qr_filename:
        delete_qr_file(old_qr_filename)

    record['qr_filename'] = new_qr_filename
    record['qr_code_path'] = new_qr_path
    record['qr_style'] = new_style

    # Update in Supabase PostgreSQL
    if is_supabase_available():
        update_media_qr_style_in_db(media_id, new_style, new_qr_path)

    # Update in local JSON storage
    try:
        save_local_media(record)
    except Exception:
        pass

    return record


def delete_media_and_files(
    media_id: str, creator_token: str
) -> Tuple[bool, str, int]:
    """
    Verify creator token, remove media and QR files from local disk and
    private Supabase Storage, and remove metadata.
    """
    record = get_media(media_id)
    if not record:
        return False, "Media not found.", 404

    expected_token = record.get('creator_token')
    if not creator_token or creator_token != expected_token:
        return False, "Unauthorized. Valid creator token is required.", 403

    # Delete media file from local disk and Supabase Storage
    delete_uploaded_file(
        record.get('filename'),
        record.get('type') or record.get('media_type'),
        storage_path=record.get('storage_path')
    )

    # Delete QR code image from local disk and Supabase Storage
    delete_qr_file(record.get('qr_filename') or '', media_id=media_id)

    # Soft-delete from Supabase PostgreSQL
    if is_supabase_available():
        delete_media_from_db(media_id)

    # Remove from local JSON storage
    try:
        delete_local_media(media_id)
    except Exception:
        pass

    return True, "Media and QR code deleted successfully.", 200


def get_signed_media_url(
    record: Dict[str, Any], expires_in: Optional[int] = None
) -> Optional[str]:
    """
    Generate a server-side short-lived signed URL for private viewing.
    """
    if not record:
        return None

    storage_path = record.get('storage_path')
    if not storage_path:
        mtype = record.get('type') or record.get('media_type') or 'photo'
        if mtype == 'photo':
            subfolder = 'photos'
        elif mtype == 'video':
            subfolder = 'videos'
        else:
            subfolder = 'documents'
        storage_path = f"{subfolder}/{record.get('filename')}"

    return generate_signed_url(storage_path, expires_in=expires_in)


def format_media_dict(
    record: Dict[str, Any], public_base_url: str
) -> Optional[Dict[str, Any]]:
    """Format record for public API / JSON presentation."""
    if not record:
        return None

    media_id = record['id']
    media_type = record.get('type') or record.get('media_type') or 'photo'
    if media_type == 'photo':
        default_title = 'Photo'
    elif media_type == 'video':
        default_title = 'Video'
    else:
        default_title = record.get('original_name') or 'Document'
    size_val = record.get('size_bytes') or record.get('file_size') or 0

    return {
        'id': media_id,
        'type': media_type,
        'media_type': media_type,
        'title': record.get('title') or default_title,
        'description': record.get('description', ''),
        'original_name': record.get('original_name') or record.get(
            'original_filename', ''
        ),
        'mime_type': record.get('mime_type', ''),
        'size_bytes': size_val,
        'formatted_size': format_file_size(size_val),
        'access': record.get('access', 'unlisted'),
        'qr_style': record.get('qr_style', 'classic'),
        'qr_url': f"{public_base_url}/qr-image/{record.get('qr_filename')}",
        'media_url': f"{public_base_url}/m/{media_id}",
        'file_url': f"{public_base_url}/media-file/{media_id}",
        'created_at': record.get('created_at')
    }


def regenerate_all_qr_codes(
    new_base_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Regenerate all existing QR codes with the current or provided base URL
    without re-uploading or modifying existing media files.
    Preserves all media IDs, titles, descriptions, and file locations.
    """
    from config import resolve_public_base_url
    base_url = (new_base_url or resolve_public_base_url()).rstrip('/')

    records_map: Dict[str, Dict[str, Any]] = {}

    # 1. Local JSON records
    try:
        from database.database import read_data
        local_data = read_data()
        for r in local_data.get('media', []):
            if r.get('id'):
                records_map[r['id']] = r
    except Exception as e:
        print(f"Notice: local records read skipped: {e}")

    # 2. Supabase records
    if is_supabase_available():
        try:
            from services.supabase_service import list_media_from_db
            db_records = list_media_from_db(limit=1000)
            for r in db_records:
                if r.get('id'):
                    records_map[r['id']] = r
        except Exception as e:
            print(f"Notice: Supabase records read skipped: {e}")

    updated_ids = []
    errors = []

    for media_id, record in records_map.items():
        try:
            style = record.get('qr_style', 'classic')
            target_url = f"{base_url}/m/{media_id}"

            # Generate new QR code PNG
            new_qr_filename = generate_qr_code(
                target_url, media_id, style=style
            )
            new_qr_path = f"qr-codes/{new_qr_filename}"

            record['qr_filename'] = new_qr_filename
            record['qr_code_path'] = new_qr_path

            # Update Supabase DB
            if is_supabase_available():
                update_media_qr_style_in_db(media_id, style, new_qr_path)

            # Update local JSON
            try:
                save_local_media(record)
            except Exception:
                pass

            updated_ids.append(media_id)
        except Exception as e:
            errors.append(f"Failed regenerating QR for {media_id}: {e}")

    return {
        'success': True,
        'base_url': base_url,
        'total_found': len(records_map),
        'regenerated_count': len(updated_ids),
        'regenerated_ids': updated_ids,
        'errors': errors
    }
