# Receipt Tracker

Personal, local grocery receipt tracker. Upload receipt photos, extract line items with a vision LLM, and track prices over time.

## Sprint 1 features

- Upload receipt images (JPG, PNG, WEBP)
- Parse store, date, total, and line items via OpenAI vision
- Store receipts and items in local SQLite
- View receipt history and item details
- Click an item to see its price history chart

## Sprint 2 features

- Edit receipt metadata (store, date, total)
- Edit, add, and delete line items (single-row or bulk edit mode)
- Auto-calc line totals from qty × unit price while editing
- Re-parse a receipt from the saved image
- Delete receipts (including image files)
- Validation warnings when line items don't match receipt total

## Sprint 3 features

- **Price Tracker** tab — browse and search all tracked groceries
- Per-product analytics: latest, average, min/max, buy frequency
- Price-over-time chart with average benchmark line
- Rate-of-change table between consecutive purchases
- Purchase history with links back to source receipts

## Sprint 4 features

- **Merge products** — combine duplicate grocery items across receipts
- **Product aliases** — receipt text maps to canonical products after merge
- **Merge suggestions** — fuzzy name matching + optional AI suggestions
- **Duplicate receipt detection** — blocks identical images; warns on same store/date/total
- **Orphan cleanup** — removes unused products after deletes/merges

## Sprint 5 features

- **Auto-categorize** items during receipt parsing (Produce, Dairy, etc.)
- **Manual category edit** on product detail
- **Spending tab** — total spent, avg trip, items per trip
- Charts: spend by category, by store, monthly trend

## Sprint 6 features

- **Watchlist** — pin products and see them in the Price Tracker sidebar
- **Price alerts** — flags items up 10%+ or at highest recorded price
- **Cross-store comparison** — per-product store price table
- **Inflation basket** — weighted average % change across your tracked items
- **Unit normalization** — parser extracts unit size; shows price per oz/lb/each

## Sprint 7 features

- **Batch upload** — select multiple receipt photos at once
- **Review queue** — filter receipts needing attention (low confidence, bad totals, duplicates)
- **Parse confidence** — per-line and per-receipt scores from the vision model
- **Image preprocessing** — auto-rotate and boost contrast before parsing
- **Export** — CSV and JSON backup endpoints
- **Tests** — core analytics, validation, and store normalization

## Sprint 8 features

- **Monthly budget** — set a target and see remaining spend this month
- **Store normalization** — chains like "TRADER JOE'S #123" → Trader Joe's
- **Receipt notes** — tag trips ("stock-up", "party", etc.)
- **PWA** — installable web app with service worker for offline shell

## Phase A — Trust the data

- **Mark reviewed** — clear receipts from the review queue after you've verified them
- **Bulk re-parse** — backfill categories and unit data across many receipts (missing categories or all)
- **Product unit size** — edit package size and toggle per-unit price charts
- **Import JSON** — restore from an exported backup (merge or replace)

## Phase B — Harden

- **Route modules** — API split into `backend/routes/` (receipts, products, spending, etc.)
- **Integration tests** — API tests with isolated temp SQLite DB
- **GitHub Actions CI** — runs `pytest` on push/PR to `main`
- **Health check** — `GET /api/health` reports status and whether `OPENAI_API_KEY` is set
- **Startup warning** — logs a clear message if the API key is missing

## Setup

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Copy the environment file and add your OpenAI API key:

```bash
cp .env.example .env
```

3. Start the server:

```bash
uvicorn backend.main:app --reload
```

4. Open [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Data storage

- SQLite database: `data/receipts.db`
- Receipt images: `data/receipts/`

Both are gitignored and stay on your machine.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | App status and API key check |
| POST | `/api/receipts/upload` | Upload and parse a receipt image |
| POST | `/api/receipts/upload/batch` | Upload multiple receipt images |
| GET | `/api/receipts` | List all receipts (`?review_only=true`) |
| GET | `/api/receipts/review-queue` | Receipts needing review |
| GET | `/api/receipts/{id}` | Receipt detail with line items |
| PATCH | `/api/receipts/{id}` | Update receipt metadata and notes |
| DELETE | `/api/receipts/{id}` | Delete receipt and image |
| POST | `/api/receipts/{id}/reparse` | Re-parse from saved image |
| GET | `/api/products/watchlist` | Watched products |
| GET | `/api/insights/alerts` | Price increase alerts |
| GET | `/api/insights/inflation-basket` | Basket inflation metric |
| GET | `/api/spending/overview` | Spending summary and chart data |
| GET/PATCH | `/api/settings/budget` | Monthly budget settings |
| POST | `/api/receipts/{id}/mark-reviewed` | Mark receipt as reviewed |
| POST | `/api/receipts/reparse/batch` | Bulk re-parse receipts |
| GET | `/api/receipts/reparse-candidates` | Receipts eligible for re-parse |
| POST | `/api/import/json/file` | Import JSON backup file |
| GET | `/api/export/csv` | Export line items as CSV |

## Tests

```bash
pytest tests/ -q
```

Unit tests cover analytics, validation, and store normalization. Integration tests (`tests/test_api.py`) exercise the HTTP API against an isolated temp database.

## Next steps

- Category-level budgets in the UI
- Price alert thresholds (customizable)
- Cheapest-store dashboard for watched items
- Mobile layout pass
