"""Starts the relay on a temporary copy of the fixture registry and checks what it serves and writes.
Run:  python3 test/relay_test.py      (exit code 1 on any failure; the page part needs Playwright and is skipped without it)"""
import json, os, re, shutil, socket, subprocess, sys, tempfile, time, hashlib
import urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RELAY = next(p for p in (ROOT / 'cde_registry_browser_relay.py', ROOT / 'dist' / 'cde_registry_browser_relay.py') if p.is_file())
FIX = HERE / 'fixtures' if (HERE / 'fixtures').is_dir() else ROOT / 'fixtures' / 'registry'

fails = []
def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        fails.append(msg)

def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

tmp = Path(tempfile.mkdtemp(prefix='cdeb-relay-test-'))
reg = tmp / 'registry'
shutil.copytree(FIX, reg)
(reg / 'staged_proposed').mkdir()
shutil.copy(reg / 'tissue_weight.json', reg / 'staged_proposed' / 'tissue_weight.json')
before = {p.name: sha(p) for p in reg.glob('*.json')}
port = free_port()
env = {k: v for k, v in os.environ.items() if k != 'OMOPHUB_API_KEY'}
env.update(CDEB_RELAY_PORT=str(port), CDEB_REGISTRY_DIR=str(reg))
proc = subprocess.Popen([sys.executable, str(RELAY)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
BASE = 'http://127.0.0.1:%d' % port

def req(method, path, body=None, headers=None):
    r = urllib.request.Request(BASE + path, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

try:
    for _ in range(50):
        try:
            if req('GET', '/health')[0] == 200:
                break
        except Exception:
            time.sleep(0.1)
    st, page = req('GET', '/')
    m = re.search(rb'<meta name="cdeb-relay-token" content="([^"]+)">', page)
    check(st == 200 and m is not None, 'the page is served with its token')
    tok = {'X-CDEB-Token': m.group(1).decode() if m else ''}

    st, _ = req('GET', '/registry/list')
    check(st == 403, 'list without the token is refused (%d)' % st)
    st, _ = req('GET', '/registry/list', headers={'X-CDEB-Token': 'wrong'})
    check(st == 403, 'list with a wrong token is refused (%d)' % st)
    st, _ = req('GET', '/registry/list', headers=dict(tok, Origin='null'))
    check(st == 403, 'a null-origin page is refused even with the token (%d)' % st)
    st, _ = req('GET', '/registry/list', headers=dict(tok, Origin='https://example.org'))
    check(st == 403, 'another site is refused (%d)' % st)
    st, _ = req('GET', '/registry/list', headers=dict(tok, Host='evil.test:%d' % port))
    check(st == 403, 'a foreign Host header is refused (%d)' % st)
    st, body = req('GET', '/registry/list', headers=tok)
    lst = json.loads(body) if st == 200 else {}
    check(st == 200 and len(lst.get('files', [])) == len(before), 'list: %d registry files' % len(lst.get('files', [])))
    check(lst.get('staged') == ['tissue_weight.json'] and not any(f.startswith('staged_proposed') for f in lst.get('files', [])), 'staged copies are listed apart from the registry files')

    st, body = req('GET', '/registry/file?area=registry&path=csf_tau.json', headers=tok)
    check(st == 200 and body == (reg / 'csf_tau.json').read_bytes(), 'reads a registry file byte for byte')
    for bad in ['../x.json', '/etc/passwd', 'a%5Cb.json', '.hidden.json', 'staged_proposed/tissue_weight.json', 'csf_tau.txt', 'a/../csf_tau.json']:
        st, _ = req('GET', '/registry/file?area=registry&path=' + bad, headers=tok)
        check(st == 400, 'refuses path %s (%d)' % (bad, st))
    st, _ = req('GET', '/registry/file?area=staged&path=nothing.json', headers=tok)
    check(st == 404, 'a missing staged file is 404')

    text = (reg / 'csf_tau.json').read_text(encoding='utf-8').replace('"csf_tau"', '"csf_tau"', 1)
    edited = text.replace('"definition": "', '"definition": "EDITED ', 1).encode('utf-8')
    st, body = req('PUT', '/registry/staged?path=csf_tau.json', edited, dict(tok, **{'Content-Type': 'application/json'}))
    check(st == 200 and (reg / 'staged_proposed' / 'csf_tau.json').read_bytes() == edited, 'PUT writes staged_proposed/csf_tau.json byte for byte')
    st, _ = req('PUT', '/registry/staged?path=sub/new_one.json', b'{"a": 1}\n', tok)
    check(st == 200 and (reg / 'staged_proposed' / 'sub' / 'new_one.json').is_file(), 'PUT creates subfolders inside staged_proposed')
    st, _ = req('PUT', '/registry/staged?path=csf_tau.json', b'{not json', tok)
    check(st == 400 and (reg / 'staged_proposed' / 'csf_tau.json').read_bytes() == edited, 'invalid JSON is refused and nothing is written')
    st, _ = req('PUT', '/registry/staged?path=../csf_tau.json', b'{}', tok)
    check(st == 400, 'PUT refuses a path outside staged_proposed (%d)' % st)
    st, _ = req('PUT', '/registry/staged?path=csf_tau.json', b'{}', {'Content-Type': 'application/json'})
    check(st == 403, 'PUT without the token is refused (%d)' % st)
    st, _ = req('PUT', '/registry/staged?path=csf_tau.json', b'{}', dict(tok, Origin='https://example.org'))
    check(st == 403, 'PUT from another site is refused (%d)' % st)
    check({p.name: sha(p) for p in reg.glob('*.json')} == before, 'no registry file changed')
    check(not list((reg / 'staged_proposed').rglob('.cdeb-*')), 'no temporary files left behind')

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print('  skip the page part (Playwright is not installed)')
    if sync_playwright:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            errors = []
            pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.goto(BASE + '/')
            pg.wait_for_function('window.CDEB && CDEB.files.size > 0 && !CDEB.S.loading', timeout=15000)
            n = pg.evaluate('CDEB.files.size')
            check(n == len(before) + 1, 'the page opened the registry by itself: %d entries (16 registry files + 1 staged-only)' % n)
            check(pg.evaluate("CDEB.files.get('csf_tau.json').stagedId") == 'csf_tau.json' and 'EDITED' in pg.evaluate("CDEB.files.get('csf_tau.json').value.definition"),
                  'where a staged copy exists, the staged copy is what opens')
            check(pg.evaluate("CDEB.files.has('staged_proposed/sub/new_one.json')"), 'a staged file with no registry counterpart opens as its own entry')
            pg.evaluate("CDEB.setPath(CDEB.files.get('prodromal_category.json'), ['definition'], 'saved through the relay')")
            pg.evaluate("() => { CDEB.saveFile(CDEB.files.get('prodromal_category.json')); }")
            pg.wait_for_function("CDEB.files.get('prodromal_category.json').saveState && CDEB.files.get('prodromal_category.json').saveState.kind !== 'busy'", timeout=10000)
            stt = pg.evaluate("CDEB.files.get('prodromal_category.json').saveState")
            out = reg / 'staged_proposed' / 'prodromal_category.json'
            check(stt['kind'] == 'ok' and out.is_file() and 'saved through the relay' in out.read_text(encoding='utf-8'), 'Save through the relay wrote staged_proposed/prodromal_category.json: ' + stt['msg'])
            check(out.read_text(encoding='utf-8') == pg.evaluate("CDEB.currentText(CDEB.files.get('prodromal_category.json'))"), 'disk text equals the page text')
            pg.evaluate("CDEB.setPath(CDEB.files.get('initial_diagnosis.json'), ['registry_label'], 'initial_diagnosis_v2')")
            pg.evaluate("() => { CDEB.saveFile(CDEB.files.get('initial_diagnosis.json')); }")
            pg.wait_for_function("CDEB.files.get('initial_diagnosis.json').saveState && CDEB.files.get('initial_diagnosis.json').saveState.kind !== 'busy'", timeout=10000)
            check((reg / 'staged_proposed' / 'initial_diagnosis_v2.json').is_file(), 'a relabelled element is staged under its new label')
            check({q.name: sha(q) for q in reg.glob('*.json')} == before, 'still no registry file changed')
            check(not errors, 'no page errors: %s' % errors[:3])
            b.close()
finally:
    proc.terminate()
    try:
        out = proc.communicate(timeout=5)[0].decode('utf-8', 'replace')
    except Exception:
        out = ''
    check('OMOPHUB' not in out or 'NOT FOUND' in out, 'relay output mentions no key value')
    shutil.rmtree(tmp, ignore_errors=True)

print('\n%d failure(s)' % len(fails))
sys.exit(1 if fails else 0)
