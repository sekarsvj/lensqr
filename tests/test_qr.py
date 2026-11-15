import os
import shutil
import unittest
from PIL import Image
from app import create_app
from config import Config
from database import database
from services.qr_service import generate_qr_code, STYLE_PALETTES


class TestQRService(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(Config.BASE_DIR, 'test_qr_sandbox')
        self.qr_dir = os.path.join(self.test_dir, 'qr_codes')
        self.photos_dir = os.path.join(self.test_dir, 'photos')
        self.videos_dir = os.path.join(self.test_dir, 'videos')
        self.test_json = os.path.join(self.test_dir, 'media.json')

        os.makedirs(self.qr_dir, exist_ok=True)
        os.makedirs(self.photos_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)

        Config.QR_FOLDER = self.qr_dir
        Config.UPLOAD_FOLDER_PHOTOS = self.photos_dir
        Config.UPLOAD_FOLDER_VIDEOS = self.videos_dir
        Config.JSON_STORAGE_PATH = self.test_json

        database.initialize_storage()

        self.app = create_app({
            'TESTING': True,
            'QR_FOLDER': self.qr_dir,
            'JSON_STORAGE_PATH': self.test_json,
            'UPLOAD_FOLDER_PHOTOS': self.photos_dir,
            'UPLOAD_FOLDER_VIDEOS': self.videos_dir
        })
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_qr_code_file(self):
        """Test QR code generation creates valid PNG image."""
        url = "https://example.com/m/test_media_123"
        filename = generate_qr_code(url, "test_media_123", style="coral")

        filepath = os.path.join(self.qr_dir, filename)
        self.assertTrue(os.path.isfile(filepath))

        # Verify with Pillow
        img = Image.open(filepath)
        self.assertEqual(img.format, 'PNG')
        self.assertGreater(img.size[0], 100)
        self.assertGreater(img.size[1], 100)
        img.close()

    def test_qr_palettes(self):
        """Test all 6 defined color palettes."""
        expected_styles = [
            'classic',
            'coral',
            'ocean',
            'emerald',
            'violet',
            'midnight']
        for style in expected_styles:
            self.assertIn(style, STYLE_PALETTES)
            fname = generate_qr_code(
                "https://example.com/m/123", "test_id", style=style)
            path = os.path.join(self.qr_dir, fname)
            self.assertTrue(os.path.isfile(path))

    def test_download_qr_endpoint(self):
        """Test downloading QR image via route."""
        # Create a record in JSON storage
        record = {
            'id': 'dl_test_1',
            'creator_token': 'c1',
            'type': 'photo',
            'original_name': 'pic.jpg',
            'filename': 'uuid.jpg',
            'mime_type': 'image/jpeg',
            'size_bytes': 100,
            'qr_filename': 'qr_dl_test_1_classic.png',
            'access': 'unlisted',
            'created_at': '2026-11-15T00:00:00Z'
        }
        database.save_media(record)
        generate_qr_code(
            "https://test.com/m/dl_test_1",
            "dl_test_1",
            style="classic")

        res = self.client.get('/download-qr/dl_test_1')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'image/png')
        self.assertIn('attachment', res.headers.get('Content-Disposition', ''))
        res.close()

    def test_qr_style_regeneration(self):
        """Test regenerating QR style without altering media ID."""
        record = {
            'id': 'regen_test',
            'creator_token': 'c1',
            'type': 'photo',
            'original_name': 'pic.jpg',
            'filename': 'uuid.jpg',
            'mime_type': 'image/jpeg',
            'size_bytes': 100,
            'qr_filename': 'qr_regen_test_classic.png',
            'qr_style': 'classic',
            'access': 'unlisted',
            'created_at': '2026-11-15T00:00:00Z'
        }
        database.save_media(record)
        generate_qr_code(
            "https://test.com/m/regen_test",
            "regen_test",
            style="classic")

        self.client.get('/')
        with self.client.session_transaction() as sess:
            csrf = sess.get('csrf_token')

        res = self.client.post('/generate-qr', json={
            'media_id': 'regen_test',
            'qr_style': 'ocean'
        }, headers={'X-CSRFToken': csrf})

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['qr_style'], 'ocean')

        # Verify JSON updated
        updated = database.get_media('regen_test')
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated['qr_style'], 'ocean')


if __name__ == '__main__':
    unittest.main()
