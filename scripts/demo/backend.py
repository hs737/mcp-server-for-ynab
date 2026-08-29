"""A synthetic YNAB API, so the demo shows real tool output over invented data.

The point is honesty: every number in the GIF is produced by the actual server
code paths, not typed into a mockup. Only the budget behind them is fictional,
because the alternative is publishing someone's real finances.
"""

from __future__ import annotations

import json
import random
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

PLAN_ID = "demo-plan"
TODAY = date(2026, 8, 28)
MONTH = TODAY.replace(day=1).isoformat()

random.seed(11)


def _m(dollars: float) -> int:
    return round(dollars * 1000)


ACCOUNTS = [
    ("Everyday Checking", "checking", 4182.55, True),
    ("Emergency Savings", "savings", 11500.00, True),
    ("Travel Card", "creditCard", -842.19, True),
    ("Brokerage", "otherAsset", 23840.00, False),
]

CATEGORIES = [
    # name, budgeted, activity, balance
    ("Rent", 2150.00, -2150.00, 0.00),
    ("Groceries", 650.00, -712.40, -62.40),
    ("Dining Out", 220.00, -268.15, -48.15),
    ("Transport", 180.00, -142.30, 37.70),
    ("Utilities", 240.00, -231.88, 8.12),
    ("Subscriptions", 95.00, -89.97, 5.03),
    ("Health", 300.00, -83.34, 216.66),
]

# payee, amount, cadence days, count
RECURRING = [
    ("Nationwide Insurance", 142.00, 30, 12),
    ("Fiber Internet", 79.99, 30, 11),
    ("Mobile Plan", 65.27, 30, 9),
    ("Streaming Plus", 22.99, 30, 12),
    ("Cloud Backup", 9.99, 30, 12),
    ("Gym Membership", 48.00, 30, 8),
]

# Deliberately irregular, to show the detector declining to call it recurring.
NOISE = [("Corner Grocer", 7), ("Hardware Store", 4), ("Coffee Bar", 9)]


def _transactions() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    tid = 0

    for payee, amount, gap, count in RECURRING:
        for i in range(count):
            when = TODAY - timedelta(days=gap * (count - 1 - i))
            tid += 1
            out.append(
                {
                    "id": f"t{tid}",
                    "date": when.isoformat(),
                    "amount": -_m(amount),
                    "memo": None,
                    "cleared": "cleared",
                    "approved": True,
                    "account_id": "a1",
                    "account_name": "Everyday Checking",
                    "payee_id": f"p-{payee.lower().replace(' ', '-')}",
                    "payee_name": payee,
                    "category_id": "c6",
                    "category_name": "Subscriptions",
                    "deleted": False,
                    "subtransactions": [],
                }
            )

    for payee, count in NOISE:
        for _ in range(count):
            when = TODAY - timedelta(days=random.randint(1, 120))
            tid += 1
            out.append(
                {
                    "id": f"t{tid}",
                    "date": when.isoformat(),
                    "amount": -_m(round(random.uniform(6, 90), 2)),
                    "memo": None,
                    "cleared": "cleared",
                    "approved": True,
                    "account_id": "a1",
                    "account_name": "Everyday Checking",
                    "payee_id": f"p-{payee.lower().replace(' ', '-')}",
                    "payee_name": payee,
                    "category_id": "c2",
                    "category_name": "Groceries",
                    "deleted": False,
                    "subtransactions": [],
                }
            )
    return out


ALL_TXNS = _transactions()

UNCATEGORIZED = [
    ("Hardware Store", -84.21, 2),
    ("Corner Grocer", -46.08, 1),
    ("Unknown Merchant", -19.99, 4),
]
UNAPPROVED = [
    ("Fiber Internet", -79.99, 1),
    ("Coffee Bar", -6.75, 3),
]


def _queue(items: list[tuple[str, float, int]], *, categorized: bool) -> list[dict[str, Any]]:
    out = []
    for index, (payee, amount, days_ago) in enumerate(items):
        out.append(
            {
                "id": f"q{index}-{int(categorized)}",
                "date": (TODAY - timedelta(days=days_ago)).isoformat(),
                "amount": _m(amount),
                "memo": None,
                "cleared": "uncleared",
                "approved": categorized,
                "account_id": "a1",
                "account_name": "Everyday Checking",
                "payee_id": f"p-{index}",
                "payee_name": payee,
                "category_id": "c2" if categorized else None,
                "category_name": "Groceries" if categorized else None,
                "deleted": False,
                "subtransactions": [],
            }
        )
    return out


def _month_payload() -> dict[str, Any]:
    cats = []
    for index, (name, budgeted, activity, balance) in enumerate(CATEGORIES, start=1):
        cats.append(
            {
                "id": f"c{index}",
                "category_group_id": "g1",
                "name": name,
                "hidden": False,
                "budgeted": _m(budgeted),
                "activity": _m(activity),
                "balance": _m(balance),
                "deleted": False,
                "goal_type": "NEED" if name in {"Groceries", "Health"} else None,
                "goal_under_funded": _m(120.00) if name == "Health" else None,
            }
        )
    return {
        "month": MONTH,
        "income": _m(5400.00),
        "budgeted": _m(3835.00),
        "activity": _m(-3678.04),
        "to_be_budgeted": _m(280.00),
        "age_of_money": 38,
        "deleted": False,
        "categories": cats,
    }


def _accounts_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": f"a{index}",
            "name": name,
            "type": kind,
            "on_budget": on_budget,
            "closed": False,
            "balance": _m(balance),
            "cleared_balance": _m(balance),
            "uncleared_balance": 0,
            "transfer_payee_id": f"tp{index}",
            "deleted": False,
        }
        for index, (name, kind, balance, on_budget) in enumerate(ACCOUNTS, start=1)
    ]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:  # keep the demo terminal clean
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        body: dict[str, Any]

        if path.endswith("/months/" + MONTH) or "/months/" in path:
            body = {"data": {"month": _month_payload()}}
        elif path.endswith("/accounts"):
            body = {"data": {"accounts": _accounts_payload(), "server_knowledge": 1}}
        elif path.endswith("/categories"):
            body = {
                "data": {
                    "category_groups": [
                        {
                            "id": "g1",
                            "name": "Monthly Bills",
                            "hidden": False,
                            "deleted": False,
                            "categories": _month_payload()["categories"],
                        }
                    ],
                    "server_knowledge": 1,
                }
            }
        elif path.endswith("/transactions"):
            kind = (query.get("type") or [None])[0]
            if kind == "uncategorized":
                txns = _queue(UNCATEGORIZED, categorized=False)
            elif kind == "unapproved":
                txns = _queue(UNAPPROVED, categorized=True)
            else:
                txns = ALL_TXNS
            body = {"data": {"transactions": txns, "server_knowledge": 1}}
        elif path.endswith("/scheduled_transactions"):
            body = {"data": {"scheduled_transactions": [], "server_knowledge": 1}}
        elif path.endswith("/budgets"):
            body = {"data": {"budgets": [{"id": PLAN_ID, "name": "Demo Household"}], "default_budget": None}}
        else:
            body = {"data": {}}

        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def serve() -> str:
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/v1"
