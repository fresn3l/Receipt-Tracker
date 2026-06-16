from sqlalchemy import inspect, text

from backend.database import engine


def run_migrations() -> None:
    inspector = inspect(engine)
    if "receipts" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("receipts")}
        if "image_hash" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE receipts ADD COLUMN image_hash VARCHAR(64)"))

    if "product_aliases" not in inspector.get_table_names():
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
