#!/usr/bin/env python3
"""Local server for the CDE Registry browser: serves the page, the registry folder, and OMOP Hub search.

    python cde_registry_browser_relay.py [--registry PATH]      then open  http://127.0.0.1:8765/

- Listens on 127.0.0.1 only.
- Serves cde_registry_browser.html (next to this script) at http://127.0.0.1:8765/ and
  opens the registry folder in it: by default the repository's registry/ (two folders up
  from this script), or --registry PATH, or the CDEB_REGISTRY_DIR environment variable.
- Registry files are only read. Saves from the page are written to
  <registry>/staged_proposed/<path> and nowhere else.
- The registry calls need a token that exists only in the page this server serves, so
  other pages cannot read or write through it.
- Reads OMOPHUB_API_KEY from the environment, else from a .env file next to this
  script (copy .env.example to .env and put your own key in it). The key is sent only to api.omophub.com; it is never printed, logged, or
  returned to the page. Passes on two read-only calls: concept search and concept
  lookup by id.
- Standard library only.
"""
import argparse
import hmac
import json
import os
import secrets
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = '127.0.0.1'
PORT = int(os.environ.get('CDEB_RELAY_PORT', '8765'))
API = 'https://api.omophub.com/v1'
USER_AGENT = 'sysbio-cdm/1.0 (cde-registry-browser relay)'
HERE = Path(__file__).resolve().parent
PAGE = HERE / 'cde_registry_browser.html'
STAGED = 'staged_proposed'
REGISTRY = Path(os.environ.get('CDEB_REGISTRY_DIR') or (HERE.parent.parent / 'registry')).resolve()
TOKEN = secrets.token_urlsafe(32)
TOKEN_META = b'<meta name="cdeb-relay-token" content="">'
MAX_BODY = 8 * 1024 * 1024
MAX_DEPTH = 5
SEARCH_PARAMS = {'query', 'vocabulary_ids', 'domain_ids', 'concept_class_ids', 'standard_concept', 'include_invalid', 'page', 'page_size'}
CACHE_SECONDS = 24 * 3600
CACHE_MAX = 3000


def load_key():
    """Return (key, where it came from). Never prints the key."""
    key = os.environ.get('OMOPHUB_API_KEY', '').strip()
    if key:
        return key, 'environment variable'
    env = HERE / '.env'
    if env.is_file():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line[7:].lstrip()
            name, sep, value = line.partition('=')
            if sep and name.strip() == 'OMOPHUB_API_KEY':
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
                    value = value[1:-1]
                elif ' #' in value:
                    value = value.split(' #', 1)[0].rstrip()
                if value:
                    return value, '.env next to the relay'
    return '', None


KEY, KEY_SOURCE = load_key()
_cache = {}
_cache_lock = threading.Lock()


def cache_get(k):
    with _cache_lock:
        hit = _cache.get(k)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1], hit[2]
        return None


def cache_put(k, status, body):
    with _cache_lock:
        if len(_cache) >= CACHE_MAX:
            for old in sorted(_cache, key=lambda x: _cache[x][0])[: CACHE_MAX // 4]:
                _cache.pop(old, None)
        _cache[k] = (time.time(), status, body)


def upstream(path, query):
    """Call OMOP Hub. Returns (status, body bytes). The key goes only in the Authorization header."""
    url = API + '/' + path + (('?' + urllib.parse.urlencode(query)) if query else '')
    req = urllib.request.Request(url, headers={
        'Authorization': 'Bearer ' + KEY,
        'Accept': 'application/json',
        'User-Agent': USER_AGENT,
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        body = e.read() or b''
        try:
            json.loads(body.decode('utf-8'))
        except Exception:
            body = json.dumps({'error': {'code': 'upstream_http_' + str(e.code), 'message': 'OMOP Hub answered HTTP ' + str(e.code)}}).encode()
        return e.code, body
    except Exception as e:  # network failure, timeout, TLS
        msg = type(e).__name__ + (': ' + str(e.reason) if hasattr(e, 'reason') else '')
        return 502, json.dumps({'error': {'code': 'upstream_unreachable', 'message': 'Could not reach OMOP Hub (' + msg + ')'}}).encode()


def safe_rel(raw):
    """A relative .json path inside the registry, or None. No absolute paths, no '..', no hidden parts."""
    if not raw or '\\' in raw or raw.startswith('/') or '\x00' in raw:
        return None
    parts = raw.split('/')
    if len(parts) > MAX_DEPTH + 1 or any(p in ('', '.', '..') or p.startswith('.') for p in parts):
        return None
    if not parts[-1].lower().endswith('.json'):
        return None
    return parts


def inside(base, parts):
    p = base.joinpath(*parts).resolve()
    try:
        p.relative_to(base.resolve())
    except ValueError:
        return None
    return p


def list_json(base, skip_staged):
    out = []
    if not base.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(base):
        rel_dir = Path(dirpath).relative_to(base)
        depth = len(rel_dir.parts)
        keep = []
        for d in sorted(dirnames):
            if d.startswith('.') or depth >= MAX_DEPTH or (skip_staged and depth == 0 and d == STAGED):
                continue
            keep.append(d)
        dirnames[:] = keep
        for f in sorted(filenames):
            if f.lower().endswith('.json') and not f.startswith('.'):
                out.append('/'.join(rel_dir.parts + (f,)))
    return sorted(out)


def write_staged(parts, body):
    target = inside(REGISTRY / STAGED, parts)
    if target is None:
        raise ValueError('path outside staged_proposed')
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.cdeb-', suffix='.tmp', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'wb') as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return target


class Handler(BaseHTTPRequestHandler):
    server_version = 'cde-registry-browser-relay/1.0'
    protocol_version = 'HTTP/1.1'

    def allowed_origin(self):
        """None = refuse; '' = same-origin or non-browser (no CORS header needed); else the Origin to echo."""
        host = (self.headers.get('Host') or '').lower()
        if host not in ('127.0.0.1:%d' % PORT, 'localhost:%d' % PORT):
            return None  # DNS-rebinding guard
        origin = self.headers.get('Origin')
        if origin is None:
            site = (self.headers.get('Sec-Fetch-Site') or '').lower()
            return '' if site in ('', 'same-origin', 'none') else None
        if origin in ('null', 'http://127.0.0.1:%d' % PORT, 'http://localhost:%d' % PORT):
            return origin
        return None

    def send(self, status, body, ctype='application/json; charset=utf-8', origin=''):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def fail(self, status, code, message, origin=''):
        self.send(status, json.dumps({'error': {'code': code, 'message': message}}).encode(), origin=origin)

    def do_OPTIONS(self):
        origin = self.allowed_origin()
        if origin is None:
            return self.fail(403, 'origin_not_allowed', 'This relay only answers the CDE Registry browser on this computer.')
        self.send_response(204)
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Methods', 'GET')  # registry calls are same-origin only
            self.send_header('Access-Control-Max-Age', '600')
            self.send_header('Vary', 'Origin')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        origin = self.allowed_origin()
        if origin is None:
            return self.fail(403, 'origin_not_allowed', 'This relay only answers the CDE Registry browser on this computer.')
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        if path in ('/', '/cde_registry_browser.html'):
            if not PAGE.is_file():
                return self.fail(404, 'no_page', 'cde_registry_browser.html is not next to the relay script.', origin)
            body = PAGE.read_bytes()
            if TOKEN_META in body:
                body = body.replace(TOKEN_META, b'<meta name="cdeb-relay-token" content="' + TOKEN.encode() + b'">', 1)
            return self.send(200, body, 'text/html; charset=utf-8', origin)
        if path.startswith('/registry/'):
            return self.registry_get(path, parsed.query, origin)
        if path == '/health':
            return self.send(200, json.dumps({'service': 'cde-registry-browser-relay', 'has_key': bool(KEY), 'key_source': KEY_SOURCE}).encode(), origin=origin)
        if path.startswith('/omophub/'):
            if not KEY:
                return self.fail(503, 'no_api_key', 'The relay has no OMOPHUB_API_KEY (environment, or .env next to the relay script).', origin)
            sub = path[len('/omophub/'):]
            q = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
            if sub == 'search/concepts':
                query = [(k, v[-1]) for k, v in sorted(q.items()) if k in SEARCH_PARAMS]
                if not any(k == 'query' for k, _ in query):
                    return self.fail(400, 'no_query', 'search/concepts needs a query.', origin)
            elif sub.startswith('concepts/') and sub[len('concepts/'):].isdigit() and len(sub) < 40:
                query = []
            else:
                return self.fail(404, 'not_relayed', 'The relay passes on only search/concepts and concepts/<id>.', origin)
            ck = sub + '?' + urllib.parse.urlencode(query)
            hit = cache_get(ck)
            if hit:
                return self.send(hit[0], hit[1], origin=origin)
            status, body = upstream(sub, query)
            if status == 200:
                cache_put(ck, status, body)
            return self.send(status, body, origin=origin)
        return self.fail(404, 'not_found', 'Unknown path.', origin)

    def registry_allowed(self, origin):
        """Registry calls: only the page this server served (same origin, carrying the token)."""
        if origin is None or origin == 'null':
            return False
        tok = self.headers.get('X-CDEB-Token') or ''
        return hmac.compare_digest(tok.encode(), TOKEN.encode())

    def registry_get(self, path, query, origin):
        if not self.registry_allowed(origin):
            return self.fail(403, 'no_token', 'Registry calls are answered only for the page this relay serves.', origin)
        if not REGISTRY.is_dir():
            return self.fail(404, 'no_registry', 'The registry folder does not exist: ' + str(REGISTRY), origin)
        if path == '/registry/list':
            body = {'name': REGISTRY.name, 'registry': str(REGISTRY), 'staged_dir': str(REGISTRY / STAGED),
                    'files': list_json(REGISTRY, True), 'staged': list_json(REGISTRY / STAGED, False)}
            return self.send(200, json.dumps(body).encode(), origin=origin)
        if path == '/registry/file':
            q = urllib.parse.parse_qs(query)
            area = (q.get('area') or ['registry'])[-1]
            parts = safe_rel((q.get('path') or [''])[-1])
            if parts is None or area not in ('registry', 'staged') or (area == 'registry' and parts[0] == STAGED):
                return self.fail(400, 'bad_path', 'Not a .json path inside the registry.', origin)
            p = inside(REGISTRY / STAGED if area == 'staged' else REGISTRY, parts)
            if p is None or not p.is_file():
                return self.fail(404, 'no_file', 'No such file.', origin)
            return self.send(200, p.read_bytes(), 'application/json; charset=utf-8', origin)
        return self.fail(404, 'not_found', 'Unknown path.', origin)

    def do_PUT(self):
        origin = self.allowed_origin()
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path != '/registry/staged':
            return self.fail(404, 'not_found', 'Only /registry/staged accepts writes.', origin or '')
        if not self.registry_allowed(origin):
            return self.fail(403, 'no_token', 'Registry calls are answered only for the page this relay serves.', origin or '')
        parts = safe_rel((urllib.parse.parse_qs(parsed.query).get('path') or [''])[-1])
        if parts is None:
            return self.fail(400, 'bad_path', 'Not a .json path inside staged_proposed.', origin)
        try:
            n = int(self.headers.get('Content-Length') or '-1')
        except ValueError:
            n = -1
        if n < 0 or n > MAX_BODY:
            return self.fail(413 if n > MAX_BODY else 411, 'bad_length', 'A body of at most 8 MB with Content-Length is required.', origin)
        body = self.rfile.read(n)
        try:
            json.loads(body.decode('utf-8'))
        except Exception:
            return self.fail(400, 'not_json', 'The body is not valid UTF-8 JSON; nothing written.', origin)
        if not REGISTRY.is_dir():
            return self.fail(404, 'no_registry', 'The registry folder does not exist: ' + str(REGISTRY), origin)
        try:
            target = write_staged(parts, body)
        except Exception as e:
            return self.fail(500, 'write_failed', 'Could not write: ' + type(e).__name__, origin)
        rel = '/'.join(target.relative_to(REGISTRY).parts)
        return self.send(200, json.dumps({'ok': True, 'path': rel, 'bytes': len(body)}).encode(), origin=origin)

    def log_message(self, fmt, *args):
        # method, path and status only; the key never appears in a request line
        sys.stderr.write('%s  %s\n' % (time.strftime('%H:%M:%S'), fmt % args))


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # a browser or client closing a kept-alive connection is normal; stay quiet about it
        if isinstance(sys.exc_info()[1], (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def main():
    global REGISTRY
    ap = argparse.ArgumentParser(description='Local server for the CDE Registry browser.')
    ap.add_argument('--registry', help='registry folder to open (default: the repository registry/ two folders up, or CDEB_REGISTRY_DIR)')
    args = ap.parse_args()
    if args.registry:
        REGISTRY = Path(args.registry).expanduser().resolve()
    try:
        server = Server((HOST, PORT), Handler)
    except OSError as e:
        print('Could not listen on %s:%d (%s). Is the relay already running?' % (HOST, PORT, e), flush=True)
        return 1
    print('CDE Registry browser relay on http://%s:%d/' % (HOST, PORT), flush=True)
    print('OMOP Hub API key: ' + ('found (' + KEY_SOURCE + ')' if KEY else 'NOT FOUND - copy .env.example to .env next to this script and put your key in it'), flush=True)
    print('Page: ' + ('http://%s:%d/' % (HOST, PORT) if PAGE.is_file() else 'cde_registry_browser.html is not next to this script'), flush=True)
    print('Registry: ' + str(REGISTRY) + ('' if REGISTRY.is_dir() else '  (DOES NOT EXIST)'), flush=True)
    print('Saves go to: ' + str(REGISTRY / STAGED), flush=True)
    print('Ctrl+C stops it.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
