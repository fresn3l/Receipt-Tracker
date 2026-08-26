# macOS packaging notes

## Dev run (browser)

```bash
cd Finance-App   # this repo
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
finance-app --browser
# or: python -m app.main --browser
```

## Native window

```bash
finance-app
```

Uses **pywebview** against an embedded uvicorn server on `127.0.0.1`.

## Build unsigned `.app`

```bash
pip install -e ".[packaging]"
pyinstaller packaging/macos/Finance.spec
# Output: dist/Finance.app
open dist/Finance.app
```

### Smoke checklist

1. App window opens to Dashboard.
2. Settings: save an OpenAI key; data dir shows under Application Support / `~/.finance-app`.
3. Banking → Import: upload a CSV; transactions appear.
4. Receipts → upload a receipt image (requires API key); receipt lists.
5. Quit and reopen: bank JSON + receipts SQLite still present.
6. Legacy migrate: if `~/.finance-tracker` exists, bank data copies once on first launch.

### Gatekeeper / notarization

Unsigned builds need right-click → Open the first time on macOS. Notarization and Developer ID signing are out of scope for v1.
