import os
import sys

# Ensure root directory is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app


class VercelPathFixer:
    """
    WSGI middleware to fix PATH_INFO on Vercel.
    Correctly extracts the original path from Vercel's HTTP headers
    or strips the /api/index prefix from rewrites.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # 1. Prefer original URL headers passed by Vercel edge
        orig_uri = environ.get('HTTP_X_FORWARDED_URI') or environ.get('HTTP_X_MATCHED_PATH')
        if orig_uri:
            orig_path = orig_uri.split('?')[0]
            if orig_path.startswith('/api/index'):
                orig_path = orig_path[len('/api/index'):] or '/'
            environ['PATH_INFO'] = orig_path
        else:
            path = environ.get('PATH_INFO', '')
            if path in ('/api/index', '/api/index/'):
                environ['PATH_INFO'] = '/'
            elif path.startswith('/api/index/'):
                environ['PATH_INFO'] = path[len('/api/index'):] or '/'

        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathFixer(app.wsgi_app)
