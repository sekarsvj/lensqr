import os
import sys
import urllib.parse

# Ensure root directory is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app


class VercelPathFixer:
    """
    WSGI middleware for Vercel Serverless routing.
    Extracts the matched path from the __path__ rewrite parameter,
    restoring PATH_INFO so Flask routing and HTTP methods (POST, GET)
    work properly on all routes.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        if environ.get('HTTP_X_DEBUG_ENV') == '1':
            import json
            headers_dict = {k: str(v) for k, v in environ.items() if isinstance(v, (str, int, float, bool))}
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [json.dumps(headers_dict, indent=2).encode('utf-8')]

        query = environ.get('QUERY_STRING', '')
        params = urllib.parse.parse_qs(query)

        if '__path__' in params:
            raw_path = params['__path__'][0] if params['__path__'] else ''
            target_path = '/' + raw_path.lstrip('/') if raw_path else '/'
            environ['PATH_INFO'] = target_path

            # Clean __path__ parameter out of QUERY_STRING
            clean_params = {k: v for k, v in params.items() if k != '__path__'}
            environ['QUERY_STRING'] = urllib.parse.urlencode(clean_params, doseq=True)
        elif environ.get('PATH_INFO') in ('/api/index', '/api/index/'):
            environ['PATH_INFO'] = '/'

        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathFixer(app.wsgi_app)
