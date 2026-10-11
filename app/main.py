import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Item, Loan

app = FastAPI(title="Loan Desk", version="1.0.0")
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
logger = logging.getLogger("loan-desk")
Database = Annotated[Session, Depends(get_session)]


class NewItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=60)
    total: int = Field(strict=True, ge=1, le=100)


class NewLoan(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    item_id: int = Field(strict=True, ge=1)
    borrower: str = Field(min_length=1, max_length=40)


def item_view(item: Item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "total": item.total,
        "available": item.available,
        "on_loan": item.total - item.available,
    }


def loan_view(loan: Loan, item_name: str) -> dict:
    return {
        "id": loan.id,
        "item_id": loan.item_id,
        "item_name": item_name,
        "borrower": loan.borrower,
        "borrowed_at": loan.borrowed_at.isoformat(),
        "returned_at": loan.returned_at.isoformat() if loan.returned_at else None,
    }


@app.exception_handler(SQLAlchemyError)
def database_failure(_request: Request, _error: SQLAlchemyError) -> JSONResponse:
    # Never put DB connection strings or driver errors into the response or logs.
    logger.warning("database_request_failed")
    return JSONResponse(
        status_code=503, content={"detail": "DB 연결 또는 초기화 상태를 확인해 주세요."}
    )


@app.get("/")
def home() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/healthz")
def health(session: Database) -> dict:
    # Requires both a reachable DB and initialized tables, not merely a running HTTP server.
    session.scalar(select(Item.id).limit(1))
    session.scalar(select(Loan.id).limit(1))
    return {"status": "ok", "service": "loan-desk", "database": "ready"}


@app.get("/api/items")
def items(session: Database) -> list[dict]:
    return [item_view(item) for item in session.scalars(select(Item).order_by(Item.id))]


@app.post("/api/items", status_code=201)
def create_item(body: NewItem, session: Database) -> dict:
    try:
        with session.begin():
            item = Item(name=body.name, total=body.total, available=body.total)
            session.add(item)
            session.flush()
            result = item_view(item)
    except IntegrityError:
        raise HTTPException(409, "같은 이름의 물품이 이미 등록되어 있어요.") from None
    return result


@app.get("/api/loans")
def loans(session: Database) -> list[dict]:
    rows = session.execute(select(Loan, Item.name).join(Item).order_by(Loan.id.desc()).limit(200))
    return [loan_view(loan, name) for loan, name in rows]


@app.post("/api/loans", status_code=201)
def borrow(body: NewLoan, session: Database) -> dict:
    with session.begin():
        item = session.scalar(select(Item).where(Item.id == body.item_id).with_for_update())
        if item is None:
            raise HTTPException(404, "물품을 찾지 못했어요.")
        if item.available == 0:
            raise HTTPException(409, "모두 대여 중이에요. 반납 후 다시 시도해 주세요.")
        item.available -= 1
        loan = Loan(item_id=item.id, borrower=body.borrower, borrowed_at=datetime.now(UTC))
        session.add(loan)
        session.flush()
        result = loan_view(loan, item.name)
    return result


@app.post("/api/loans/{loan_id}/return")
def return_item(loan_id: int, session: Database) -> dict:
    with session.begin():
        loan = session.scalar(select(Loan).where(Loan.id == loan_id).with_for_update())
        if loan is None:
            raise HTTPException(404, "대여 기록을 찾지 못했어요.")
        if loan.returned_at is not None:
            raise HTTPException(409, "이미 반납한 물품이에요.")
        item = session.scalar(select(Item).where(Item.id == loan.item_id).with_for_update())
        item.available += 1
        loan.returned_at = datetime.now(UTC)
        result = loan_view(loan, item.name)
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
