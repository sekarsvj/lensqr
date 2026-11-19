import os
import json
import shutil
import threading
from datetime import datetime
from config import Config

_storage_lock = threading.Lock()

REQUIRED_FIELDS = {
    'id', 'type', 'original_name', 'filename',
    'mime_type', 'size_bytes', 'qr_filename', 'access', 'created_at'
}


def get_storage_path():
    """Retrieve current configured path to the JSON storage file."""
    return getattr(
        Config,
        'JSON_STORAGE_PATH',
        os.path.join(
            Config.BASE_DIR,
            'data',
            'media.json'))


def initialize_storage():
    """
    Ensure the data directory and media.json file exist with valid structure.
    Never overwrites an existing valid or corrupted database silently.
    """
    path = get_storage_path()
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)

    with _storage_lock:
        if not os.path.exists(path):
            initial_data = {"media": []}
            _write_data_unlocked(initial_data, path)
        else:
            # Verify file integrity
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                if not isinstance(
                        content,
                        dict) or "media" not in content or not isinstance(
                        content["media"],
                        list):
                    raise ValueError(
                        "JSON storage format invalid (missing 'media' array)."
                    )
            except Exception as e:
                # Corrupted JSON detected - do not overwrite! Create emergency
                # copy.
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                corrupt_backup = f"{path}.corrupted_{timestamp}"
                shutil.copy2(path, corrupt_backup)
                raise RuntimeError(
                    f"Corrupted database file at {path}! "
                    f"Preserved data to {corrupt_backup}. Error: {str(e)}"
                )


def _read_data_unlocked(path):
    """Internal helper to read and parse the JSON file without locking."""
    if not os.path.exists(path):
        return {"media": []}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(
                data,
                dict) or "media" not in data or not isinstance(
                data["media"],
                list):
            raise ValueError(
                "Invalid metadata format: root must be dict with 'media' list."
            )
        return data
    except json.JSONDecodeError as jde:
        raise RuntimeError(
            f"Corrupted JSON in storage file {path}: {str(jde)}"
        )


def read_data():
    """
    Safely read all media records from the JSON database under thread lock.
    Returns dict: {"media": [...]}
    """
    path = get_storage_path()
    with _storage_lock:
        return _read_data_unlocked(path)


def _write_data_unlocked(data, path):
    """
    Internal helper to perform atomic file writing with flush and sync.
    Writes to a temporary file in the same directory, then renames.
    """
    if not isinstance(
            data,
            dict) or "media" not in data or not isinstance(
            data["media"],
            list):
        raise ValueError(
            "Cannot write invalid data structure. Expected dict with 'media'."
        )

    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    temp_path = f"{path}.tmp_{os.getpid()}_{threading.get_ident()}"

    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        # Atomic file replacement (Windows and POSIX compliant)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def write_data(data):
    """
    Atomically write metadata to the JSON storage file under thread lock.
    """
    path = get_storage_path()
    with _storage_lock:
        _write_data_unlocked(data, path)


def validate_record(record):
    """
    Validate that a media record contains all mandatory fields with correct
    types.
    """
    if not isinstance(record, dict):
        raise ValueError("Record must be a dictionary.")

    missing = REQUIRED_FIELDS - set(record.keys())
    if missing:
        missing_str = ', '.join(sorted(missing))
        raise ValueError(f"Record is missing required fields: {missing_str}")

    if record['type'] not in ['photo', 'video', 'document']:
        raise ValueError("Record 'type' must be 'photo', 'video', or 'document'.")

    if not isinstance(record['id'], str) or not record['id'].strip():
        raise ValueError("Record 'id' must be a non-empty string.")

    if not isinstance(record['size_bytes'], int) or record['size_bytes'] < 0:
        raise ValueError("Record 'size_bytes' must be a non-negative integer.")


def save_media(record):
    """
    Save or update a media record in JSON storage.
    Validates structure and ensures atomic write under thread lock.
    """
    validate_record(record)
    path = get_storage_path()

    with _storage_lock:
        data = _read_data_unlocked(path)
        existing_index = None
        for i, item in enumerate(data['media']):
            if item.get('id') == record['id']:
                existing_index = i
                break

        if existing_index is not None:
            data['media'][existing_index] = record
        else:
            data['media'].append(record)

        _write_data_unlocked(data, path)
        return record


def get_media(media_id):
    """
    Find and return a single media record by unique media_id, or None if
    missing.
    """
    if not media_id:
        return None
    data = read_data()
    for item in data.get('media', []):
        if item.get('id') == media_id:
            return item
    return None


def list_media(creator_token=None):
    """
    List media records. If creator_token is provided, returns only records
    belonging to that creator.
    """
    data = read_data()
    all_media = data.get('media', [])
    if creator_token:
        return [m for m in all_media if m.get(
            'creator_token') == creator_token]
    return all_media


def delete_media(media_id):
    """
    Remove a media record from the JSON storage file by media_id.
    Returns True if removed, False if not found.
    """
    if not media_id:
        return False

    path = get_storage_path()
    with _storage_lock:
        data = _read_data_unlocked(path)
        original_count = len(data.get('media', []))
        data['media'] = [
            m for m in data.get(
                'media',
                []) if m.get('id') != media_id]

        if len(data['media']) == original_count:
            return False

        _write_data_unlocked(data, path)
        return True


def format_file_size(size_in_bytes):
    """Format file size in bytes to a human-readable string."""
    if not size_in_bytes:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            return f"{
                size_in_bytes:.1f} {unit}" if unit != 'B' else f"{
                int(size_in_bytes)} B"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.1f} TB"
