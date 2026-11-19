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
    When Vercel rewrites requests /(.*) to /api/index, PATH_INFO arrives as
    /api/index or /api/index/<subpath>.
    This strips the /api/index prefix so Flask routing matches correctly.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path == '/api/index' or path == '/api/index/':
            environ['PATH_INFO'] = '/'
        elif path.startswith('/api/index/'):
            environ['PATH_INFO'] = path[len('/api/index'):] or '/'

        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathFixer(app.wsgi_app)
