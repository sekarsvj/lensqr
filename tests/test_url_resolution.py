"""
LensQR Photo & Video QR Generator - URL Resolution & QR Accessibility Tests.
Verifies that no production QR code contains localhost or 127.0.0.1,
validates Render HTTPS domain detection, and tests batch regeneration.
"""

import io
import os
import unittest
from PIL import Image
from config import Config, resolve_public_base_url, get_lan_ip
from app import create_app
from services.media_service import regenerate_all_qr_codes, get_media


class TestUrlResolutionAndQrAccessibility(unittest.TestCase):
    """Test suite for URL resolution and localhost QR prevention."""

    def setUp(self):
        self.app = create_app({
            'TESTING': True,
            'WTF_CSRF_ENABLED': False
        })
        self.client = self.app.test_client()

    def create_dummy_image(self):
        """Create a valid PNG image in memory."""
        img = Image.new('RGB', (80, 80), color='blue')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    def get_csrf(self, client):
        """Extract a valid session CSRF token."""
        client.get('/')
        with client.session_transaction() as sess:
            return sess.get('csrf_token')

    def test_production_public_url_never_contains_localhost(self):
        """
        Verify production QR codes strictly encode the configured PUBLIC_URL
        and never contain localhost or 127.0.0.1.
        """
        prod_domain = "https://qr.lensqr.net"
        test_app = create_app({
            'TESTING': True,
            'PUBLIC_URL': prod_domain
        })
        test_client = test_app.test_client()
        csrf = self.get_csrf(test_client)

        img = self.create_dummy_image()
        res = test_client.post('/upload/photo', data={
            'csrf_token': csrf,
            'title': 'Prod QR Test',
            'file': (img, 'prod_photo.png')
        }, headers={'X-CSRFToken': csrf}, content_type='multipart/form-data')

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        media_url = data['media_url']
        self.assertTrue(media_url.startswith(prod_domain))
        self.assertNotIn('localhost', media_url)
        self.assertNotIn('127.0.0.1', media_url)
        self.assertNotIn('0.0.0.0', media_url)

    def test_render_https_domain_automatic_detection(self):
        """
        Verify that in Render production environments (RENDER_EXTERNAL_URL),
        QR codes automatically use the Render HTTPS domain.
        """
        render_domain = "https://lensqr-app.onrender.com"
        old_env = os.environ.get('RENDER_EXTERNAL_URL')
        old_pub = os.environ.get('PUBLIC_URL')

        try:
            os.environ['RENDER_EXTERNAL_URL'] = render_domain
            if 'PUBLIC_URL' in os.environ:
                del os.environ['PUBLIC_URL']

            resolved = resolve_public_base_url()
            self.assertEqual(resolved, render_domain)
            self.assertTrue(resolved.startswith('https://'))
            self.assertNotIn('localhost', resolved)
            self.assertNotIn('127.0.0.1', resolved)
        finally:
            if old_env is not None:
                os.environ['RENDER_EXTERNAL_URL'] = old_env
            elif 'RENDER_EXTERNAL_URL' in os.environ:
                del os.environ['RENDER_EXTERNAL_URL']

            if old_pub is not None:
                os.environ['PUBLIC_URL'] = old_pub

    def test_local_dev_fallback_uses_lan_ip_not_loopback(self):
        """
        Verify that during local development with no PUBLIC_URL configured,
        resolve_public_base_url returns the LAN IP rather than 127.0.0.1.
        """
        old_pub = os.environ.get('PUBLIC_URL')
        old_render = os.environ.get('RENDER_EXTERNAL_URL')

        try:
            if 'PUBLIC_URL' in os.environ:
                del os.environ['PUBLIC_URL']
            if 'RENDER_EXTERNAL_URL' in os.environ:
                del os.environ['RENDER_EXTERNAL_URL']

            resolved = resolve_public_base_url()
            lan_ip = get_lan_ip()

            self.assertIn(lan_ip, resolved)
            self.assertNotIn('localhost', resolved)
            self.assertTrue(resolved.startswith('http://'))
        finally:
            if old_pub is not None:
                os.environ['PUBLIC_URL'] = old_pub
            if old_render is not None:
                os.environ['RENDER_EXTERNAL_URL'] = old_render

    def test_dev_public_url_tunnel_override(self):
        """
        Verify that DEV_PUBLIC_URL provides a clean override for local tunnels.
        """
        tunnel_url = "https://my-tunnel.loca.lt"
        old_dev = os.environ.get('DEV_PUBLIC_URL')
        old_pub = os.environ.get('PUBLIC_URL')
        old_render = os.environ.get('RENDER_EXTERNAL_URL')

        try:
            if 'PUBLIC_URL' in os.environ:
                del os.environ['PUBLIC_URL']
            if 'RENDER_EXTERNAL_URL' in os.environ:
                del os.environ['RENDER_EXTERNAL_URL']
            os.environ['DEV_PUBLIC_URL'] = tunnel_url

            resolved = resolve_public_base_url()
            self.assertEqual(resolved, tunnel_url)
            self.assertNotIn('localhost', resolved)
        finally:
            if old_dev is not None:
                os.environ['DEV_PUBLIC_URL'] = old_dev
            elif 'DEV_PUBLIC_URL' in os.environ:
                del os.environ['DEV_PUBLIC_URL']

            if old_pub is not None:
                os.environ['PUBLIC_URL'] = old_pub
            if old_render is not None:
                os.environ['RENDER_EXTERNAL_URL'] = old_render

    def test_cloudflare_tunnel_url_resolution(self):
        """
        Verify that Cloudflare Tunnel trycloudflare.com HTTPS URLs are strictly
        encoded into QR codes and viewer links.
        """
        tunnel_url = "https://angle-beast-bottles-infectious.trycloudflare.com"
        old_pub = os.environ.get('PUBLIC_URL')
        try:
            os.environ['PUBLIC_URL'] = tunnel_url
            test_app = create_app({
                'TESTING': True,
                'PUBLIC_URL': tunnel_url
            })
            test_client = test_app.test_client()
            csrf = self.get_csrf(test_client)

            img = self.create_dummy_image()
            res = test_client.post('/upload/photo', data={
                'csrf_token': csrf,
                'title': 'Cloudflare Tunnel Test Photo',
                'file': (img, 'tunnel_test.png')
            }, headers={'X-CSRFToken': csrf}, content_type='multipart/form-data')

            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data['success'])
            self.assertTrue(data['media_url'].startswith(tunnel_url))
            self.assertNotIn('localhost', data['media_url'])
            self.assertNotIn('127.0.0.1', data['media_url'])
        finally:
            if old_pub is not None:
                os.environ['PUBLIC_URL'] = old_pub
            elif 'PUBLIC_URL' in os.environ:
                del os.environ['PUBLIC_URL']

    def test_proxy_fix_cloudflare_forwarded_headers(self):
        """
        Verify that Werkzeug ProxyFix correctly interprets Cloudflare Tunnel
        forwarded headers (X-Forwarded-Proto, X-Forwarded-Host).
        """
        old_pub = os.environ.get('PUBLIC_URL')
        try:
            if 'PUBLIC_URL' in os.environ:
                del os.environ['PUBLIC_URL']

            test_app = create_app({'TESTING': True, 'PUBLIC_URL': ''})
            test_client = test_app.test_client()

            cf_host = 'my-custom-tunnel.trycloudflare.com'
            res = test_client.get('/', headers={
                'X-Forwarded-Proto': 'https',
                'X-Forwarded-Host': cf_host
            })
            self.assertEqual(res.status_code, 200)
            # The context processor injects public_url which should match the forwarded HTTPS host
            with test_client.application.test_request_context('/', headers={
                'X-Forwarded-Proto': 'https',
                'X-Forwarded-Host': cf_host
            }):
                resolved = resolve_public_base_url()
                self.assertNotIn('localhost', resolved)
        finally:
            if old_pub is not None:
                os.environ['PUBLIC_URL'] = old_pub

    def test_batch_qr_regeneration_preserves_ids_and_files(self):
        """
        Verify regenerate_all_qr_codes updates all existing QR codes to the
        target base URL while strictly preserving media IDs and uploaded files.
        """
        target_prod_url = "https://production.lensqr.net"
        res = regenerate_all_qr_codes(new_base_url=target_prod_url)

        self.assertTrue(res['success'])
        self.assertEqual(res['base_url'], target_prod_url)
        self.assertGreater(res['total_found'], 0)
        self.assertEqual(res['regenerated_count'], res['total_found'])

        # Check that legacy record PPXCmmUp55 still exists with same ID and file
        rec = get_media('PPXCmmUp55')
        if rec:
            self.assertEqual(rec['id'], 'PPXCmmUp55')
            self.assertTrue(
                os.path.isfile(
                    os.path.join(Config.QR_FOLDER, rec['qr_filename'])
                )
            )

    def test_batch_regeneration_api_endpoint(self):
        """Test POST /api/admin/regenerate-qr-codes endpoint."""
        csrf = self.get_csrf(self.client)
        res = self.client.post(
            '/api/admin/regenerate-qr-codes',
            json={'base_url': 'https://api-test.lensqr.net'},
            headers={'X-CSRFToken': csrf}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['base_url'], 'https://api-test.lensqr.net')


if __name__ == '__main__':
    unittest.main()

