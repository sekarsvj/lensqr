import os
import secrets
from datetime import datetime
from flask import (
    Flask, render_template, request, jsonify,
    url_for, send_from_directory, abort, session, redirect
)
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from database.database import initialize_storage, get_media, format_file_size
from services.media_service import (
    create_media, update_media_qr_style,
    delete_media_and_files, format_media_dict,
    get_signed_media_url, regenerate_all_qr_codes
)
from services.qr_service import STYLE_PALETTES


def create_app(test_config=None):
    """Application factory for the Photo & Video QR Generator."""
    templates_dir = os.path.join(Config.BASE_DIR, 'templates')
    static_dir = os.path.join(Config.BASE_DIR, 'static')
    app = Flask(__name__, template_folder=templates_dir, static_folder=static_dir)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    # Support reverse proxy & Cloudflare Tunnel headers (X-Forwarded-Proto, X-Forwarded-Host)
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_port=1,
        x_prefix=1
    )

    # Cookie security settings
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    if not app.debug and not app.testing:
        app.config['SESSION_COOKIE_SECURE'] = True

    # Initialize storage & ensure directories exist
    with app.app_context():
        upload_photos = app.config.get(
            'UPLOAD_FOLDER_PHOTOS',
            Config.UPLOAD_FOLDER_PHOTOS)
        upload_videos = app.config.get(
            'UPLOAD_FOLDER_VIDEOS',
            Config.UPLOAD_FOLDER_VIDEOS)
        upload_docs = app.config.get(
            'UPLOAD_FOLDER_DOCUMENTS',
            Config.UPLOAD_FOLDER_DOCUMENTS)
        qr_folder = app.config.get('QR_FOLDER', Config.QR_FOLDER)
        data_dir = app.config.get('DATA_DIR', Config.DATA_DIR)

        os.makedirs(upload_photos, exist_ok=True)
        os.makedirs(upload_videos, exist_ok=True)
        os.makedirs(upload_docs, exist_ok=True)
        os.makedirs(qr_folder, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)

        initialize_storage()

        if Config.is_supabase_configured():
            try:
                from services.storage_service import ensure_storage_bucket
                ensure_storage_bucket()
            except Exception as se:
                app.logger.warning(
                    f"Supabase bucket initialization deferred: {se}"
                )

    def get_public_base_url():
        """
        Determine base public URL for encoded QR targets.
        Strictly prioritizes PUBLIC_URL and public tunnel domains,
        avoiding loopback localhost so external scanners can access media.
        """
        from config import resolve_public_base_url, is_loopback
        
        # Check explicit PUBLIC_URL environment variable first
        env_pub = os.environ.get('PUBLIC_URL', '').strip().rstrip('/')
        if env_pub and not is_loopback(env_pub):
            return env_pub

        # Check app config
        configured = (app.config.get('PUBLIC_URL') or '').strip().rstrip('/')
        if configured and not is_loopback(configured):
            return configured

        return resolve_public_base_url(request)

    @app.before_request
    def csrf_protection():
        """CSRF validation on all state-changing endpoints."""
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)

        if 'creator_tokens' not in session:
            session['creator_tokens'] = []

        if request.method in ['POST', 'DELETE', 'PUT', 'PATCH']:
            # Skip static assets
            if request.endpoint == 'static':
                return

            token = request.headers.get(
                'X-CSRFToken') or request.form.get('csrf_token')
            if not token and request.is_json and request.json:
                token = request.json.get('csrf_token')

            expected_token = session.get('csrf_token')
            if not token or not expected_token or not secrets.compare_digest(
                    str(token), str(expected_token)):
                return jsonify({
                    'success': False,
                    'error': (
                        'CSRF verification failed. '
                        'Please refresh the page and try again.'
                    )
                }), 400

    @app.context_processor
    def inject_globals():
        """Inject template helpers and branding into Jinja context."""
        return {
            'csrf_token': session.get('csrf_token', ''),
            'brand_name': app.config.get('BRAND_NAME', 'LensQR'),
            'public_url': get_public_base_url(),
            'qr_styles': STYLE_PALETTES,
            'config': app.config
        }

    # Error Handlers
    @app.errorhandler(404)
    def handle_not_found(error):
        """Render custom 404 page for missing or deleted media."""
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': 'Requested resource was not found.'
            }), 404
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def handle_server_error(error):
        """Render custom 500 error page."""
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': 'An internal server error occurred.'
            }), 500
        return render_template('500.html'), 500

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(error):
        """Handle uploads exceeding maximum allowed size."""
        max_mb = Config.MAX_CONTENT_LENGTH // (1024 * 1024)
        if request.is_json or request.headers.get(
                'Accept') == 'application/json':
            return jsonify({
                'success': False,
                'error': f'Payload exceeds maximum upload limit of {max_mb}MB.'
            }), 413
        return render_template(
            'base.html',
            error=f'File exceeds maximum limit of {max_mb}MB.'
        ), 413

    # Core Routes
    @app.route('/', strict_slashes=False)
    @app.route('/api/index', strict_slashes=False)
    def index():
        """Homepage: Photo & Video QR Generator Studio."""
        return render_template('index.html')

    @app.route('/upload/photo', methods=['POST'])
    def upload_photo():
        """Upload one photograph and generate QR code."""
        try:
            file_storage = request.files.get('file')
            if not file_storage or not file_storage.filename:
                return jsonify({
                    'success': False,
                    'error': 'Please select a photo file to upload.'
                }), 400

            title = request.form.get('title', '')
            description = request.form.get('description', '')
            qr_style = request.form.get('qr_style', 'classic')

            record = create_media(
                file_storage=file_storage,
                media_type='photo',
                title=title,
                description=description,
                qr_style=qr_style,
                public_base_url=get_public_base_url()
            )

            # Store creator token in session
            tokens = session.get('creator_tokens', [])
            tokens.append(record['creator_token'])
            session['creator_tokens'] = tokens
            session.modified = True

            base_url = get_public_base_url()
            return jsonify({
                'success': True,
                'media_id': record['id'],
                'creator_token': record['creator_token'],
                'title': record['title'],
                'media_type': 'photo',
                'media_url': f"{base_url}/m/{record['id']}",
                'qr_url': url_for(
                    'serve_qr_image', filename=record['qr_filename']),
                'result_url': url_for('qr_result', media_id=record['id'])
            })
        except ValueError as ve:
            return jsonify({'success': False, 'error': str(ve)}), 400
        except Exception as e:
            return jsonify(
                {'success': False, 'error': f'Upload failed: {str(e)}'}), 500

    @app.route('/upload/video', methods=['POST'])
    def upload_video():
        """Upload one video and generate QR code."""
        try:
            file_storage = request.files.get('file')
            if not file_storage or not file_storage.filename:
                return jsonify({
                    'success': False,
                    'error': 'Please select a video file to upload.'
                }), 400

            title = request.form.get('title', '')
            description = request.form.get('description', '')
            qr_style = request.form.get('qr_style', 'classic')

            record = create_media(
                file_storage=file_storage,
                media_type='video',
                title=title,
                description=description,
                qr_style=qr_style,
                public_base_url=get_public_base_url()
            )

            # Store creator token in session
            tokens = session.get('creator_tokens', [])
            tokens.append(record['creator_token'])
            session['creator_tokens'] = tokens
            session.modified = True

            base_url = get_public_base_url()
            return jsonify({
                'success': True,
                'media_id': record['id'],
                'creator_token': record['creator_token'],
                'title': record['title'],
                'media_type': 'video',
                'media_url': f"{base_url}/m/{record['id']}",
                'qr_url': url_for(
                    'serve_qr_image', filename=record['qr_filename']),
                'result_url': url_for('qr_result', media_id=record['id'])
            })
        except ValueError as ve:
            return jsonify({'success': False, 'error': str(ve)}), 400
        except Exception as e:
            return jsonify(
                {'success': False, 'error': f'Upload failed: {str(e)}'}), 500

    @app.route('/upload/document', methods=['POST'])
    def upload_document():
        """Upload one document (PDF, Word, Excel, PowerPoint, Text, etc.) and generate QR code."""
        try:
            file_storage = request.files.get('file')
            if not file_storage or not file_storage.filename:
                return jsonify({
                    'success': False,
                    'error': 'Please select a document file to upload.'
                }), 400

            title = request.form.get('title', '')
            description = request.form.get('description', '')
            qr_style = request.form.get('qr_style', 'classic')

            record = create_media(
                file_storage=file_storage,
                media_type='document',
                title=title,
                description=description,
                qr_style=qr_style,
                public_base_url=get_public_base_url()
            )

            # Store creator token in session
            tokens = session.get('creator_tokens', [])
            tokens.append(record['creator_token'])
            session['creator_tokens'] = tokens
            session.modified = True

            base_url = get_public_base_url()
            return jsonify({
                'success': True,
                'media_id': record['id'],
                'creator_token': record['creator_token'],
                'title': record['title'],
                'media_type': 'document',
                'media_url': f"{base_url}/m/{record['id']}",
                'qr_url': url_for(
                    'serve_qr_image', filename=record['qr_filename']),
                'result_url': url_for('qr_result', media_id=record['id'])
            })
        except ValueError as ve:
            return jsonify({'success': False, 'error': str(ve)}), 400
        except Exception as e:
            return jsonify(
                {'success': False, 'error': f'Upload failed: {str(e)}'}), 500

    @app.route('/result/<media_id>')
    def qr_result(media_id):
        """
        Display QR code result page with downloads, copy tools, and palette
        switcher.
        """
        record = get_media(media_id)
        if not record:
            abort(404)

        base_url = get_public_base_url()
        created_dt = record.get('created_at', '')
        try:
            parsed_dt = datetime.fromisoformat(created_dt)
            formatted_date = parsed_dt.strftime('%b %d, %Y')
        except Exception:
            formatted_date = 'Recently'

        return render_template(
            'result.html',
            media=record,
            media_url=f"{base_url}/m/{record['id']}",
            formatted_size=format_file_size(record.get('size_bytes', 0)),
            created_date=formatted_date
        )

    @app.route('/m/<media_id>')
    @app.route('/view/<media_id>')
    def media_viewer(media_id):
        """
        Public unlisted media viewer page.
        Displays photograph or plays video. Does not require login or app.
        Generates fresh short-lived signed URL from Supabase Storage.
        """
        record = get_media(media_id)
        if not record:
            abort(404)

        created_dt = record.get('created_at', '')
        try:
            parsed_dt = datetime.fromisoformat(created_dt)
            formatted_date = parsed_dt.strftime('%B %d, %Y')
        except Exception:
            formatted_date = 'Recently'

        base_url = get_public_base_url()
        signed_media_url = get_signed_media_url(record)

        return render_template(
            'viewer.html',
            media=record,
            base_url=base_url,
            media_file_url=signed_media_url,
            formatted_size=format_file_size(
                record.get('size_bytes') or record.get('file_size') or 0
            ),
            created_date=formatted_date
        )

    @app.route('/media-file/<media_id>')
    def serve_media_file(media_id):
        """
        Safely serve media file (photo or video) with HTTP Range support for
        seeking. Redirects to short-lived signed URL when Supabase is
        configured.
        """
        record = get_media(media_id)
        if not record:
            abort(404)

        # When Supabase is configured, stream directly via signed URL
        if Config.is_supabase_configured():
            signed_url = get_signed_media_url(record)
            if signed_url:
                return redirect(signed_url, code=307)

        safe_filename = os.path.basename(record['filename'])
        media_type = record.get('type') or record.get('media_type') or 'photo'
        if media_type == 'photo':
            folder = app.config.get(
                'UPLOAD_FOLDER_PHOTOS',
                Config.UPLOAD_FOLDER_PHOTOS)
        elif media_type == 'document':
            folder = app.config.get(
                'UPLOAD_FOLDER_DOCUMENTS',
                Config.UPLOAD_FOLDER_DOCUMENTS)
        else:
            folder = app.config.get(
                'UPLOAD_FOLDER_VIDEOS',
                Config.UPLOAD_FOLDER_VIDEOS)

        # conditional=True enables HTTP 206 Partial Content for video seeking
        return send_from_directory(
            folder,
            safe_filename,
            conditional=True,
            mimetype=record.get('mime_type')
        )

    @app.route('/download-qr/<media_id>')
    def download_qr(media_id):
        """Download generated QR code PNG as an attachment."""
        record = get_media(media_id)
        if not record or not record.get('qr_filename'):
            abort(404)

        qr_folder = app.config.get('QR_FOLDER', Config.QR_FOLDER)
        safe_filename = os.path.basename(record['qr_filename'])
        download_name = f"qr-{record['type']}-{record['id']}.png"

        return send_from_directory(
            qr_folder,
            safe_filename,
            as_attachment=True,
            download_name=download_name
        )

    @app.route('/qr-image/<path:filename>')
    def serve_qr_image(filename):
        """Serve generated QR code image file from root qr_codes directory."""
        qr_folder = app.config.get('QR_FOLDER', Config.QR_FOLDER)
        safe_name = os.path.basename(filename)
        return send_from_directory(qr_folder, safe_name)

    @app.route('/generate-qr', methods=['POST'])
    def regenerate_qr_endpoint():
        """
        Regenerate QR code style palette without changing the media link.
        """
        media_id = request.form.get('media_id') or (request.json.get(
            'media_id') if request.is_json and request.json else None)
        qr_style = request.form.get('qr_style') or (request.json.get(
            'qr_style') if request.is_json and request.json else 'classic')

        if not media_id:
            return jsonify(
                {'success': False, 'error': 'media_id is required.'}), 400

        try:
            base_url = get_public_base_url()
            updated_record = update_media_qr_style(
                media_id, qr_style, base_url)
            return jsonify({
                'success': True,
                'media_id': media_id,
                'qr_style': updated_record['qr_style'],
                'qr_url': url_for(
                    'serve_qr_image',
                    filename=updated_record['qr_filename']
                ),
                'media_url': f"{base_url}/m/{media_id}"
            })
        except ValueError as ve:
            return jsonify({'success': False, 'error': str(ve)}), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to update style: {str(e)}'
            }), 500

    @app.route('/my-codes')
    def my_codes_page():
        """Display the creator management dashboard."""
        return render_template('my_codes.html')

    @app.route('/api/media/<media_id>', methods=['GET'])
    def get_media_api(media_id):
        """Return public metadata for a media record as JSON."""
        record = get_media(media_id)
        if not record:
            return jsonify(
                {'success': False, 'error': 'Media not found.'}), 404

        base_url = get_public_base_url()
        return jsonify({
            'success': True,
            'data': format_media_dict(record, base_url)
        })

    @app.route('/api/media/<media_id>/delete', methods=['POST'])
    def delete_media_api(media_id):
        """
        Permanently delete media record, files, and QR image after creator
        authorization.
        """
        provided_token = request.headers.get('X-Creator-Token')
        if not provided_token and request.is_json and request.json:
            provided_token = request.json.get('creator_token')

        # Fallback to session if no explicit token provided in header/json
        if not provided_token:
            record = get_media(media_id)
            if record and record.get('creator_token') in session.get(
                    'creator_tokens', []):
                provided_token = record['creator_token']

        success, message, code = delete_media_and_files(
            media_id, provided_token or '')
        if success:
            tokens = session.get('creator_tokens', [])
            if provided_token in tokens:
                tokens.remove(provided_token)
                session['creator_tokens'] = tokens
                session.modified = True

            return jsonify({'success': True, 'message': message}), code
        else:
            return jsonify({'success': False, 'error': message}), code

    @app.route('/api/admin/regenerate-qr-codes', methods=['POST'])
    def batch_regenerate_qr():
        """
        Batch regenerate existing QR codes with effective or specified URL.
        Preserves existing media IDs and files.
        """
        target_url = None
        if request.is_json and request.json:
            target_url = request.json.get('base_url')
        elif request.form.get('base_url'):
            target_url = request.form.get('base_url')

        res = regenerate_all_qr_codes(new_base_url=target_url)
        return jsonify(res), (200 if res.get('success') else 500)

    return app


app = create_app()

if __name__ == '__main__':
    from config import get_lan_ip, resolve_public_base_url, is_loopback
    
    # Run on 0.0.0.0:5000 so external proxies and LAN devices can connect
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    
    # Never expose Flask debug mode publicly unless FLASK_DEBUG is explicitly enabled
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    
    lan_ip = get_lan_ip()
    target_pub = resolve_public_base_url()
    
    print("=" * 65)
    print("  LensQR Photo & Video QR Generator")
    print(f"  * Host Binding:       {host}:{port}")
    print(f"  * Local PC Access:    http://127.0.0.1:{port}")
    print(f"  * Mobile/LAN Access:  http://{lan_ip}:{port}")
    print(f"  * Public Base URL:    {target_pub}")
    print(f"  * QR Codes Will Use:  {target_pub}")
    print(f"  * Debug Mode:         {debug} (Interactive debugger off)")
    print("=" * 65)
    if is_loopback(target_pub) or target_pub.startswith(f"http://{lan_ip}"):
        print("  NOTICE: To allow people from other locations (e.g. Punjab) to")
        print("          scan QR codes, run with Cloudflare Tunnel:")
        print("          Run: python run_with_tunnel.py")
        print("=" * 65)
    
    app.run(host=host, port=port, debug=debug)
