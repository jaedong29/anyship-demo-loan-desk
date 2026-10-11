"""Integration tests against a disposable, local PostgreSQL-backed app."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import httpx
import pytest

BASE = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:18086")
if urlsplit(BASE).hostname not in {"127.0.0.1", "localhost"}:
    raise RuntimeError("Use a disposable local demo server for these write tests.")


def request(method, path, **kwargs):
    return httpx.request(method, BASE + path, timeout=15, **kwargs)


def new_item(total=1, prefix="검증 물품"):
    response = request(
        "POST", "/api/items", json={"name": prefix + uuid.uuid4().hex[:10], "total": total}
    )
    assert response.status_code == 201
    return response.json()


def stock(item_id):
    return next(item for item in request("GET", "/api/items").json() if item["id"] == item_id)


def test_page_and_database_health():
    assert "빌려쓰는 사이" in request("GET", "/").text
    result = request("GET", "/healthz")
    assert result.status_code == 200
    assert result.json()["database"] == "ready"


def test_register_borrow_return_and_duplicate_guards():
    item = new_item(2)
    assert request("POST", "/api/items", json={"name": item["name"], "total": 3}).status_code == 409
    loan = request("POST", "/api/loans", json={"item_id": item["id"], "borrower": "시연 참가자"})
    assert loan.status_code == 201
    assert stock(item["id"])["available"] == 1
    returned = request("POST", f"/api/loans/{loan.json()['id']}/return")
    assert returned.status_code == 200 and returned.json()["returned_at"]
    assert request("POST", f"/api/loans/{loan.json()['id']}/return").status_code == 409
    assert stock(item["id"])["available"] == 2


@pytest.mark.parametrize(
    "body",
    [
        {"name": " ", "total": 1},
        {"name": "물품", "total": 0},
        {"name": "물품", "total": True},
        {"name": "물품", "total": "2"},
        {"name": "물품", "total": 101},
    ],
)
def test_invalid_item_inputs(body):
    assert request("POST", "/api/items", json=body).status_code == 422


def test_invalid_and_missing_loans():
    assert request("POST", "/api/loans", json={"item_id": -1, "borrower": "A"}).status_code == 422
    assert request("POST", "/api/loans", json={"item_id": 1, "borrower": " "}).status_code == 422
    assert (
        request("POST", "/api/loans", json={"item_id": 2147483647, "borrower": "A"}).status_code
        == 404
    )
    assert request("POST", "/api/loans/2147483647/return").status_code == 404


def test_only_one_concurrent_request_can_borrow_the_last_copy():
    item = new_item(1, "동시 대여 ")

    def borrow(index):
        return request(
            "POST", "/api/loans", json={"item_id": item["id"], "borrower": f"가상 참가자 {index}"}
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = list(executor.map(borrow, range(8)))
    assert sorted(response.status_code for response in responses) == [201] + [409] * 7
    assert stock(item["id"])["available"] == 0
    loan_id = next(response.json()["id"] for response in responses if response.status_code == 201)
    with ThreadPoolExecutor(max_workers=2) as executor:
        returned = list(
            executor.map(lambda _: request("POST", f"/api/loans/{loan_id}/return"), range(2))
        )
    assert sorted(response.status_code for response in returned) == [200, 409]
    assert stock(item["id"])["available"] == 1


def test_html_looking_names_are_stored_as_plain_data():
    item = new_item(prefix="<b>텍스트</b>")
    loan = request(
        "POST",
        "/api/loans",
        json={"item_id": item["id"], "borrower": "<img src=x onerror=alert(1)>"},
    )
    assert loan.status_code == 201
    assert loan.json()["borrower"] == "<img src=x onerror=alert(1)>"
    assert request("POST", f"/api/loans/{loan.json()['id']}/return").status_code == 200
