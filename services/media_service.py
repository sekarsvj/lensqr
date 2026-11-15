from datetime import datetime, timezone
from database.database import (
    save_media, get_media, delete_media, format_file_size
)
from services.upload_service import (
    generate_media_id, generate_creator_token,
    save_uploaded_file, delete_uploaded_file
)
from services.qr_service import generate_qr_code, delete_qr_file


def create_media(
        file_storage,
        media_type,
        title,
        description,
        qr_style,
        public_base_url):
    """
    Validate and save uploaded media file, generate QR code,
    and persist record in JSON storage.
    Returns the saved media record dict.
    """
    if media_type not in ['photo', 'video']:
        raise ValueError("Invalid media type. Must be 'photo' or 'video'.")

    # Validate and save binary file
    file_info = save_uploaded_file(file_storage, media_type)

    media_id = generate_media_id()
    creator_token = generate_creator_token()

    # Target URL encoded in QR code
    target_url = f"{public_base_url}/m/{media_id}"

    # Generate QR code
    qr_filename = generate_qr_code(target_url, media_id, style=qr_style)

    # Construct metadata record
    record = {
        'id': media_id,
        'creator_token': creator_token,
        'type': media_type,
        'title': title.strip() if title else (
            'Photo' if media_type == 'photo' else 'Video'),
        'description': description.strip() if description else '',
        'original_name': file_info['original_name'],
        'filename': file_info['filename'],
        'mime_type': file_info['mime_type'],
        'size_bytes': file_info['file_size'],
        'qr_filename': qr_filename,
        'qr_style': qr_style,
        'access': 'unlisted',
        'views_count': 0,
        'created_at': datetime.now(
            timezone.utc).isoformat()}

    # Save to JSON storage
    save_media(record)
    return record


def update_media_qr_style(media_id, new_style, public_base_url):
    """
    Regenerate QR code with a new color palette without changing the media
    link.
    """
    record = get_media(media_id)
    if not record:
        raise ValueError("Media record not found.")

    old_qr_filename = record.get('qr_filename')
    target_url = f"{public_base_url}/m/{media_id}"

    # Generate new QR code
    new_qr_filename = generate_qr_code(target_url, media_id, style=new_style)

    # Clean up old QR file if filename changed
    if old_qr_filename and old_qr_filename != new_qr_filename:
        delete_qr_file(old_qr_filename)

    record['qr_filename'] = new_qr_filename
    record['qr_style'] = new_style
    save_media(record)
    return record


def delete_media_and_files(media_id, creator_token):
    """
    Verify creator token, remove uploaded photo/video and QR code from disk,
    and remove metadata from JSON storage.
    """
    record = get_media(media_id)
    if not record:
        return False, "Media not found.", 404

    expected_token = record.get('creator_token')
    if not creator_token or creator_token != expected_token:
        return False, "Unauthorized. Valid creator token is required.", 403

    # Delete uploaded media file from disk
    delete_uploaded_file(record.get('filename'), record.get('type'))

    # Delete QR code image from disk
    delete_qr_file(record.get('qr_filename'), media_id=media_id)

    # Remove from JSON storage
    delete_media(media_id)
    return True, "Media and QR code deleted successfully.", 200


def format_media_dict(record, public_base_url):
    """Format record for public API / JSON presentation."""
    if not record:
        return None

    media_id = record['id']
    default_title = 'Photo' if record['type'] == 'photo' else 'Video'
    return {
        'id': media_id,
        'type': record['type'],
        'title': record.get('title') or default_title,
        'description': record.get('description', ''),
        'original_name': record['original_name'],
        'mime_type': record['mime_type'],
        'size_bytes': record['size_bytes'],
        'formatted_size': format_file_size(record['size_bytes']),
        'access': record.get('access', 'unlisted'),
        'qr_style': record.get('qr_style', 'classic'),
        'qr_url': f"{public_base_url}/qr-image/{record['qr_filename']}",
        'media_url': f"{public_base_url}/m/{media_id}",
        'file_url': f"{public_base_url}/media-file/{media_id}",
        'created_at': record.get('created_at')
    }
