"""Tests for the gripr MCP tool functions against a mocked gripr API -- no live backend needed.

httpx.Client is monkeypatched process-wide for the duration of each test to route through an
httpx.MockTransport, which is the cleanest way to intercept calls made by server.py's `_get`/
`_post` helpers without threading a client through every function signature.
"""

import httpx
import pytest

import server as gripr_mcp


def use_mock_transport(monkeypatch, handler):
    real_client = httpx.Client  # captured before patching, so the factory below doesn't recurse

    def client_factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)


def test_list_accounts_narrows_to_the_fields_a_caller_needs(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/gripr/accounts"
        assert request.url.params["include_archived"] == "false"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 4,
                    "name": "ING",
                    "type": "checking",
                    "balance_mode": "transactional",
                    "opening_balance": "0",
                    "manual_balance": "0",
                    "is_archived": False,
                    "balance": "610.59",
                }
            ],
        )

    use_mock_transport(monkeypatch, handler)
    assert gripr_mcp.list_accounts() == [
        {"id": 4, "name": "ING", "type": "checking", "balance": "610.59"}
    ]


def test_list_categories_narrows_to_the_fields_a_caller_needs(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/gripr/categories"
        return httpx.Response(
            200,
            json=[{"id": 12, "name": "Boodschappen", "kind": "expense", "parent_id": None, "is_archived": False}],
        )

    use_mock_transport(monkeypatch, handler)
    assert gripr_mcp.list_categories() == [{"id": 12, "name": "Boodschappen", "kind": "expense", "parent_id": None}]


def test_add_transaction_posts_an_expense_with_no_counter_account(monkeypatch):
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(__import__("json").loads(request.content))
        return httpx.Response(200, json={"id": 1, **sent})

    use_mock_transport(monkeypatch, handler)
    gripr_mcp.add_transaction(
        date="2026-09-12", transaction_type="expense", account_id=4, amount="5.59", category_id=12
    )

    assert sent == {
        "date": "2026-09-12",
        "type": "expense",
        "account_id": 4,
        "amount": "5.59",
        "category_id": 12,
        "counter_account_id": None,
        "notes": None,
    }


def test_add_transaction_posts_a_transfer_with_no_category(monkeypatch):
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(__import__("json").loads(request.content))
        return httpx.Response(200, json={"id": 2, **sent})

    use_mock_transport(monkeypatch, handler)
    gripr_mcp.add_transaction(
        date="2026-09-12",
        transaction_type="transfer",
        account_id=4,
        amount="100",
        category_id=999,  # deliberately wrong -- must be dropped, not sent
        counter_account_id=7,
    )

    assert sent["type"] == "transfer"
    assert sent["category_id"] is None
    assert sent["counter_account_id"] == 7


def test_add_transaction_posts_a_refund_under_its_expense_category(monkeypatch):
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.update(__import__("json").loads(request.content))
        return httpx.Response(200, json={"id": 3, **sent})

    use_mock_transport(monkeypatch, handler)
    gripr_mcp.add_transaction(
        date="2026-09-30", transaction_type="refund", account_id=4, amount="30", category_id=12,
        counter_account_id=7,  # meaningless for a refund -- must be dropped, not sent
    )

    assert sent["type"] == "refund"
    assert sent["category_id"] == 12
    assert sent["counter_account_id"] is None


@pytest.mark.parametrize(
    "kwargs, message_fragment",
    [
        ({"transaction_type": "withdrawal"}, "transaction_type must be"),
        ({"amount": "not-a-number"}, "not a valid decimal"),
        ({"amount": "0"}, "positive number"),
        ({"amount": "-5"}, "positive number"),
        ({"category_id": None}, "category_id is required"),
    ],
)
def test_add_transaction_validates_before_calling_the_api(monkeypatch, kwargs, message_fragment):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should never reach the API when input is invalid")

    use_mock_transport(monkeypatch, handler)
    base = dict(date="2026-09-12", transaction_type="expense", account_id=4, amount="5.59", category_id=12)
    base.update(kwargs)

    with pytest.raises(ValueError, match=message_fragment):
        gripr_mcp.add_transaction(**base)


def test_add_transaction_requires_a_counter_account_for_transfers(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should never reach the API when input is invalid")

    use_mock_transport(monkeypatch, handler)
    with pytest.raises(ValueError, match="counter_account_id is required"):
        gripr_mcp.add_transaction(date="2026-09-12", transaction_type="transfer", account_id=4, amount="100")


def test_add_transaction_surfaces_the_apis_error_detail(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Account not found"})

    use_mock_transport(monkeypatch, handler)
    with pytest.raises(ValueError, match="Account not found"):
        gripr_mcp.add_transaction(
            date="2026-09-12", transaction_type="expense", account_id=999, amount="5.59", category_id=12
        )
