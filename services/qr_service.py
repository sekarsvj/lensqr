import os
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from qrcode.image.pil import PilImage
from config import Config

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


def get_qr_folder():
    """Retrieve path to QR storage directory."""
    return getattr(
        Config,
        'QR_FOLDER',
        os.path.join(
            Config.BASE_DIR,
            'qr_codes'))


def generate_qr_code(target_url, media_id, style='classic'):
    """
    Generate a high-resolution, print-ready QR code pointing to target_url.
    Saves as PNG in qr_codes/ folder and returns the filename.
    """
    folder = get_qr_folder()
    os.makedirs(folder, exist_ok=True)

    if style not in STYLE_PALETTES:
        style = 'classic'

    palette = STYLE_PALETTES[style]

    # Configure QR code with Error Correction Level M (15% error correction)
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=12,
        border=3,
        image_factory=PilImage
    )
    qr.add_data(target_url)
    qr.make(fit=True)

    # Generate image
    pil_box = qr.make_image(
        fill_color=palette['fill_color'],
        back_color=palette['back_color']
    )
    img = pil_box.get_image().convert('RGB')

    filename = f"qr_{media_id}_{style}.png"
    filepath = os.path.join(folder, filename)
    img.save(filepath, 'PNG', quality=95)

    return filename


def delete_qr_file(qr_filename, media_id=None):
    """Safely delete a QR code PNG from the filesystem."""
    folder = get_qr_folder()
    if qr_filename:
        path = os.path.join(folder, os.path.basename(qr_filename))
        if os.path.isfile(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"Error deleting QR file {path}: {e}")

    # Also clean any lingering styles for this media_id
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
