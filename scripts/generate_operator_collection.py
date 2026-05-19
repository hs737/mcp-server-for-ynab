#!/usr/bin/env python3
"""Generate the YNAB operator Postman collection from postman/sources/operator/routes.yaml.

Usage:
    uv run python scripts/generate_operator_collection.py          # write output
    uv run python scripts/generate_operator_collection.py --check  # fail if stale (CI)

Source of truth: postman/sources/operator/routes.yaml
Output:         postman/collections/ynab-operator.postman_collection.json
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).parent.parent
ROUTES_PATH = REPO_ROOT / "postman" / "sources" / "operator" / "routes.yaml"
OUTPUT_PATH = REPO_ROOT / "postman" / "collections" / "ynab-operator.postman_collection.json"

COLLECTION_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
BASE_URL_VAR = "{{base_url}}"

AUTH_HEADER = {
    "key": "Authorization",
    "value": "Bearer {{api_key}}",
    "type": "text",
    "description": "YNAB Personal Access Token. Set api_key in your environment.",
}
CONTENT_TYPE_HEADER = {
    "key": "Content-Type",
    "value": "application/json",
    "type": "text",
}

# Variables exposed at collection level — operators set these in their environment.
COLLECTION_VARIABLES = [
    {
        "key": "base_url",
        "value": "https://api.ynab.com/v1",
        "type": "default",
        "description": "YNAB API base URL. Do not change unless testing a mock.",
    },
    {"key": "api_key", "value": "", "type": "secret", "description": "YNAB Personal Access Token. Required."},
    {
        "key": "plan_id",
        "value": "",
        "type": "default",
        "description": "Default budget/plan ID. Copy from List Plans response.",
    },
    {"key": "account_id", "value": "", "type": "default", "description": "Account ID for account-scoped requests."},
    {
        "key": "account_id_2",
        "value": "",
        "type": "default",
        "description": "Second account ID, used for transfer requests.",
    },
    {"key": "category_id", "value": "", "type": "default", "description": "Category ID for category-scoped requests."},
    {
        "key": "category_id_2",
        "value": "",
        "type": "default",
        "description": "Second category ID, used for split transaction requests.",
    },
    {
        "key": "category_group_id",
        "value": "",
        "type": "default",
        "description": "Category group ID for category group requests.",
    },
    {
        "key": "transaction_id",
        "value": "",
        "type": "default",
        "description": "Transaction ID for single-transaction requests.",
    },
    {"key": "payee_id", "value": "", "type": "default", "description": "Payee ID for payee-scoped requests."},
    {
        "key": "payee_location_id",
        "value": "",
        "type": "default",
        "description": "Payee location ID for location requests.",
    },
    {"key": "scheduled_transaction_id", "value": "", "type": "default", "description": "Scheduled transaction ID."},
    {
        "key": "month",
        "value": "2025-05-01",
        "type": "default",
        "description": "ISO date for the first day of the month, e.g. 2025-05-01.",
    },
    {
        "key": "last_knowledge_of_server",
        "value": "",
        "type": "default",
        "description": "Save server_knowledge from any response; pass it back for delta sync.",
    },
]


def _stable_id(label: str) -> str:
    """Return a deterministic UUID for a given label string."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"ynab-operator.{label}"))


def _build_url(path: str, query_params: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a Postman URL object from a path template and optional query params."""
    raw = f"{BASE_URL_VAR}{path}"
    # Split path into segments, preserving {{var}} placeholders
    segments = [s for s in path.lstrip("/").split("/") if s]
    url: dict[str, Any] = {
        "raw": raw,
        "host": [BASE_URL_VAR],
        "path": segments,
    }
    if query_params:
        url["query"] = []
        for qp in query_params:
            url["query"].append(
                {
                    "key": qp["key"],
                    "value": qp.get("example", ""),
                    "description": qp.get("description", ""),
                    "disabled": not qp.get("required", False),
                }
            )
    return url


def _smoke_test_script(route_name: str) -> dict[str, Any]:
    """Build a lightweight smoke assertion event for read routes."""
    return {
        "listen": "test",
        "script": {
            "id": _stable_id(f"script.smoke.{route_name}"),
            "type": "text/javascript",
            "exec": [
                'pm.test("Status is 200", function() {',
                "    pm.response.to.have.status(200);",
                "});",
                'pm.test("Response has data key", function() {',
                "    const json = pm.response.json();",
                '    pm.expect(json).to.have.property("data");',
                "});",
            ],
        },
    }


def _build_request(route: dict[str, Any]) -> dict[str, Any]:
    method = route["method"].upper()
    headers = [AUTH_HEADER]
    if method in ("POST", "PUT", "PATCH"):
        headers = [AUTH_HEADER, CONTENT_TYPE_HEADER]

    req: dict[str, Any] = {
        "method": method,
        "header": headers,
        "url": _build_url(route["path"], route.get("query_params", [])),
        "description": route.get("description", "").strip(),
    }

    if "body" in route:
        req["body"] = {
            "mode": "raw",
            "raw": json.dumps(route["body"], indent=2),
            "options": {"raw": {"language": "json"}},
        }

    return req


def _build_item(route: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": _stable_id(f"route.{route['name']}"),
        "name": route["name"],
        "request": _build_request(route),
        "response": [],
    }
    if route.get("smoke_check") and route.get("classification") == "read":
        item["event"] = [_smoke_test_script(route["name"])]
    return item


def _build_folder(folder: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _stable_id(f"folder.{folder['name']}"),
        "name": folder["name"],
        "description": folder.get("description", "").strip(),
        "item": [_build_item(route) for route in folder.get("routes", [])],
    }


def _generate(routes_path: Path) -> dict[str, Any]:
    with open(routes_path) as f:
        spec = yaml.safe_load(f)

    if "collection" not in spec:
        raise ValueError("routes.yaml must have a top-level 'collection' key")
    if "folders" not in spec:
        raise ValueError("routes.yaml must have a top-level 'folders' key")

    col = spec["collection"]
    return {
        "info": {
            "_postman_id": _stable_id("collection.operator"),
            "name": col["name"],
            "description": col.get("description", "").strip(),
            "schema": COLLECTION_SCHEMA,
        },
        "item": [_build_folder(folder) for folder in spec["folders"]],
        "variable": COLLECTION_VARIABLES,
    }


def _stats(collection: dict[str, Any]) -> tuple[int, int]:
    """Return (folder_count, request_count)."""
    folders = collection.get("item", [])
    requests = sum(len(f.get("item", [])) for f in folders)
    return len(folders), requests


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed collection differs from what would be generated. Use in CI.",
    )
    args = parser.parse_args()

    if not ROUTES_PATH.exists():
        print(f"ERROR: Routes file not found: {ROUTES_PATH}", file=sys.stderr)
        sys.exit(1)

    collection = _generate(ROUTES_PATH)
    generated = json.dumps(collection, indent=2) + "\n"

    folders, requests = _stats(collection)

    if args.check:
        if not OUTPUT_PATH.exists():
            print(
                f"ERROR: Committed collection not found at {OUTPUT_PATH}.\n"
                "Run: uv run python scripts/generate_operator_collection.py",
                file=sys.stderr,
            )
            sys.exit(1)
        existing = OUTPUT_PATH.read_text()
        if existing != generated:
            print(
                "ERROR: Operator collection is out of date.\n"
                "Run: uv run python scripts/generate_operator_collection.py",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"OK: Operator collection is current. ({folders} folders, {requests} requests)")
    else:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(generated)
        print(f"Generated: {OUTPUT_PATH}")
        print(f"  {folders} folders, {requests} requests")


if __name__ == "__main__":
    main()
