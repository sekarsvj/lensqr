"""
LensQR Photo & Video QR Generator - QR Code Generation & Storage Service.
Generates high-resolution, print-ready QR codes with custom palettes,
persisting them both locally and in private Supabase Storage.
"""

import io
import os
from typing import Optional
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from qrcode.image.pil import PilImage
from config import Config
from services.storage_service import (
    upload_qr_to_storage,
    delete_from_storage
)

STYLE_PALETTES = {
    'classic': {
        'name': 'Classic Black',
        'fill_color': '#0F172A',
        'back_color': '#FFFFFF',
        'accent': '#334155'
    },
    'coral': {
        'name': 'Coral Sunset',
        'fill_color': '#E11D48',
        'back_color': '#FFFFFF',
        'accent': '#FB7185'
    },
    'ocean': {
        'name': 'Ocean Blue',
        'fill_color': '#0284C7',
        'back_color': '#FFFFFF',
        'accent': '#38BDF8'
    },
    'emerald': {
        'name': 'Emerald',
        'fill_color': '#059669',
        'back_color': '#FFFFFF',
        'accent': '#34D399'
    },
    'violet': {
        'name': 'Violet',
        'fill_color': '#7C3AED',
        'back_color': '#FFFFFF',
        'accent': '#A78BFA'
    },
    'midnight': {
        'name': 'Midnight',
        'fill_color': '#090D16',
        'back_color': '#F1F5F9',
        'accent': '#0284C7'
    }
}


def get_qr_folder() -> str:
    """Retrieve path to local QR storage directory."""
    return getattr(
        Config,
        'QR_FOLDER',
        os.path.join(Config.BASE_DIR, 'qr_codes')
    )


def generate_qr_code(
    target_url: str, media_id: str, style: str = 'classic'
) -> str:
    """
    Generate a high-resolution, print-ready QR code pointing to target_url.
    Saves as PNG locally and synchronizes to Supabase Storage.
    Returns the generated QR filename.
    """
    folder = get_qr_folder()
    os.makedirs(folder, exist_ok=True)

    if style not in STYLE_PALETTES:
        style = 'classic'

    palette = STYLE_PALETTES[style]

    # Error Correction Level M (~15% recovery)
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=12,
        border=3,
        image_factory=PilImage
    )
    qr.add_data(target_url)
    qr.make(fit=True)

    pil_box = qr.make_image(
        fill_color=palette['fill_color'],
        back_color=palette['back_color']
    )
    img = pil_box.get_image().convert('RGB')

    filename = f"qr_{media_id}_{style}.png"
    filepath = os.path.join(folder, filename)

    # Save to buffer and local file
    buf = io.BytesIO()
    img.save(buf, format='PNG', quality=95)
    img_bytes = buf.getvalue()

    with open(filepath, 'wb') as f:
        f.write(img_bytes)

    # Sync to Supabase Storage if configured
    try:
        qr_storage_path = f"qr-codes/{filename}"
        upload_qr_to_storage(img_bytes, qr_storage_path)
    except Exception as e:
        print(f"Warning: Could not sync QR {filename} to Supabase: {e}")

    return filename


def delete_qr_file(qr_filename: str, media_id: Optional[str] = None) -> None:
    """
    Safely delete a QR code PNG from the local filesystem and Supabase
    Storage.
    """
    folder = get_qr_folder()
    qr_storage_paths = []

    if qr_filename:
        safe_name = os.path.basename(qr_filename)
        path = os.path.join(folder, safe_name)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"Error deleting local QR file {path}: {e}")
        qr_storage_paths.append(f"qr-codes/{safe_name}")

    if media_id and os.path.isdir(folder):
        prefix = f"qr_{media_id}_"
        for fname in os.listdir(folder):
            if fname.startswith(prefix):
                var_path = os.path.join(folder, fname)
                if os.path.isfile(var_path):
                    try:
                        os.remove(var_path)
                    except Exception:
                        pass
                qr_storage_paths.append(f"qr-codes/{fname}")

    # Remove from Supabase Storage
    if qr_storage_paths:
        try:
            delete_from_storage(qr_storage_paths)
        except Exception as e:
            print(f"Warning: Could not delete QR files from Supabase: {e}")
