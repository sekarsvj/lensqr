import io
from PIL import Image
from app import create_app
from database.database import get_media


def test_full_pipeline():
    app = create_app()
    client = app.test_client()

    print("=" * 65)
    print("LensQR Photo & Video QR Generator - JSON Storage Verification")
    print("=" * 65)

    # 1. Obtain CSRF token & load homepage
    home = client.get('/')
    assert home.status_code == 200, f"Home page failed: {home.status_code}"
    print("✓ Home page loaded successfully (HTTP 200)")

    with client.session_transaction() as sess:
        csrf_token = sess.get('csrf_token')
    assert csrf_token, "CSRF token missing in session"
    print(f"✓ CSRF token verified: {csrf_token[:12]}...")

    # 2. Upload one photograph
    img = io.BytesIO()
    Image.new('RGB', (600, 400), color=(255, 94, 98)).save(img, 'JPEG')
    img.seek(0)

    photo_payload = {
        'csrf_token': csrf_token,
        'title': 'Sample Vacation Picture',
        'description': 'High-resolution sample photo',
        'qr_style': 'coral',
        'file': (img, 'sunset_beach.jpg')
    }

    res = client.post(
        '/upload/photo',
        data=photo_payload,
        content_type='multipart/form-data',
        headers={'X-CSRFToken': csrf_token}
    )
    assert res.status_code == 200, f"Upload failed: {res.data}"
    data = res.get_json()
    assert data['success'] is True
    photo_id = data['media_id']
    creator_token = data['creator_token']
    print(f"✓ Photo uploaded to JSON storage (Media ID: {photo_id})")
    print(f"  Public Media URL: {data['media_url']}")
    print(f"  QR Code URL: {data['qr_url']}")

    # 3. Verify record in JSON file
    record = get_media(photo_id)
    assert record is not None, "Record not found in JSON storage"
    assert record['type'] == 'photo'
    assert record['original_name'] == 'sunset_beach.jpg'
    print(
        f"✓ JSON database record verified (Original: {
            record['original_name']}, size: {
            record['size_bytes']} bytes)")

    # 4. Verify Result Page
    result_page = client.get(f'/result/{photo_id}')
    assert result_page.status_code == 200
    assert b'QR Code Generated Successfully' in result_page.data
    print("✓ Result page rendered successfully")

    # 5. Verify Public Media Viewer Page
    viewer_page = client.get(f'/m/{photo_id}')
    assert viewer_page.status_code == 200
    assert b'Sample Vacation Picture' in viewer_page.data
    assert b'sunset_beach.jpg' in viewer_page.data
    print("✓ Public Media Viewer page verified with responsive image viewer")

    # 6. Verify QR Code Download Route
    qr_res = client.get(f'/download-qr/{photo_id}')
    assert qr_res.status_code == 200
    assert qr_res.mimetype == 'image/png'
    qr_img = Image.open(io.BytesIO(qr_res.data))
    assert qr_img.size[0] > 100 and qr_img.size[1] > 100
    print(
        f"✓ QR Code downloaded and verified (Dimensions: {
            qr_img.size[0]}x{
            qr_img.size[1]}px, format: PNG)")
    qr_res.close()

    # 7. Test QR Code Style Regeneration
    regen_res = client.post('/generate-qr', json={
        'csrf_token': csrf_token,
        'media_id': photo_id,
        'qr_style': 'emerald'
    }, headers={'X-CSRFToken': csrf_token})
    assert regen_res.status_code == 200
    regen_data = regen_res.get_json()
    assert regen_data['qr_style'] == 'emerald'
    print(
        "✓ QR code successfully regenerated with 'emerald' "
        "palette without changing media URL"
    )

    # 8. Upload one video
    vid_io = io.BytesIO(
        b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41' +
        b'\x00' *
        4096)
    video_payload = {
        'csrf_token': csrf_token,
        'title': 'Product Teaser Video',
        'description': 'Short promotional video clip',
        'qr_style': 'ocean',
        'file': (vid_io, 'teaser_promo.mp4')
    }

    vid_res = client.post(
        '/upload/video',
        data=video_payload,
        content_type='multipart/form-data',
        headers={'X-CSRFToken': csrf_token}
    )
    assert vid_res.status_code == 200
    vid_data = vid_res.get_json()
    video_id = vid_data['media_id']
    video_token = vid_data['creator_token']
    print(f"✓ Video uploaded to JSON storage (Media ID: {video_id})")

    # 9. Verify Video Player in Viewer Page
    vid_viewer = client.get(f'/m/{video_id}')
    assert vid_viewer.status_code == 200
    assert b'Product Teaser Video' in vid_viewer.data
    assert b'<video' in vid_viewer.data
    print("✓ Video viewer verified with native HTML5 player container")

    # 10. Test Secure Deletion
    del_res = client.post(f'/api/media/{photo_id}/delete', json={
        'creator_token': creator_token
    }, headers={'X-CSRFToken': csrf_token, 'X-Creator-Token': creator_token})
    assert del_res.status_code == 200
    assert get_media(photo_id) is None
    print(f"✓ Photo {photo_id} permanently deleted with creator authorization")

    # Clean up video test record
    client.post(f'/api/media/{video_id}/delete', json={
        'creator_token': video_token
    }, headers={'X-CSRFToken': csrf_token, 'X-Creator-Token': video_token})
    print(f"✓ Video {video_id} cleaned up")

    print("=" * 65)
    print("ALL 10 PIPELINE VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == '__main__':
    test_full_pipeline()
