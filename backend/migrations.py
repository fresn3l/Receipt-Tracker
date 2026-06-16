from sqlalchemy import inspect, text

from backend.database import engine

_RECEIPT_COLUMNS = {
    "image_hash": "VARCHAR(64)",
    "notes": "TEXT",
    "parse_confidence": "FLOAT",
}


def run_migrations() -> None:
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "receipts" in tables:
        columns = {col["name"] for col in inspector.get_columns("receipts")}
        for name, col_type in _RECEIPT_COLUMNS.items():
            if name not in columns:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE receipts ADD COLUMN {name} {col_type}"))

    if "products" in tables:
        columns = {col["name"] for col in inspector.get_columns("products")}
        product_columns = {
            "is_watched": "BOOLEAN DEFAULT 0",
            "normalized_unit": "VARCHAR(20)",
            "unit_amount": "FLOAT",
        }
        for name, col_type in product_columns.items():
            if name not in columns:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE products ADD COLUMN {name} {col_type}"))

    if "line_items" in tables:
        columns = {col["name"] for col in inspector.get_columns("line_items")}
        for name, col_type in {"unit_label": "VARCHAR(50)", "parse_confidence": "FLOAT"}.items():
            if name not in columns:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE line_items ADD COLUMN {name} {col_type}"))

    if "product_aliases" not in tables:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE product_aliases (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL REFERENCES products(id),
                        alias VARCHAR(300) NOT NULL UNIQUE
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX ix_product_aliases_product_id ON product_aliases (product_id)"))

    if "app_settings" not in tables:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE app_settings (
                        id INTEGER PRIMARY KEY,
                        monthly_budget FLOAT,
                        category_budgets_json TEXT
                    )
                    """
                )
            )
            conn.execute(text("INSERT INTO app_settings (id, monthly_budget) VALUES (1, NULL)"))
