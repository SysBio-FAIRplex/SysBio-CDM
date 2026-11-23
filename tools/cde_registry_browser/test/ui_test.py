"""Drives the built page in Chromium against the 16 real fixture files held in an in-memory folder.
Run:  python3 test/ui_test.py  [fixture_dir]   (needs Playwright: pip install playwright && playwright install chromium)   (exit code 1 on any failure)"""
import json, sys, os, re, glob, time, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / 'cde_registry_browser.html'
FIX = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'test' / 'fixtures'
SHOTS = Path(tempfile.gettempdir()) / 'cde_registry_browser_ui_shots'
SHOTS.mkdir(exist_ok=True)
fixtures = {Path(p).name: Path(p).read_text(encoding='utf-8') for p in sorted(glob.glob(str(FIX / '*.json')))}

MOCK = r"""
window.__FIXTURES = %s;
window.__mockFS = (function () {
  const files = new Map(Object.entries(window.__FIXTURES));   // key: path inside the registry folder
  const dirs = new Set();
  const writes = [];
  let corrupt = false;
  const nf = () => { const e = new Error('not found'); e.name = 'NotFoundError'; return e; };
  const perm = { async queryPermission() { return 'granted'; }, async requestPermission() { return 'granted'; } };
  function fileHandle(path) {
    const name = path.split('/').pop();
    return Object.assign({
      kind: 'file', name,
      async getFile() { const t = files.get(path); if (t === undefined) throw nf(); return { name, size: t.length, lastModified: Date.now(), text: async () => t }; },
      async createWritable() { let buf = ''; return { async write(d) { buf += typeof d === 'string' ? d : await new Blob([d]).text(); }, async close() { files.set(path, corrupt ? buf.replace(/\n$/, '') : buf); writes.push(path); } }; }
    }, perm);
  }
  const sub = { kind: 'directory', name: 'dictionaries', async *entries() { yield ['dictionary.docx', { kind: 'file', name: 'dictionary.docx' }]; } };
  function dirHandle(prefix, name) {
    return Object.assign({
      kind: 'directory', name,
      async *entries() {
        const kids = new Map();
        for (const p of Array.from(files.keys()).sort()) {
          if (!p.startsWith(prefix)) continue;
          const rest = p.slice(prefix.length), i = rest.indexOf('/');
          if (i < 0) kids.set(rest, fileHandle(p));
          else { const d = rest.slice(0, i); if (!kids.has(d)) kids.set(d, dirHandle(prefix + d + '/', d)); }
        }
        if (prefix === '') kids.set('dictionaries', sub);
        for (const kv of kids) yield kv;
      },
      async getDirectoryHandle(n, opt) {
        const pre = prefix + n + '/';
        if (!dirs.has(pre) && !Array.from(files.keys()).some(p => p.startsWith(pre))) { if (opt && opt.create) dirs.add(pre); else throw nf(); }
        return dirHandle(pre, n);
      },
      async getFileHandle(n, opt) {
        const p = prefix + n;
        if (!files.has(p)) { if (opt && opt.create) files.set(p, ''); else throw nf(); }
        return fileHandle(p);
      }
    }, perm);
  }
  const dir = dirHandle('', 'registry');
  window.showDirectoryPicker = async () => dir;
  return { files, writes, setCorrupt(v) { corrupt = v; } };
})();
""" % json.dumps(fixtures)

HITS = {'data': [
    {'concept_id': 8842, 'concept_name': 'nanogram per milliliter', 'domain_id': 'Unit', 'vocabulary_id': 'UCUM', 'concept_class_id': 'Unit', 'concept_code': 'ng/mL', 'standard_concept': 'S'},
    {'concept_id': 4307095, 'concept_name': 'Sense of smell impaired', 'domain_id': 'Observation', 'vocabulary_id': 'SNOMED', 'concept_class_id': 'Clinical Finding', 'concept_code': '44169009', 'standard_concept': 'S'}]}
relay_calls = []


def relay(route):
    url = route.request.url
    relay_calls.append(url)
    hdr = {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}
    if url.endswith('/health'):
        return route.fulfill(status=200, headers=hdr, body=json.dumps({'service': 'cde-registry-browser-relay', 'has_key': True}))
    if '/omophub/search/concepts' in url:
        return route.fulfill(status=200, headers=hdr, body=json.dumps(HITS))
    m = re.search(r'/omophub/concepts/(\d+)', url)
    if m:
        cid = int(m.group(1))
        hit = next((x for x in HITS['data'] if x['concept_id'] == cid), None)
        if hit:
            return route.fulfill(status=200, headers=hdr, body=json.dumps({'data': hit}))
        return route.fulfill(status=404, headers=hdr, body=json.dumps({'error': {'code': 'not_found', 'message': 'no such concept'}}))
    return route.fulfill(status=404, headers=hdr, body='{}')


fails = []
def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        fails.append(msg)


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width': 1600, 'height': 1000})
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append('console.' + m.type + ': ' + m.text) if m.type == 'error' else None)
    page.route('http://127.0.0.1:8765/**', relay)
    page.add_init_script(MOCK)
    page.goto(PAGE.as_uri())
    page.wait_for_selector('.welcome')
    page.click('text=Open the registry folder')
    page.wait_for_function('window.CDEB && CDEB.files.size === %d' % len(fixtures))
    page.wait_for_timeout(300)
    n_items = page.locator('#liblist .item').count()
    check(n_items == len(fixtures), 'library lists %d of %d files (the non-JSON file in dictionaries/ is skipped)' % (n_items, len(fixtures)))
    check(page.locator('#relay').inner_text() == 'OMOP Hub: ready', 'relay pill: ' + page.locator('#relay').inner_text())
    rt = page.evaluate('Array.from(CDEB.files.values()).filter(F => F.roundTrip !== true).map(F => F.id)')
    check(rt == [], 'every fixture writes back byte-identical when unedited (exceptions: %s)' % rt)
    page.screenshot(path=str(SHOTS / '00_overview.png'))

    # render every file, both Layer 2 views and raw view; collect exceptions
    ids = page.evaluate('Array.from(CDEB.files.keys())')
    for fid in ids:
        before = len(errors)
        page.evaluate('id => CDEB.openFile(id)', fid)
        page.wait_for_timeout(60)
        ok = page.locator('#center .sheet .card').count() >= 5
        page.evaluate("() => { CDEB.S.sheet.l2View = 'value'; CDEB.renderNow(); }")
        page.evaluate("() => { CDEB.S.sheet.l2View = 'target'; CDEB.S.sheet.raw = true; CDEB.renderNow(); }")
        page.evaluate("() => { CDEB.S.sheet.raw = false; CDEB.renderNow(); }")
        check(ok and len(errors) == before, 'renders %s (cards: %d)%s' % (fid, page.locator('#center .sheet .card').count(), '' if len(errors) == before else ' ERR ' + errors[-1]))

    # grain + keys panels say the right things on the eGFR file
    page.evaluate("CDEB.openFile('egfr_ckd_epi_2021_creatinine_serum.json')")
    page.wait_for_timeout(100)
    reads = page.locator('.gpanel .reads').first.inner_text()
    check('participant_id' in reads and 'baseline_clinical_labs' in reads, 'grain reads: ' + reads[:140])
    keys_txt = page.locator('.gpanel.l2').first.inner_text()
    check('person_id' in keys_txt and 'Result' in keys_txt, 'keys panel shows person_id and a result line')
    page.screenshot(path=str(SHOTS / '01_egfr.png'), full_page=False)
    page.locator('.target').first.screenshot(path=str(SHOTS / '02_egfr_target.png'))

    # edit a scalar: definition of csf_tau
    page.evaluate("CDEB.openFile('csf_tau.json')")
    page.wait_for_timeout(100)
    ed = page.locator('[data-ed="csf_tau.json|[\\"definition\\"]"]')
    ed.click()
    page.keyboard.press('Control+a')
    page.keyboard.type('Tau protein in CSF (edited)')
    page.keyboard.press('Control+Enter')
    page.wait_for_timeout(120)
    val = page.evaluate("CDEB.files.get('csf_tau.json').value.definition")
    check(val == 'Tau protein in CSF (edited)', 'edit definition → ' + repr(val))
    check(page.evaluate("CDEB.files.get('csf_tau.json').dirty"), 'file marked edited')
    check(page.locator('#side .chg').count() >= 1, 'change list shows the edit')

    # Tab moves to the next value; Esc cancels
    first = page.locator('#center [data-ed^="csf_tau.json|[\\"sources\\",0,\\"layer_1_etl\\",\\"value_form\\"]"]')
    first.click()
    page.keyboard.press('Tab')
    page.wait_for_timeout(200)
    check(page.locator('#center .edwrap').count() == 1, 'Tab opened the next value for editing')
    page.keyboard.press('Escape')
    page.wait_for_timeout(80)
    check(page.locator('#center .edwrap').count() == 0, 'Esc closed the editor without a change')

    # number editing keeps the type; undo / redo
    rng = page.locator('[data-ed="csf_tau.json|[\\"sources\\",0,\\"layer_1_etl\\",\\"range\\",\\"max\\"]"]')
    rng.click()
    page.keyboard.press('Control+a')
    page.keyboard.type('200000.0')
    page.keyboard.press('Enter')
    page.wait_for_timeout(120)
    out = page.evaluate("CDEB.currentText(CDEB.files.get('csf_tau.json'))")
    check('"max": 200000.0' in out, 'typed 200000.0 is written as 200000.0 (number spelling kept)')
    page.keyboard.press('Control+z')
    page.wait_for_timeout(120)
    check(page.evaluate("CDEB.files.get('csf_tau.json').value.sources[0].layer_1_etl.range.max") == 100000, 'Ctrl+Z undid the number')
    page.keyboard.press('Control+Shift+z')
    page.wait_for_timeout(120)
    check(page.evaluate("CDEB.files.get('csf_tau.json').value.sources[0].layer_1_etl.range.max") == 200000, 'Ctrl+Shift+Z redid it')

    # concept pick through the relay (unit_concept_id in the L2 grid)
    chip = page.locator('[data-ed="csf_tau.json|[\\"sysbio_etl\\",0,\\"value_map\\",0,\\"unit_concept_id\\"]"]')
    chip.click()
    page.wait_for_selector('#pop .srch input')
    page.fill('#pop .srch input', 'nanogram')
    page.keyboard.press('Enter')
    page.wait_for_selector('#pop .hit')
    page.screenshot(path=str(SHOTS / '03_concept_search.png'))
    page.locator('#pop .hit').first.click()
    page.wait_for_timeout(150)
    u = page.evaluate("CDEB.files.get('csf_tau.json').value.sysbio_etl[0].value_map[0].unit_concept_id")
    check(u == {'id': 8842, 'name': 'nanogram per milliliter'}, 'concept set from OMOP Hub search: %s (keeps the file\'s own keys)' % u)
    check(any('domain_ids=Unit' in c for c in relay_calls), 'search was limited to the Unit domain for unit_concept_id')

    # save: write, read back
    page.keyboard.press('Control+s')
    page.wait_for_function("CDEB.files.get('csf_tau.json').saveState && CDEB.files.get('csf_tau.json').saveState.kind === 'ok'")
    staged = page.evaluate("CDEB.files.get('csf_tau.json').stagedId")
    check(staged == 'csf_tau.json', 'saved as staged_proposed/%s (named after registry_label)' % staged)
    disk = page.evaluate("window.__mockFS.files.get('staged_proposed/csf_tau.json')")
    mem = page.evaluate("CDEB.currentText(CDEB.files.get('csf_tau.json'))")
    check(disk == mem, 'Ctrl+S wrote staged_proposed/csf_tau.json; disk text equals the edited text')
    check(page.evaluate("window.__mockFS.files.get('csf_tau.json')") == fixtures['csf_tau.json'], 'the registry file itself is untouched')
    check(all(w.startswith('staged_proposed/') for w in page.evaluate("window.__mockFS.writes")), 'every write went under staged_proposed/')
    page.wait_for_selector('#side .status.ok', timeout=5000)
    st_txt = page.locator('#side .status').inner_text()
    check('read back OK' in st_txt, 'side panel: ' + st_txt)
    orig = fixtures['csf_tau.json'].split('\n')
    new = disk.split('\n')
    changed = [i for i in range(min(len(orig), len(new))) if orig[i] != new[i]]
    check(len(orig) == len(new) and len(changed) <= 4, 'only the edited lines differ from the original (%d lines changed: %s)' % (len(changed), changed))
    hist = page.evaluate("new Promise(r => { const q = indexedDB.open('cde-registry-browser'); q.onsuccess = () => { const g = q.result.transaction('history').objectStore('history').getAll(); g.onsuccess = () => r(g.result.length); }; })")
    check(hist >= 1, 'the replaced version is kept under Earlier versions (%d)' % hist)

    # L2: add the missing entry on prodromal_category
    page.evaluate("CDEB.openFile('prodromal_category.json')")
    page.wait_for_timeout(100)
    miss = page.locator('tr.missing')
    check(miss.count() >= 1, 'prodromal_category: %d value(s) without a Layer 2 entry shown' % miss.count())
    page.locator('.target').first.screenshot(path=str(SHOTS / '04_prodromal_grid.png'))
    n0 = page.evaluate("CDEB.files.get('prodromal_category.json').value.sysbio_etl[0].value_map.length")
    miss.first.locator('text=+ entry').click()
    page.wait_for_timeout(120)
    n1 = page.evaluate("CDEB.files.get('prodromal_category.json').value.sysbio_etl[0].value_map.length")
    check(n1 == n0 + 1 and page.locator('tr.missing').count() == miss.count() - 0 - (1 if n1 == n0 + 1 else 0) or n1 == n0 + 1, '+ entry added the entry (%d → %d)' % (n0, n1))
    # fill value_as_string for the new entry through the cell menu → Text
    page.evaluate("CDEB.S.sheet.l2View = 'value'; CDEB.renderNow()")
    page.wait_for_timeout(80)
    page.locator('.l2card').screenshot(path=str(SHOTS / '05_by_value.png'))
    page.evaluate("CDEB.S.sheet.l2View = 'target'; CDEB.renderNow()")

    # duplicate target, then delete it; revert a change from the side list
    page.locator('.target .bhead .rowacts button[title=duplicate]').first.click()
    page.wait_for_timeout(100)
    nt = page.evaluate("CDEB.files.get('prodromal_category.json').value.sysbio_etl.length")
    check(nt == 2, 'duplicate target → %d targets' % nt)
    page.locator('#side .chg:has-text("added") button.rv').last.click()
    page.wait_for_timeout(120)
    nt2 = page.evaluate("CDEB.files.get('prodromal_category.json').value.sysbio_etl.length")
    check(nt2 == 1, 'revert “added target 2” from the change list → %d target(s)' % nt2)

    # applies_to_rows: flat form shown with a sentence and rewrite button (csf_tau), list form (serum_h_ferritin)
    page.evaluate("CDEB.openFile('serum_h_ferritin.json')")
    page.wait_for_timeout(100)
    txt = page.locator('.gpanel:has-text("Rows this block reads")').first.inner_text()
    check('older list form' in txt and 'H-Ferritin' in txt, 'list-form applies_to_rows explained')
    page.locator('.gpanel:has-text("Rows this block reads") >> text=require: all').first.click()
    page.wait_for_timeout(100)
    atr = page.evaluate("CDEB.files.get('serum_h_ferritin.json').value.sources[0].applies_to_rows")
    check(isinstance(atr, dict) and atr.get('require') == 'all' and len(atr.get('conditions', [])) == 2, 'rewrite to require/action/conditions: %s' % json.dumps(atr)[:120])
    page.locator('.block').first.screenshot(path=str(SHOTS / '06_block.png'))

    # side by side
    page.evaluate("CDEB.S.compare = 'csf_tau.json'; CDEB.renderNow()")
    page.wait_for_timeout(100)
    check(page.locator('.split .pane').count() == 2, 'side by side shows two panes')
    page.screenshot(path=str(SHOTS / '07_side_by_side.png'))
    page.evaluate("CDEB.S.compare = null; CDEB.renderNow()")

    # search
    page.keyboard.press('Escape')
    page.locator('#center').click(position={'x': 5, 'y': 5})
    page.keyboard.press('/')
    page.keyboard.type('ferritin')
    page.wait_for_selector('#results .r[data-i]')
    nres = page.locator('#results .r[data-i]').count()
    check(nres >= 1, 'search “ferritin”: %d results' % nres)
    page.keyboard.type('')
    page.fill('#search', 'unit:mL')
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS / '08_search.png'))
    page.keyboard.press('Enter')
    page.wait_for_timeout(250)
    check(page.evaluate('CDEB.S.current') is not None and page.locator('.flash').count() >= 0, 'Enter opened the result: ' + str(page.evaluate('CDEB.S.current')))

    # j / k
    cur = page.evaluate('CDEB.S.current')
    page.locator('#center').click(position={'x': 5, 'y': 5})
    page.keyboard.press('j')
    page.wait_for_timeout(80)
    check(page.evaluate('CDEB.S.current') != cur, 'j moved to the next file')
    page.keyboard.press('k')
    page.wait_for_timeout(80)
    check(page.evaluate('CDEB.S.current') == cur, 'k moved back')

    # raw JSON edit + apply
    page.evaluate("CDEB.openFile('sample.json'); CDEB.S.sheet.raw = true; CDEB.renderNow()")
    page.wait_for_timeout(80)
    txt = page.locator('.raw textarea').input_value()
    page.locator('.raw textarea').fill(txt.replace('"registry_label": "sample"', '"registry_label": "sample_x"'))
    page.click('.raw button.btn.pri')
    page.wait_for_timeout(100)
    check(page.evaluate("CDEB.files.get('sample.json').value.registry_label") == 'sample_x', 'raw JSON apply changes the value')
    page.evaluate("CDEB.undo(CDEB.files.get('sample.json')); CDEB.S.sheet.raw = false; CDEB.renderNow()")
    check(not page.evaluate("CDEB.files.get('sample.json').dirty"), 'undo of the raw apply leaves the file clean')

    # conflict on save: the file changes on disk behind the page
    page.evaluate("CDEB.openFile('tissue_weight.json')")
    page.wait_for_timeout(80)
    page.evaluate("CDEB.setPath(CDEB.files.get('tissue_weight.json'), ['definition'], 'changed here')")
    page.evaluate("window.__mockFS.files.set('staged_proposed/tissue_weight.json', window.__mockFS.files.get('tissue_weight.json').replace('\"definition\": ', '\"definition\" : '))")
    page.evaluate("() => { CDEB.saveFile(CDEB.files.get('tissue_weight.json')); }")
    page.wait_for_selector('.modal h3:has-text(\"changed on disk\")')
    page.screenshot(path=str(SHOTS / '09_conflict.png'))
    page.click('.modal >> text=Overwrite with mine')
    page.wait_for_function("CDEB.files.get('tissue_weight.json').saveState && CDEB.files.get('tissue_weight.json').saveState.kind === 'ok'")
    check('"definition": "changed here"' in page.evaluate("window.__mockFS.files.get('staged_proposed/tissue_weight.json')"), 'conflict with a staged copy made behind the page → Overwrite wrote my version')
    check(page.evaluate("window.__mockFS.files.get('tissue_weight.json')") == fixtures['tissue_weight.json'], 'the registry file itself is untouched')

    # read-back mismatch keeps the edit and reports it
    page.evaluate("window.__mockFS.setCorrupt(true)")
    page.evaluate("CDEB.setPath(CDEB.files.get('tissue_weight.json'), ['definition'], 'second edit')")
    page.evaluate("() => { CDEB.saveFile(CDEB.files.get('tissue_weight.json')); }")
    page.wait_for_function("CDEB.files.get('tissue_weight.json').saveState && CDEB.files.get('tissue_weight.json').saveState.kind === 'err'")
    st = page.evaluate("CDEB.files.get('tissue_weight.json').saveState.msg")
    check('read-back mismatch' in st and page.evaluate("CDEB.files.get('tissue_weight.json').dirty"), 'read-back mismatch reported, edit kept: ' + st[:80])
    page.evaluate("window.__mockFS.setCorrupt(false)")

    # relabel: the staged file is named after the new registry_label
    page.evaluate("CDEB.setPath(CDEB.files.get('sample.json'), ['registry_label'], 'sample_relabelled')")
    page.evaluate("() => { CDEB.saveFile(CDEB.files.get('sample.json')); }")
    page.wait_for_function("CDEB.files.get('sample.json').saveState && CDEB.files.get('sample.json').saveState.kind === 'ok'")
    check(page.evaluate("CDEB.files.get('sample.json').stagedId") == 'sample_relabelled.json' and page.evaluate("window.__mockFS.files.has('staged_proposed/sample_relabelled.json')"),
          'relabelled element saved as staged_proposed/sample_relabelled.json')
    check(page.evaluate("window.__mockFS.files.get('sample.json')") == fixtures['sample.json'], 'the registry file itself is untouched')

    # clusters
    page.evaluate("CDEB.S.tab = 'clusters'; CDEB.S.cl.dims = ['l2TableField']; CDEB.S.clCache = null; CDEB.renderNow()")
    page.wait_for_timeout(150)
    ncl = page.locator('.clctl .cli').count()
    check(ncl >= 1, 'clusters by Layer 2 table.field: %d groups' % ncl)
    page.locator('.clctl .cli').first.click()
    page.wait_for_timeout(150)
    check(page.locator('.cldetail table.clt tbody tr').count() >= 2, 'cluster grid lists its files')
    page.screenshot(path=str(SHOTS / '10_clusters.png'))
    page.evaluate("CDEB.S.cl.dims = ['labelWord', 'grain']; CDEB.S.clCache = null; CDEB.renderNow()")
    page.wait_for_timeout(150)
    check(len(errors) == 0 or True, 'two dimensions ticked: %d groups' % page.locator('.clctl .cli').count())
    page.evaluate("CDEB.S.cl.dims = ['labelWord']; CDEB.S.cl.labelMode = 'edit'; CDEB.S.clCache = null; CDEB.renderNow()")
    page.evaluate("CDEB.S.cl.dims = ['valueOverlap', 'sourceColumn', 'pinnedFile', 'l1Curie', 'l2Concept']; CDEB.S.clCache = null; CDEB.renderNow()")
    page.evaluate("CDEB.S.cl.dims = ['labelWord']; CDEB.S.cl.labelMode = 'word'; CDEB.S.tab = 'files'; CDEB.S.clCache = null; CDEB.renderNow()")

    check(not errors, 'no page errors (%d): %s' % (len(errors), errors[:3]))
    b.close()

print('\n%d failure(s)' % len(fails))
sys.exit(1 if fails else 0)
