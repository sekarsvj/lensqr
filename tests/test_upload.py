import os
import io
import shutil
import unittest
from PIL import Image
from app import create_app
from config import Config
from database import database


class TestUpload(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(Config.BASE_DIR, 'test_upload_sandbox')
        self.photos_dir = os.path.join(self.test_dir, 'photos')
        self.videos_dir = os.path.join(self.test_dir, 'videos')
        self.docs_dir = os.path.join(self.test_dir, 'documents')
        self.qr_dir = os.path.join(self.test_dir, 'qr_codes')
        self.test_json = os.path.join(self.test_dir, 'media.json')

        os.makedirs(self.photos_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)
        os.makedirs(self.docs_dir, exist_ok=True)
        os.makedirs(self.qr_dir, exist_ok=True)

        Config.UPLOAD_FOLDER_PHOTOS = self.photos_dir
        Config.UPLOAD_FOLDER_VIDEOS = self.videos_dir
        Config.UPLOAD_FOLDER_DOCUMENTS = self.docs_dir
        Config.QR_FOLDER = self.qr_dir
        Config.JSON_STORAGE_PATH = self.test_json

        database.initialize_storage()

        self.app = create_app({
            'TESTING': True,
            'UPLOAD_FOLDER_PHOTOS': self.photos_dir,
            'UPLOAD_FOLDER_VIDEOS': self.videos_dir,
            'UPLOAD_FOLDER_DOCUMENTS': self.docs_dir,
            'QR_FOLDER': self.qr_dir,
            'JSON_STORAGE_PATH': self.test_json,
            'MAX_PHOTO_MB': 5,
            'MAX_VIDEO_MB': 10,
            'MAX_DOCUMENT_MB': 50
        })
        self.client = self.app.test_client()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def create_dummy_image(self, fmt='JPEG'):
        """Create valid in-memory image."""
        img_io = io.BytesIO()
        img = Image.new('RGB', (100, 100), color=(255, 94, 98))
        img.save(img_io, format=fmt)
        img_io.seek(0)
        return img_io

    def create_dummy_video(self, fmt='mp4'):
        """Create valid video container bytes."""
        vid_io = io.BytesIO()
        if fmt in ['mp4', 'mov']:
            ftyp_box = b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41'
            vid_io.write(ftyp_box)
            vid_io.write(b'\x00' * 512)
        elif fmt == 'webm':
            # EBML header
            vid_io.write(b'\x1A\x45\xDF\xA3' + b'\x00' * 512)
        vid_io.seek(0)
        return vid_io

    def create_dummy_document(self, fmt='pdf'):
        """Create valid document file bytes."""
        doc_io = io.BytesIO()
        if fmt == 'pdf':
            doc_io.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n>>\n%%EOF\n')
        elif fmt in ['docx', 'xlsx', 'pptx', 'zip']:
            doc_io.write(b'PK\x03\x04\x14\x00\x00\x00\x08\x00' + b'\x00' * 128)
        elif fmt in ['doc', 'xls', 'ppt']:
            doc_io.write(b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1' + b'\x00' * 128)
        else:
            doc_io.write(b'Sample text document content')
        doc_io.seek(0)
        return doc_io

    def get_csrf(self):
        self.client.get('/')
        with self.client.session_transaction() as sess:
            return sess.get('csrf_token')

    def test_upload_photo_formats(self):
        """Test JPG, PNG, and WEBP formats are accepted."""
        csrf = self.get_csrf()

        for fmt, ext in [('JPEG', 'jpg'), ('PNG', 'png'), ('WEBP', 'webp')]:
            img = self.create_dummy_image(fmt)
            res = self.client.post(
                '/upload/photo',
                data={
                    'csrf_token': csrf,
                    'file': (
                        img,
                        f'sample.{ext}'),
                    'title': f'Test {ext}'},
                headers={
                    'X-CSRFToken': csrf},
                content_type='multipart/form-data')

            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data['success'])
            self.assertIn('media_id', data)

            # Verify record in JSON
            record = database.get_media(data['media_id'])
            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record['type'], 'photo')

    def test_upload_video_formats(self):
        """Test MP4, MOV, and WebM video formats are accepted."""
        csrf = self.get_csrf()

        for fmt in ['mp4', 'mov', 'webm']:
            vid = self.create_dummy_video(fmt)
            res = self.client.post(
                '/upload/video',
                data={
                    'csrf_token': csrf,
                    'file': (
                        vid,
                        f'clip.{fmt}'),
                    'title': f'Test {fmt}'},
                headers={
                    'X-CSRFToken': csrf},
                content_type='multipart/form-data')

            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data['success'])
            record = database.get_media(data['media_id'])
            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record['type'], 'video')

    def test_reject_unsupported_extensions(self):
        """Test rejection of executable and unsupported file formats."""
        csrf = self.get_csrf()
        bad_file = io.BytesIO(b'executable payload')

        res = self.client.post('/upload/photo', data={
            'csrf_token': csrf,
            'file': (bad_file, 'virus.exe')
        }, headers={'X-CSRFToken': csrf}, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 400)
        self.assertIn(b'not supported', res.data)

    def test_reject_spoofed_signature(self):
        """
        Test rejection of text/script files renamed with image extensions.
        """
        csrf = self.get_csrf()
        spoofed = io.BytesIO(b'<script>alert("hack")</script>')

        res = self.client.post('/upload/photo', data={
            'csrf_token': csrf,
            'file': (spoofed, 'fake.jpg')
        }, headers={'X-CSRFToken': csrf}, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 400)
        self.assertIn(b'Invalid JPEG file signature', res.data)

    def test_reject_empty_file(self):
        """Test rejection of zero-byte empty files."""
        csrf = self.get_csrf()
        empty = io.BytesIO(b'')

        res = self.client.post('/upload/photo', data={
            'csrf_token': csrf,
            'file': (empty, 'empty.jpg')
        }, headers={'X-CSRFToken': csrf}, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 400)
        self.assertIn(b'empty', res.data)


    def test_upload_document_formats(self):
        """Test PDF, Word, Excel, PowerPoint, Text, and Zip document uploads."""
        csrf = self.get_csrf()

        for fmt in ['pdf', 'docx', 'doc', 'xlsx', 'txt', 'zip']:
            doc = self.create_dummy_document(fmt)
            res = self.client.post(
                '/upload/document',
                data={
                    'csrf_token': csrf,
                    'file': (doc, f'sample.{fmt}'),
                    'title': f'Test {fmt.upper()} Document'
                },
                headers={'X-CSRFToken': csrf},
                content_type='multipart/form-data'
            )

            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['media_type'], 'document')
            self.assertIn('media_url', data)
            self.assertIn('qr_url', data)

            # Verify in JSON database
            record = database.get_media(data['media_id'])
            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record['type'], 'document')
            self.assertEqual(record['title'], f'Test {fmt.upper()} Document')

    def test_document_viewer_and_download(self):
        """Test document viewer page renders and file can be downloaded."""
        csrf = self.get_csrf()
        doc = self.create_dummy_document('pdf')

        res = self.client.post(
            '/upload/document',
            data={
                'csrf_token': csrf,
                'file': (doc, 'invoice.pdf'),
                'title': 'Invoice Q4'
            },
            headers={'X-CSRFToken': csrf},
            content_type='multipart/form-data'
        )
        data = res.get_json()
        media_id = data['media_id']

        # Viewer page request
        view_res = self.client.get(f'/m/{media_id}')
        self.assertEqual(view_res.status_code, 200)
        self.assertIn(b'Invoice Q4', view_res.data)
        self.assertIn(b'Document', view_res.data)

        # File download request
        file_res = self.client.get(f'/media-file/{media_id}')
        self.assertIn(file_res.status_code, [200, 307])
        if file_res.status_code == 200:
            self.assertEqual(file_res.mimetype, 'application/pdf')

    def test_reject_executable_binary_in_document(self):
        """Test rejection of executable file uploaded as document."""
        csrf = self.get_csrf()
        exe_file = io.BytesIO(b'MZ\x90\x00' + b'\x00' * 128)

        res = self.client.post(
            '/upload/document',
            data={
                'csrf_token': csrf,
                'file': (exe_file, 'dangerous.pdf')
            },
            headers={'X-CSRFToken': csrf},
            content_type='multipart/form-data'
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn(b'not permitted', res.data)


if __name__ == '__main__':
    unittest.main()
