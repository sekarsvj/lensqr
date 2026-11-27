import os
import uuid
import secrets
from PIL import Image
from werkzeug.utils import secure_filename
from config import Config


def generate_media_id():
    """
    Generate a cryptographically secure, URL-safe random string for media id.
    """
    # 10 to 12 alphanumeric characters
    return secrets.token_urlsafe(9).replace('-', '').replace('_', '')[:10]


def generate_creator_token():
    """
    Generate a 256-bit secret token for the media creator to manage/delete.
    """
    return secrets.token_hex(32)


def get_file_extension(filename):
    """Safely extract lowercase extension without leading dot."""
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()


def is_allowed_file(filename, media_type):
    """Check if file extension is allowed for the given media type."""
    ext = get_file_extension(filename)
    if media_type == 'photo':
        return ext in Config.ALLOWED_PHOTO_EXTENSIONS
    elif media_type == 'video':
        return ext in Config.ALLOWED_VIDEO_EXTENSIONS
    elif media_type == 'document':
        return ext in Config.ALLOWED_DOCUMENT_EXTENSIONS
    return False


def validate_magic_bytes(file_stream, ext):
    """
    Validate magic bytes / file header signatures to verify file type matches.
    Rewinds the stream to position 0 when finished.
    """
    file_stream.seek(0)
    header = file_stream.read(64)
    file_stream.seek(0)

    if len(header) < 4:
        return False, "Uploaded file is empty or corrupted."

    # Prevent executable file uploads under any circumstances
    if header.startswith(b'MZ') or header.startswith(b'\x7FELF'):
        return False, "Executable binaries are not permitted."

    if ext in ['jpg', 'jpeg']:
        if not header.startswith(b'\xFF\xD8\xFF'):
            return False, "Invalid JPEG file signature."
    elif ext == 'png':
        if not header.startswith(b'\x89PNG\r\n\x1a\n'):
            return False, "Invalid PNG file signature."
    elif ext == 'webp':
        if not (header.startswith(b'RIFF') and len(
                header) >= 12 and header[8:12] == b'WEBP'):
            return False, "Invalid WEBP file signature."
    elif ext == 'webm':
        if not header.startswith(b'\x1A\x45\xDF\xA3'):
            return False, "Invalid WebM video file signature."
    elif ext in ['mp4', 'mov']:
        if len(header) >= 8:
            box_type = header[4:8]
            valid_boxes = [
                b'ftyp', b'moov', b'mdat', b'wide', b'free', b'skip'
            ]
            if box_type not in valid_boxes:
                return False, "Invalid MP4/MOV video file container."
        else:
            return False, "Invalid video container header structure."
    elif ext == 'pdf':
        if not header.startswith(b'%PDF-'):
            return False, "Invalid PDF file signature."
    elif ext in ['docx', 'xlsx', 'pptx', 'odt', 'ods', 'odp', 'zip']:
        if not header.startswith(b'PK\x03\x04') and not header.startswith(b'PK\x05\x06'):
            return False, f"Invalid Office/Zip archive signature for .{ext}."
    elif ext in ['doc', 'xls', 'ppt']:
        if not header.startswith(b'\xD0\xCF\x11\xE0'):
            return False, f"Invalid legacy Office document signature for .{ext}."

    return True, None


def validate_image_integrity(file_stream, ext):
    """
    Verify that an image file can actually be parsed and opened by Pillow.
    """
    try:
        file_stream.seek(0)
        img = Image.open(file_stream)
        # Verifies file integrity without decoding whole pixel array
        img.verify()
        file_stream.seek(0)
        return True, None
    except Exception as e:
        file_stream.seek(0)
        return False, f"Image file is corrupted or unprocessable: {str(e)}"


def save_uploaded_file(file_storage, media_type):
    """
    Validates, renames, and saves an uploaded FileStorage object.
    Returns dict with (filename, original_name, file_size, mime_type).
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No file selected for upload.")

    raw_filename = file_storage.filename
    clean_original = secure_filename(raw_filename)
    if not clean_original:
        clean_original = f"media_{secrets.token_hex(4)}"

    ext = get_file_extension(raw_filename)
    if not ext or not is_allowed_file(raw_filename, media_type):
        if media_type == 'photo':
            allowed = Config.ALLOWED_PHOTO_EXTENSIONS
        elif media_type == 'video':
            allowed = Config.ALLOWED_VIDEO_EXTENSIONS
        else:
            allowed = Config.ALLOWED_DOCUMENT_EXTENSIONS
        raise ValueError(
            f"File format '.{ext}' is not supported for {media_type} QR. "
            f"Permitted formats: {', '.join(sorted(allowed))}"
        )

    # Measure file size
    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)

    if file_size == 0:
        raise ValueError("Uploaded file is completely empty.")

    # Check max file size
    if media_type == 'photo':
        max_limit = Config.MAX_PHOTO_SIZE
        max_mb = Config.MAX_PHOTO_MB
    elif media_type == 'video':
        max_limit = Config.MAX_VIDEO_SIZE
        max_mb = Config.MAX_VIDEO_MB
    else:
        max_limit = Config.MAX_DOCUMENT_SIZE
        max_mb = Config.MAX_DOCUMENT_MB

    if file_size > max_limit:
        raise ValueError(
            f"File exceeds the maximum permitted size of {max_mb} MB.")

    # Validate magic bytes
    valid_sig, sig_err = validate_magic_bytes(file_storage.stream, ext)
    if not valid_sig:
        raise ValueError(sig_err)

    # Validate photo image integrity
    if media_type == 'photo':
        valid_img, img_err = validate_image_integrity(file_storage.stream, ext)
        if not valid_img:
            raise ValueError(img_err)

    # Generate cryptographically secure random server filename
    safe_filename = f"{uuid.uuid4().hex}.{ext}"
    if media_type == 'photo':
        subfolder = 'photos'
        target_dir = Config.UPLOAD_FOLDER_PHOTOS
    elif media_type == 'video':
        subfolder = 'videos'
        target_dir = Config.UPLOAD_FOLDER_VIDEOS
    else:
        subfolder = 'documents'
        target_dir = Config.UPLOAD_FOLDER_DOCUMENTS

    storage_path = f"{subfolder}/{safe_filename}"
    os.makedirs(target_dir, exist_ok=True)

    dest_path = os.path.join(target_dir, safe_filename)
    file_storage.save(dest_path)

    # MIME type detection
    mime_type = file_storage.content_type
    if not mime_type or mime_type == 'application/octet-stream':
        if ext in ['jpg', 'jpeg']:
            mime_type = 'image/jpeg'
        elif ext == 'png':
            mime_type = 'image/png'
        elif ext == 'webp':
            mime_type = 'image/webp'
        elif ext == 'mp4':
            mime_type = 'video/mp4'
        elif ext == 'mov':
            mime_type = 'video/quicktime'
        elif ext == 'webm':
            mime_type = 'video/webm'
        elif ext == 'pdf':
            mime_type = 'application/pdf'
        elif ext == 'doc':
            mime_type = 'application/msword'
        elif ext == 'docx':
            mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif ext == 'xls':
            mime_type = 'application/vnd.ms-excel'
        elif ext == 'xlsx':
            mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif ext == 'ppt':
            mime_type = 'application/vnd.ms-powerpoint'
        elif ext == 'pptx':
            mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        elif ext == 'txt':
            mime_type = 'text/plain'
        elif ext == 'rtf':
            mime_type = 'application/rtf'
        elif ext in ['csv', 'tsv']:
            mime_type = 'text/csv'
        elif ext == 'zip':
            mime_type = 'application/zip'
        elif ext == 'json':
            mime_type = 'application/json'
        elif ext == 'xml':
            mime_type = 'application/xml'
        else:
            mime_type = 'application/octet-stream'

    # Sync to Supabase Storage if configured
    try:
        from services.storage_service import upload_media_to_storage
        with open(dest_path, 'rb') as f:
            upload_media_to_storage(f.read(), storage_path, mime_type)
    except Exception as e:
        print(f"Warning: Could not sync {storage_path} to Supabase: {e}")

    return {
        'filename': safe_filename,
        'storage_path': storage_path,
        'original_name': clean_original[:120],
        'file_size': file_size,
        'mime_type': mime_type
    }


def delete_uploaded_file(filename, media_type, storage_path=None):
    """
    Safely delete an uploaded file from disk and private Supabase Storage.
    """
    if not filename or media_type == 'url':
        return

    # Delete from local filesystem
    if media_type == 'photo':
        folder = Config.UPLOAD_FOLDER_PHOTOS
        subfolder = 'photos'
    elif media_type == 'video':
        folder = Config.UPLOAD_FOLDER_VIDEOS
        subfolder = 'videos'
    else:
        folder = Config.UPLOAD_FOLDER_DOCUMENTS
        subfolder = 'documents'

    safe_name = os.path.basename(filename)
    path = os.path.join(folder, safe_name)
    if os.path.isfile(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Error deleting file {path}: {e}")

    # Delete from Supabase Storage
    try:
        from services.storage_service import delete_from_storage
        target_path = storage_path or f"{subfolder}/{safe_name}"
        delete_from_storage(target_path)
    except Exception as e:
        print(f"Warning: Could not delete {filename} from Supabase: {e}")
