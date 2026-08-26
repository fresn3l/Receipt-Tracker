# Finance App

Unified **macOS** desktop app combining:

- **Banking** — CSV bank-statement import, categorization, budgets, recurring detection (from finance-tracker)
- **Receipts** — grocery receipt photo parsing, price history, spending (from Receipt-Tracker)

One window, one local data directory. No cloud sync required.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
finance-app --browser          # dev: system browser
finance-app                    # native pywebview window
finance-app --no-window        # API only
```

Open http://127.0.0.1:&lt;port&gt;/ (printed in the log).

## Data

Default locations:

| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/FinanceApp/` |
| Linux / other | `~/.finance-app/` |

Override with `FINANCE_APP_DATA_DIR`.

Layout:

- `bank/` — JSON transactions, categories, budgets (migrated from `~/.finance-tracker` on first launch)
- `receipts.db` + `receipts/images/` — SQLite + receipt photos
- `settings.json` — OpenAI key / model for receipt parsing

## Architecture

- FastAPI server (`app/server.py`) mounts `/api/bank/*` and existing receipt `/api/*` routes
- Static shell at `/` with Banking and Receipts iframes
- `finance-app` launches uvicorn on localhost and opens pywebview

## Packaging

See [packaging/macos/README.md](packaging/macos/README.md) for PyInstaller `.app` builds.

## Tests

```bash
pytest tests/ -q
```

## Source lineage

Merged from [Receipt-Tracker](https://github.com/fresn3l/Receipt-Tracker) and [finance-tracker](https://github.com/fresn3l/finance-tracker). Legacy repos remain archives.
