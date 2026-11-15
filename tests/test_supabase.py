"""
LensQR Photo & Video QR Generator - Supabase Integration Test Suite.
Tests Supabase storage uploads, signed URL generation, metadata mapping,
viewer routes, and production URL formatting.
"""

import io
import unittest
from PIL import Image
from config import Config
from app import create_app
from services.supabase_service import _normalize_db_record
from services.storage_service import (
    get_bucket_name,
    ensure_storage_bucket,
    upload_media_to_storage,
    generate_signed_url,
    delete_from_storage
)


class TestSupabaseIntegration(unittest.TestCase):
    """Test suite for Supabase storage, metadata, and routing."""

    def setUp(self):
        self.app = create_app({
            'TESTING': True,
            'WTF_CSRF_ENABLED': False
        })
        self.client = self.app.test_client()

    def create_dummy_image(self):
        """Create a valid PNG image in memory."""
        img = Image.new('RGB', (100, 100), color='green')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    def get_csrf(self):
        """Extract a valid session CSRF token."""
        self.client.get('/')
        with self.client.session_transaction() as sess:
            return sess.get('csrf_token')

    def test_bucket_configuration(self):
        """Verify storage bucket name matches requirements."""
        self.assertEqual(get_bucket_name(), 'qr-media')

    def test_metadata_normalization(self):
        """
        Verify database record normalization preserves all required keys.
        """
        raw_db_row = {
            'id': 'test-uuid-1234',
            'media_type': 'photo',
            'title': 'Sunset Photo',
            'description': 'A beautiful sunset',
            'original_filename': 'sunset.png',
            'storage_path': 'photos/sunset_safe.png',
            'mime_type': 'image/png',
            'file_size': 10240,
            'qr_code_path': 'qr-codes/qr_test_classic.png',
            'qr_style': 'coral',
            'creator_token': 'secret123',
            'access': 'unlisted',
            'views_count': 5,
            'is_active': True,
            'created_at': '2026-11-15T00:00:00Z'
        }
        normalized = _normalize_db_record(raw_db_row)
        self.assertEqual(normalized['id'], 'test-uuid-1234')
        self.assertEqual(normalized['type'], 'photo')
        self.assertEqual(normalized['media_type'], 'photo')
        self.assertEqual(normalized['filename'], 'photos/sunset_safe.png')
        self.assertEqual(normalized['size_bytes'], 10240)
        self.assertEqual(normalized['file_size'], 10240)
        self.assertEqual(
            normalized['qr_filename'], 'qr-codes/qr_test_classic.png'
        )

    def test_storage_upload_and_signed_url(self):
        """
        Test upload, signed URL generation, and cleanup in Supabase bucket.
        """
        if not Config.is_supabase_configured():
            self.skipTest(
                "Supabase credentials not configured in environment."
            )

        ensure_storage_bucket()
        test_path = 'photos/unit_test_img.png'
        img_data = self.create_dummy_image().read()

        # Upload
        up_ok = upload_media_to_storage(img_data, test_path, 'image/png')
        self.assertTrue(up_ok)

        # Generate signed URL
        signed_url = generate_signed_url(test_path, 120)
        self.assertIsNotNone(signed_url)
        assert signed_url is not None
        self.assertTrue(
            signed_url.startswith('http://') or
            signed_url.startswith('https://')
        )

        # Cleanup
        del_ok = delete_from_storage(test_path)
        self.assertTrue(del_ok)

    def test_production_public_url_encoding(self):
        """
        Verify QR codes encode configured production PUBLIC_URL without
        localhost.
        """
        prod_app = create_app({
            'TESTING': True,
            'PUBLIC_URL': 'https://qr.lensqr.net'
        })
        prod_client = prod_app.test_client()

        # Get CSRF
        prod_client.get('/')
        with prod_client.session_transaction() as sess:
            csrf = sess.get('csrf_token')

        img = self.create_dummy_image()
        res = prod_client.post('/upload/photo', data={
            'csrf_token': csrf,
            'title': 'Prod Test Photo',
            'file': (img, 'prod_test.png')
        }, headers={'X-CSRFToken': csrf}, content_type='multipart/form-data')

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(
            data['media_url'].startswith('https://qr.lensqr.net/m/')
        )
        self.assertNotIn('localhost', data['media_url'])
        self.assertNotIn('127.0.0.1', data['media_url'])

    def test_missing_credentials_graceful_handling(self):
        """
        Verify application functions gracefully even if Supabase is
        unconfigured.
        """
        from services.supabase_service import get_media_from_db
        res = get_media_from_db('nonexistent_id_9999')
        self.assertIsNone(res)


if __name__ == '__main__':
    unittest.main()
