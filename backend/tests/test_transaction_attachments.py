from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.transaction import Transaction, TransactionType
from app.models.transaction_attachment import TransactionAttachment
from app.repositories import transaction_repo
from app.routers import transactions as transactions_router
from app.services import transaction_attachment_service as service

PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 "


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(transactions_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture()
def txn_id(db_session, portfolio_id) -> int:
    txn = Transaction(portfolio_id=portfolio_id, date=date(2024, 1, 1), type=TransactionType.DEPOSIT, total_eur=100)
    db_session.add(txn)
    db_session.commit()
    return txn.id


def upload(client, txn_id, content=PDF, filename="invoice.pdf", content_type="application/pdf"):
    return client.post(f"/api/transactions/{txn_id}/attachments", files={"file": (filename, content, content_type)})


# -- the rules ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("content", "expected"),
    [(PDF, "application/pdf"), (PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")],
)
def test_sniff_recognises_the_allowed_formats(content, expected):
    assert service.sniff_content_type(content) == expected


@pytest.mark.parametrize("content", [b"<html><script>alert(1)</script>", b"<svg xmlns='x'/>", b"PK\x03\x04zip", b"RIFF\x00\x00\x00\x00WAVE"])
def test_sniff_rejects_everything_else(content):
    assert service.sniff_content_type(content) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("invoice.pdf", "invoice.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\me\\Q3 invoice.pdf", "Q3 invoice.pdf"),
        ("bad\x00na\nme.pdf", "badname.pdf"),
        ("", "attachment"),
        (None, "attachment"),
        ("..", ".."),
    ],
)
def test_clean_filename(raw, expected):
    assert service.clean_filename(raw) == expected


def test_clean_filename_caps_the_length_and_keeps_the_extension():
    name = service.clean_filename("a" * 400 + ".pdf")

    assert len(name) == 255
    assert name.endswith(".pdf")


# -- the endpoints -----------------------------------------------------------------------------


def test_upload_then_list_and_download(client, txn_id):
    created = upload(client, txn_id)

    assert created.status_code == 201
    body = created.json()
    assert body["filename"] == "invoice.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF)
    assert "content" not in body

    listed = client.get(f"/api/transactions/{txn_id}/attachments").json()
    assert [a["id"] for a in listed] == [body["id"]]

    download = client.get(f"/api/transactions/{txn_id}/attachments/{body['id']}")
    assert download.status_code == 200
    assert download.content == PDF
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-disposition"] == "inline; filename*=UTF-8''invoice.pdf"


def test_the_stored_type_comes_from_the_bytes_not_the_upload(client, txn_id):
    created = upload(client, txn_id, content=PNG, filename="scan.pdf", content_type="application/pdf").json()

    assert created["content_type"] == "image/png"


def test_a_filename_is_encoded_in_the_download_header(client, txn_id):
    created = upload(client, txn_id, filename="fac;tuur é.pdf").json()

    header = client.get(f"/api/transactions/{txn_id}/attachments/{created['id']}").headers["content-disposition"]

    assert header == "inline; filename*=UTF-8''fac%3Btuur%20%C3%A9.pdf"


def test_a_disallowed_type_is_refused_even_when_labelled_as_a_pdf(client, txn_id):
    response = upload(client, txn_id, content=b"<html>hi</html>", filename="x.pdf", content_type="application/pdf")

    assert response.status_code == 415
    assert client.get(f"/api/transactions/{txn_id}/attachments").json() == []


def test_an_empty_file_is_refused(client, txn_id):
    assert upload(client, txn_id, content=b"").status_code == 400


def test_an_oversized_file_is_refused(client, txn_id, monkeypatch):
    monkeypatch.setattr(service, "MAX_ATTACHMENT_BYTES", 100)

    response = upload(client, txn_id, content=PDF + b"\x00" * 100)

    assert response.status_code == 413
    assert client.get(f"/api/transactions/{txn_id}/attachments").json() == []


def test_a_transaction_has_a_limited_number_of_attachments(client, txn_id, monkeypatch):
    monkeypatch.setattr(service, "MAX_ATTACHMENTS_PER_TRANSACTION", 2)
    assert upload(client, txn_id).status_code == 201
    assert upload(client, txn_id).status_code == 201

    assert upload(client, txn_id).status_code == 409


def test_unknown_transaction_is_a_404(client):
    assert upload(client, 999).status_code == 404
    assert client.get("/api/transactions/999/attachments").status_code == 404


def test_an_attachment_is_only_served_under_its_own_transaction(client, db_session, portfolio_id, txn_id):
    other = Transaction(portfolio_id=portfolio_id, date=date(2024, 2, 1), type=TransactionType.DEPOSIT, total_eur=5)
    db_session.add(other)
    db_session.commit()
    created = upload(client, txn_id).json()

    assert client.get(f"/api/transactions/{other.id}/attachments/{created['id']}").status_code == 404
    assert client.delete(f"/api/transactions/{other.id}/attachments/{created['id']}").status_code == 404
    assert client.get(f"/api/transactions/{txn_id}/attachments/{created['id']}").status_code == 200


def test_delete_removes_the_attachment(client, txn_id):
    created = upload(client, txn_id).json()

    assert client.delete(f"/api/transactions/{txn_id}/attachments/{created['id']}").status_code == 204
    assert client.get(f"/api/transactions/{txn_id}/attachments/{created['id']}").status_code == 404


def test_the_transaction_list_reports_how_many_files_each_has(client, db_session, portfolio_id, txn_id):
    other = Transaction(portfolio_id=portfolio_id, date=date(2024, 2, 1), type=TransactionType.DEPOSIT, total_eur=5)
    db_session.add(other)
    db_session.commit()
    upload(client, txn_id)
    upload(client, txn_id, content=PNG, filename="a.png")

    items = client.get("/api/transactions", params={"portfolio_id": portfolio_id}).json()["items"]

    counts = {item["id"]: item["attachment_count"] for item in items}
    assert counts == {txn_id: 2, other.id: 0}


def test_deleting_a_transaction_deletes_its_files(client, db_session, txn_id):
    upload(client, txn_id)

    assert client.delete(f"/api/transactions/{txn_id}").status_code == 204

    assert db_session.query(TransactionAttachment).count() == 0


def test_deleting_through_the_repo_deletes_its_files(db_session, txn_id):
    # The sync and mirror code deletes through the repo, not the endpoint.
    db_session.add(TransactionAttachment(transaction_id=txn_id, filename="a.pdf", content_type="application/pdf", size_bytes=1, content=b"x"))
    db_session.commit()

    transaction_repo.delete_transaction(db_session, transaction_repo.get_transaction(db_session, txn_id))
    db_session.commit()

    assert db_session.query(TransactionAttachment).count() == 0


def test_cash_movements_filter_keeps_everything_that_moves_cash_except_buys_and_sells(client, db_session, portfolio_id):
    kinds = [
        TransactionType.DEPOSIT,
        TransactionType.WITHDRAW,
        TransactionType.INTEREST,
        TransactionType.DIVIDEND,
        TransactionType.BROKER_FEE,
        TransactionType.TRANSFER,
        TransactionType.BUY,
        TransactionType.SELL,
        TransactionType.STAKING,
    ]
    for kind in kinds:
        db_session.add(Transaction(portfolio_id=portfolio_id, date=date(2024, 1, 1), type=kind, total_eur=1))
    db_session.commit()

    page = client.get("/api/transactions", params={"portfolio_id": portfolio_id, "cash_movements": True}).json()

    assert {t["type"] for t in page["items"]} == {"Deposit", "Withdraw", "Interest", "Dividend", "Broker Fee", "Transfer"}
    assert page["total"] == 6
