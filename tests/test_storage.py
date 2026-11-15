import os
import shutil
import unittest
from config import Config
from database import database


class TestJsonStorage(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(Config.BASE_DIR, 'test_storage_sandbox')
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_json = os.path.join(self.test_dir, 'media.json')

        # Override storage path in config
        Config.JSON_STORAGE_PATH = self.test_json
        database.initialize_storage()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_initialize_storage(self):
        """Test initialize_storage creates valid media.json."""
        self.assertTrue(os.path.exists(self.test_json))
        data = database.read_data()
        self.assertIn('media', data)
        self.assertEqual(data['media'], [])

    def test_save_and_get_media(self):
        """Test saving and retrieving media records."""
        record = {
            'id': 'test123456',
            'creator_token': 'secret_token_123',
            'type': 'photo',
            'original_name': 'test.jpg',
            'filename': 'uuid_123.jpg',
            'mime_type': 'image/jpeg',
            'size_bytes': 1024,
            'qr_filename': 'qr_test123456_classic.png',
            'access': 'unlisted',
            'created_at': '2026-11-15T00:00:00Z'
        }
        database.save_media(record)

        retrieved = database.get_media('test123456')
        self.assertIsNotNone(retrieved)
        assert retrieved is not None
        self.assertEqual(retrieved['original_name'], 'test.jpg')
        self.assertEqual(retrieved['type'], 'photo')

    def test_validate_record_rejects_missing_fields(self):
        """Test record structure validation."""
        bad_record = {
            'id': 'bad_id',
            'type': 'photo'
            # Missing other required fields
        }
        with self.assertRaises(ValueError):
            database.save_media(bad_record)

    def test_list_and_delete_media(self):
        """Test listing and deleting records."""
        rec1 = {
            'id': 'm1',
            'creator_token': 'c1',
            'type': 'photo',
            'original_name': '1.jpg',
            'filename': 'f1.jpg',
            'mime_type': 'image/jpeg',
            'size_bytes': 500,
            'qr_filename': 'qr1.png',
            'access': 'unlisted',
            'created_at': '2026-11-15T00:00:00Z'
        }
        rec2 = {
            'id': 'm2',
            'creator_token': 'c2',
            'type': 'video',
            'original_name': '2.mp4',
            'filename': 'f2.mp4',
            'mime_type': 'video/mp4',
            'size_bytes': 5000,
            'qr_filename': 'qr2.png',
            'access': 'unlisted',
            'created_at': '2026-11-15T00:00:00Z'
        }
        database.save_media(rec1)
        database.save_media(rec2)

        all_records = database.list_media()
        self.assertEqual(len(all_records), 2)

        # Test filtering by creator token
        c1_records = database.list_media(creator_token='c1')
        self.assertEqual(len(c1_records), 1)
        self.assertEqual(c1_records[0]['id'], 'm1')

        # Delete record
        deleted = database.delete_media('m1')
        self.assertTrue(deleted)
        self.assertIsNone(database.get_media('m1'))
        self.assertEqual(len(database.list_media()), 1)

        # Deleting non-existent returns False
        self.assertFalse(database.delete_media('nonexistent'))

    def test_corrupted_json_handling(self):
        """Test that corrupted JSON is not silently overwritten."""
        with open(self.test_json, 'w', encoding='utf-8') as f:
            f.write("CORRUPTED NOT JSON {{{")

        with self.assertRaises(RuntimeError):
            database.initialize_storage()


if __name__ == '__main__':
    unittest.main()
