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
| POST | `/api/receipts/upload` | Upload and parse a receipt image |
| GET | `/api/receipts` | List all receipts |
| GET | `/api/receipts/{id}` | Receipt detail with line items |
| PATCH | `/api/receipts/{id}` | Update receipt metadata |
| DELETE | `/api/receipts/{id}` | Delete receipt and image |
| POST | `/api/receipts/{id}/reparse` | Re-parse from saved image |
| GET | `/api/receipts/{id}/image` | Receipt image file |
| POST | `/api/receipts/{id}/items` | Add a line item |
| PATCH | `/api/receipts/{id}/items/{item_id}` | Update a line item |
| DELETE | `/api/receipts/{id}/items/{item_id}` | Delete a line item |
| GET | `/api/products` | Products with stats (`?q=` search) |
| GET | `/api/products/merge-suggestions` | Fuzzy or AI merge suggestions |
| POST | `/api/products/merge` | Merge products into one |
| POST | `/api/products/cleanup-orphans` | Remove unused products |
| GET | `/api/products/categories` | Grocery category list |
| GET | `/api/products/{id}` | Full product detail with analytics |
| PATCH | `/api/products/{id}` | Update name or category |
| GET | `/api/products/{id}/price-history` | Price history for charts |
| GET | `/api/spending/overview` | Spending summary and chart data |

## Next steps

- Price alerts and watchlist
- Unit normalization ($/oz, $/lb)
- CSV export / backup
- Batch receipt upload
