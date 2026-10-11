from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "loan_items"
    __table_args__ = (
        CheckConstraint("total >= 1", name="item_total_positive"),
        CheckConstraint("available >= 0 AND available <= total", name="item_stock_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    total: Mapped[int]
    available: Mapped[int]


class Loan(Base):
    __tablename__ = "item_loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("loan_items.id"), index=True)
    borrower: Mapped[str] = mapped_column(String(40))
    borrowed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
