from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from receipts.database import Base


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_name: Mapped[str | None] = mapped_column(String(200))
    purchase_date: Mapped[date | None] = mapped_column(Date)
    total: Mapped[float | None] = mapped_column(Float)
    image_path: Mapped[str] = mapped_column(String(500))
    image_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    raw_parse_json: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    parse_confidence: Mapped[float | None] = mapped_column(Float)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    line_items: Mapped[list["LineItem"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    category: Mapped[str | None] = mapped_column(String(100))
    is_watched: Mapped[bool] = mapped_column(Boolean, default=False)
    normalized_unit: Mapped[str | None] = mapped_column(String(20))
    unit_amount: Mapped[float | None] = mapped_column(Float)

    line_items: Mapped[list["LineItem"]] = relationship(back_populates="product")
    aliases: Mapped[list["ProductAlias"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductAlias(Base):
    __tablename__ = "product_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    alias: Mapped[str] = mapped_column(String(300), unique=True, index=True)

    product: Mapped["Product"] = relationship(back_populates="aliases")


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    raw_name: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    unit_price: Mapped[float | None] = mapped_column(Float)
    line_total: Mapped[float | None] = mapped_column(Float)
    unit_label: Mapped[str | None] = mapped_column(String(50))
    parse_confidence: Mapped[float | None] = mapped_column(Float)

    receipt: Mapped["Receipt"] = relationship(back_populates="line_items")
    product: Mapped["Product | None"] = relationship(back_populates="line_items")


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    monthly_budget: Mapped[float | None] = mapped_column(Float)
    category_budgets_json: Mapped[str | None] = mapped_column(Text)
