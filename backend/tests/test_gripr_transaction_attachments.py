"""Attachments on a gripr transaction (docs/adr/0035). The type/size/filename rules are shared with
gainr's and tested in test_transaction_attachments.py; this covers gripr's own endpoints."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.gripr_account import GriprAccount, GriprAccountType, GriprBalanceMode
from app.models.gripr_transaction import GriprTransactionType
from app.models.gripr_transaction_attachment import GriprTransactionAttachment
from app.repositories import gripr_transaction_repo
from app.routers import gripr as gripr_router
from app.services import gripr_transaction_service
from app.services import transaction_attachment_service as service

PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(gripr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def make_txn(db) -> int:
    account = GriprAccount(name="Checking", type=GriprAccountType.CHECKING, balance_mode=GriprBalanceMode.TRANSACTIONAL)
    db.add(account)
    db.flush()
    txn = gripr_transaction_service.create_transaction(
        db, date=date(2024, 1, 1), type=GriprTransactionType.EXPENSE, amount=Decimal("12.50"), account_id=account.id
    )
    db.commit()
    return txn.id


@pytest.fixture()
def txn_id(db_session) -> int:
    return make_txn(db_session)


def upload(client, txn_id, content=PDF, filename="invoice.pdf", content_type="application/pdf"):
    return client.post(
        f"/api/gripr/transactions/{txn_id}/attachments", files={"file": (filename, content, content_type)}
    )


def test_upload_then_list_and_download(client, txn_id):
    created = upload(client, txn_id)

    assert created.status_code == 201
    body = created.json()
    assert (body["filename"], body["content_type"], body["size_bytes"]) == ("invoice.pdf", "application/pdf", len(PDF))
    assert "content" not in body
    assert [a["id"] for a in client.get(f"/api/gripr/transactions/{txn_id}/attachments").json()] == [body["id"]]

    download = client.get(f"/api/gripr/transactions/{txn_id}/attachments/{body['id']}")
    assert download.status_code == 200
    assert download.content == PDF
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-disposition"] == "inline; filename*=UTF-8''invoice.pdf"


def test_the_type_comes_from_the_bytes_and_html_is_refused(client, txn_id):
    assert upload(client, txn_id, content=PNG, filename="scan.pdf").json()["content_type"] == "image/png"

    refused = upload(client, txn_id, content=b"<html>hi</html>", filename="x.pdf")

    assert refused.status_code == 415


def test_the_limits_apply(client, txn_id, monkeypatch):
    monkeypatch.setattr(service, "MAX_ATTACHMENT_BYTES", 100)
    assert upload(client, txn_id, content=PDF + b"\x00" * 100).status_code == 413
    monkeypatch.setattr(service, "MAX_ATTACHMENT_BYTES", 10 * 1024 * 1024)
    monkeypatch.setattr(service, "MAX_ATTACHMENTS_PER_TRANSACTION", 1)
    assert upload(client, txn_id).status_code == 201

    assert upload(client, txn_id).status_code == 409


def test_unknown_transaction_is_a_404(client):
    assert upload(client, 999).status_code == 404
    assert client.get("/api/gripr/transactions/999/attachments").status_code == 404


def test_an_attachment_is_only_served_under_its_own_transaction(client, db_session, txn_id):
    other = gripr_transaction_service.create_transaction(
        db_session, date=date(2024, 1, 2), type=GriprTransactionType.EXPENSE, amount=Decimal(5),
        account_id=gripr_transaction_repo.get_transaction(db_session, txn_id).account_id,
    )
    db_session.commit()
    created = upload(client, txn_id).json()

    assert client.get(f"/api/gripr/transactions/{other.id}/attachments/{created['id']}").status_code == 404
    assert client.delete(f"/api/gripr/transactions/{other.id}/attachments/{created['id']}").status_code == 404


def test_delete_removes_the_attachment(client, txn_id):
    created = upload(client, txn_id).json()

    assert client.delete(f"/api/gripr/transactions/{txn_id}/attachments/{created['id']}").status_code == 204
    assert client.get(f"/api/gripr/transactions/{txn_id}/attachments/{created['id']}").status_code == 404


def test_the_transaction_list_and_a_single_transaction_report_the_count(client, txn_id):
    upload(client, txn_id)
    upload(client, txn_id, content=PNG, filename="a.png")

    items = client.get("/api/gripr/transactions").json()["items"]
    edited = client.put(f"/api/gripr/transactions/{txn_id}", json={"notes": "hello"}).json()

    assert [(i["id"], i["attachment_count"]) for i in items] == [(txn_id, 2)]
    assert edited["attachment_count"] == 2


def test_deleting_a_transaction_deletes_its_files(client, db_session, txn_id):
    upload(client, txn_id)

    assert client.delete(f"/api/gripr/transactions/{txn_id}").status_code == 204

    assert db_session.query(GriprTransactionAttachment).count() == 0
