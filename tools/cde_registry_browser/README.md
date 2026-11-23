# CDE Registry browser

A page for reading, editing and auditing the mapping specifications in `registry/`, plus a
small local server (the relay) that opens the registry in it and passes concept searches to
OMOP Hub. Python standard library only; no packages to install to use it.

## Start

1. Copy `.env.example` to `.env` in this folder and put your own OMOP Hub API key in it.
   Concept search needs it; everything else works without it. `.env` is never committed.
2. From this folder run

   ```
   python cde_registry_browser_relay.py
   ```

3. Open <http://127.0.0.1:8765/> in a browser.

The page opens the repository's `registry/` folder by itself. To open another registry
folder, start the relay with `--registry PATH` (or set `CDEB_REGISTRY_DIR`). The port is
8765 unless `CDEB_RELAY_PORT` says otherwise. The relay listens on 127.0.0.1 only.

## Where saves go

The registry files are only read. Every save writes `registry/staged_proposed/<path>`:

- The staged file is named after the element's `registry_label`, so an element whose
  label was changed is staged under its new name.
- Where a staged copy exists, the staged copy is what opens; the library marks it
  **staged**. A staged file with no registry counterpart opens as its own entry.
- Each save is read back from disk and compared before it shows as saved. If the staged
  file changed on disk behind the page, the page shows the difference and asks.

Moving a staged file into `registry/` is a separate, deliberate step.

## Without the relay

Opening `cde_registry_browser.html` directly works in Chrome or Edge: pick the registry
folder with **Open folder…**. Saves still go to `staged_proposed/` inside the picked
folder. Concept search needs the relay.

## Changing the page

The page is built from `src/`:

```
node build.js        # writes cde_registry_browser.html
```

Commit the rebuilt `cde_registry_browser.html` with the source change, so the page works
without Node.

## Tests

```
node test/core_test.js          # parsing, writing and checks (Node, no packages)
python test/relay_test.py       # the relay against a temporary copy of test/fixtures
python test/ui_test.py          # the page in Chromium (needs Playwright)
```

`relay_test.py` also drives the page through the relay when Playwright is installed.
`test/fixtures/` holds copies of 16 mapping specifications from `registry/` used by the tests.
