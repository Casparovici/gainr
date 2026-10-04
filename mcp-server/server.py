"""MCP server exposing gripr (gainr's personal-finance module) actions to a chat client.

A thin wrapper around the existing FastAPI backend's REST API -- it holds no business logic
of its own and reaches the database through nothing but the same HTTP surface the gripr
frontend already uses, so there's exactly one place (the backend) that decides what a valid
transaction looks like. Point GRIPR_API_BASE at a different backend (e.g. the homecloud
deployment over Tailscale) to use this against that instance instead of a local dev server.
"""

import os
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

GRIPR_API_BASE = os.environ.get("GRIPR_API_BASE", "http://localhost:8000/api/gripr")

mcp = MCPServer(
    name="gripr",
    instructions=(
        "Tools for gainr's personal-finance module (gripr): a local, single-user expense and "
        "budget tracker. Call list_accounts and list_categories to resolve the account and "
        "category the user described in words (a bank name, \"groceries\") to the ids "
        "add_transaction needs -- never guess an id."
    ),
)

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)


def _get(path: str, **params: Any) -> Any:
    with httpx.Client(base_url=GRIPR_API_BASE, timeout=10.0) as client:
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.json()


def _post(path: str, payload: dict[str, Any]) -> Any:
    with httpx.Client(base_url=GRIPR_API_BASE, timeout=10.0) as client:
        response = client.post(path, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ValueError(f"gripr rejected this: {_error_detail(exc.response)}") from exc
        return response.json()


def _error_detail(response: httpx.Response) -> str:
    try:
        return response.json().get("detail", response.text)
    except ValueError:
        return response.text


@mcp.tool(annotations=READ_ONLY)
def list_accounts(include_archived: bool = False) -> list[dict[str, Any]]:
    """List every gripr account with its current balance and type.

    Call this before add_transaction whenever the account isn't already known from context --
    match the user's wording (a nickname, a bank name) against the `name` field here rather
    than guessing an id.
    """
    accounts = _get("/accounts", include_archived=include_archived)
    return [
        {"id": a["id"], "name": a["name"], "type": a["type"], "balance": a["balance"]}
        for a in accounts
    ]


@mcp.tool(annotations=READ_ONLY)
def list_categories() -> list[dict[str, Any]]:
    """List every gripr expense/income category, including the parent/child structure.

    Call this before add_transaction to resolve what the user described (e.g. "groceries",
    "rent", "salary") to a category id. Prefer a specific subcategory (its `parent_id` is set)
    over its parent when its own name clearly matches; fall back to the parent otherwise.
    The same name can appear more than once at different levels -- e.g. a top-level
    "Boodschappen" (groceries in general) alongside a *different* "Boodschappen" nested under
    "Vakanties" (groceries bought on a trip). When that happens, use the top-level one
    (`parent_id` is null) unless the transaction is clearly tied to that other parent's
    context. Don't invent a category that isn't in this list -- if nothing fits, ask the user
    or use that kind's "Overig" (Other) category.
    """
    categories = _get("/categories")
    return [{"id": c["id"], "name": c["name"], "kind": c["kind"], "parent_id": c["parent_id"]} for c in categories]


@mcp.tool(annotations=WRITE)
def add_transaction(
    date: str,
    transaction_type: str,
    account_id: int,
    amount: str,
    category_id: int | None = None,
    counter_account_id: int | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Record one gripr transaction and return it as saved.

    date: the calendar date it happened, as YYYY-MM-DD. Resolve relative wording ("today",
      "yesterday") to an actual date yourself before calling this -- this tool doesn't guess.
    transaction_type: "expense" (money leaves account_id into category_id), "income" (money
      enters account_id from category_id), "refund" (money comes back into account_id for
      earlier spending -- a friend paying their half, a shop refund -- filed under the
      *expense* category it lowers, not an income category), or "transfer" (money moves from
      account_id to counter_account_id, no category).
    account_id: from list_accounts. For an expense/income/refund this is the account the
      money actually moved through; for a transfer, the source account.
    amount: a positive decimal as a string, e.g. "5.59" -- always positive regardless of
      transaction_type. Direction comes from transaction_type alone, never from the sign.
    category_id: from list_categories. Required for expense/income/refund (an expense-kind
      category for a refund), omit for transfer.
    counter_account_id: from list_accounts. Required for transfer (the destination account),
      omit otherwise.
    notes: optional free-text note.
    """
    if transaction_type not in ("expense", "income", "refund", "transfer"):
        raise ValueError('transaction_type must be "expense", "income", "refund", or "transfer"')
    try:
        parsed_amount = Decimal(amount)
    except InvalidOperation as exc:
        raise ValueError(f"'{amount}' is not a valid decimal amount") from exc
    if parsed_amount <= 0:
        raise ValueError("amount must be a positive number -- direction comes from transaction_type, not the sign")
    if transaction_type == "transfer" and counter_account_id is None:
        raise ValueError("counter_account_id is required when transaction_type is 'transfer'")
    if transaction_type != "transfer" and category_id is None:
        raise ValueError(f"category_id is required when transaction_type is '{transaction_type}'")

    payload = {
        "date": date,
        "type": transaction_type,
        "account_id": account_id,
        "amount": str(parsed_amount),
        "category_id": category_id if transaction_type != "transfer" else None,
        "counter_account_id": counter_account_id if transaction_type == "transfer" else None,
        "notes": notes,
    }
    return _post("/transactions", payload)


if __name__ == "__main__":
    mcp.run()
