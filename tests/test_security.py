import os
import io
import shutil
import unittest
from PIL import Image
from app import create_app
from config import Config
from database import database


class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(Config.BASE_DIR, 'test_security_sandbox')
        self.photos_dir = os.path.join(self.test_dir, 'photos')
        self.videos_dir = os.path.join(self.test_dir, 'videos')
        self.qr_dir = os.path.join(self.test_dir, 'qr_codes')
        self.test_json = os.path.join(self.test_dir, 'media.json')

        os.makedirs(self.photos_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)
        os.makedirs(self.qr_dir, exist_ok=True)

        Config.UPLOAD_FOLDER_PHOTOS = self.photos_dir
        Config.UPLOAD_FOLDER_VIDEOS = self.videos_dir
        Config.QR_FOLDER = self.qr_dir
        Config.JSON_STORAGE_PATH = self.test_json

        database.initialize_storage()

        self.app = create_app({
            'TESTING': True,
            'UPLOAD_FOLDER_PHOTOS': self.photos_dir,
            'UPLOAD_FOLDER_VIDEOS': self.videos_dir,
            'QR_FOLDER': self.qr_dir,
            'JSON_STORAGE_PATH': self.test_json
        })
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def create_dummy_image(self):
        img_io = io.BytesIO()
        img = Image.new('RGB', (100, 100), color=(255, 94, 98))
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        return img_io

    def get_csrf(self):
        self.client.get('/')
        with self.client.session_transaction() as sess:
            return sess.get('csrf_token')

    def test_csrf_protection(self):
        """Test state-changing requests without CSRF token are blocked."""
        img = self.create_dummy_image()
        res = self.client.post('/upload/photo', data={
            'file': (img, 'test.jpg')
        }, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 400)
        self.assertIn(b'CSRF verification failed', res.data)

    def test_unauthorized_deletion_rejected(self):
        """
        Test deleting media without valid creator token is rejected with 403.
        """
        csrf = self.get_csrf()

        # Save a record directly to storage
        record = {
            'id': 'sec_del_1',
            'creator_token': 'correct_secret_token',
            'type': 'photo',
            'original_name': 'photo.jpg',
            'filename': 'uuid_photo.jpg',
            'mime_type': 'image/jpeg',
            'size_bytes': 100,
            'qr_filename': 'qr_sec_del_1_classic.png',
            'access': 'unlisted',
            'created_at': '2026-11-15T00:00:00Z'
        }
        database.save_media(record)

        # 1. Attempt delete with wrong token -> 403
        bad_del = self.client.post(
            '/api/media/sec_del_1/delete',
            json={'creator_token': 'wrong_token'},
            headers={'X-CSRFToken': csrf, 'X-Creator-Token': 'wrong_token'}
        )
        self.assertEqual(bad_del.status_code, 403)
        self.assertIsNotNone(database.get_media('sec_del_1'))

        # 2. Attempt delete with correct token -> 200
        good_del = self.client.post(
            '/api/media/sec_del_1/delete',
            json={
                'creator_token': 'correct_secret_token'},
            headers={
                'X-CSRFToken': csrf,
                'X-Creator-Token': 'correct_secret_token'})
        self.assertEqual(good_del.status_code, 200)
        self.assertIsNone(database.get_media('sec_del_1'))

    def test_nonexistent_and_deleted_media_404(self):
        """Test non-existent and deleted media links return 404."""
        res = self.client.get('/m/nonexistent_xyz')
        self.assertEqual(res.status_code, 404)
        self.assertIn(b'404', res.data)

        file_res = self.client.get('/media-file/nonexistent_xyz')
        self.assertEqual(file_res.status_code, 404)

    def test_video_http_range_requests(self):
        """Test video streaming with HTTP Range requests (HTTP 206)."""
        # Create a dummy video file on disk and in database
        video_filename = 'stream_test.mp4'
        video_path = os.path.join(self.videos_dir, video_filename)
        with open(video_path, 'wb') as f:
            f.write(b'\x00\x00\x00\x18ftypisom' + b'\x00' * 4096)

        record = {
            'id': 'vid_stream_1',
            'creator_token': 'tok1',
            'type': 'video',
            'original_name': 'video.mp4',
            'filename': video_filename,
            'mime_type': 'video/mp4',
            'size_bytes': 4112,
            'qr_filename': 'qr_vid_stream_1_classic.png',
            'access': 'unlisted',
            'created_at': '2026-11-15T00:00:00Z'
        }
        database.save_media(record)

        # Request partial byte range
        res = self.client.get(
            '/media-file/vid_stream_1',
            headers={'Range': 'bytes=0-100'}
        )
        self.assertEqual(res.status_code, 206)
        self.assertIn('Content-Range', res.headers)
        res.close()


if __name__ == '__main__':
    unittest.main()
