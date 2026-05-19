#!/usr/bin/env python3
"""Generate the YNAB QA Postman collection from feature files and case YAML definitions.

Usage:
    uv run python scripts/generate_qa_collection.py          # write output
    uv run python scripts/generate_qa_collection.py --check  # fail if stale (CI)

Sources:
    tests/qa/features/*.feature   — human-readable scenario titles and tags
    tests/qa/cases/*.yaml         — machine-readable executable specs
    tests/fixtures/*.json         — request body fixtures

Output:
    postman/collections/ynab-qa.postman_collection.json

Validation (generator fails fast on):
    - Feature scenarios without a matching case definition
    - Case definitions without a matching feature scenario
    - Duplicate case IDs across all YAML files
    - References to missing fixture files
    - Unknown assertion types
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).parent.parent
FEATURES_DIR = REPO_ROOT / "tests" / "qa" / "features"
CASES_DIR = REPO_ROOT / "tests" / "qa" / "cases"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
OUTPUT_PATH = REPO_ROOT / "postman" / "collections" / "ynab-qa.postman_collection.json"

COLLECTION_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
BASE_URL_VAR = "{{base_url}}"

# Assertion types the generator knows how to render into Postman JS test scripts.
KNOWN_ASSERTION_TYPES = {
    "status",
    "json_has_key",
    "json_key_is_string",
    "json_key_is_integer",
    "json_key_is_array",
    "json_array_not_empty",
    "json_array_items_have_key",
    "custom",
}

AUTH_HEADER = {
    "key": "Authorization",
    "value": "Bearer {{api_key}}",
    "type": "text",
}
CONTENT_TYPE_HEADER = {
    "key": "Content-Type",
    "value": "application/json",
    "type": "text",
}

COLLECTION_VARIABLES = [
    {"key": "base_url", "value": "https://api.ynab.com/v1", "type": "default"},
    {"key": "api_key", "value": "", "type": "secret"},
    {"key": "plan_id", "value": "", "type": "default"},
    {"key": "account_id", "value": "", "type": "default"},
    {"key": "account_id_2", "value": "", "type": "default"},
    {"key": "category_id", "value": "", "type": "default"},
    {"key": "category_id_2", "value": "", "type": "default"},
    {"key": "transaction_id", "value": "", "type": "default"},
    {"key": "payee_id", "value": "", "type": "default"},
    {"key": "scheduled_transaction_id", "value": "", "type": "default"},
    {"key": "month", "value": "2025-05-01", "type": "default"},
    {
        "key": "qa_debug",
        "value": "false",
        "type": "default",
        "description": "Set to 'true' to enable verbose test logging.",
    },
]

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _stable_id(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"ynab-qa.{label}"))


def _parse_features() -> dict[str, dict[str, Any]]:
    """Parse all feature files and return a dict keyed by case ID.

    Returns: {case_id: {title, family, tags, feature_file}}
    """
    scenarios: dict[str, dict[str, Any]] = {}
    seen_ids: dict[str, str] = {}  # id -> file path

    for feature_file in sorted(FEATURES_DIR.glob("*.feature")):
        current_tags: list[str] = []
        family: str | None = None

        for line in feature_file.read_text().splitlines():
            line = line.strip()

            # Feature-level family tag
            if line.startswith("@family:"):
                family = line.split(":")[1].strip()
                continue

            # Scenario-level tag lines (may include @QA-* and other tags)
            if line.startswith("@"):
                current_tags = [t.lstrip("@") for t in line.split() if t.startswith("@")]
                continue

            # Scenario title line
            if line.startswith("Scenario:"):
                title = line[len("Scenario:") :].strip()
                # Find the QA-* id among the current tags
                qa_ids = [t for t in current_tags if re.match(r"^QA-[A-Z]+-\d+$", t)]
                if not qa_ids:
                    print(
                        f"WARNING: Scenario without QA-* tag in {feature_file.name}: {title!r}",
                        file=sys.stderr,
                    )
                    current_tags = []
                    continue
                if len(qa_ids) > 1:
                    print(
                        f"ERROR: Scenario has multiple QA-* tags in {feature_file.name}: {qa_ids}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                case_id = qa_ids[0]
                if case_id in seen_ids:
                    print(
                        f"ERROR: Duplicate case ID {case_id!r} in {feature_file.name} "
                        f"(first seen in {seen_ids[case_id]})",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                seen_ids[case_id] = str(feature_file.name)
                other_tags = [t for t in current_tags if not re.match(r"^QA-[A-Z]+-\d+$", t)]
                scenarios[case_id] = {
                    "title": title,
                    "family": family or "unknown",
                    "tags": other_tags,
                    "feature_file": feature_file.name,
                }
                current_tags = []

    return scenarios


def _parse_cases() -> dict[str, dict[str, Any]]:
    """Parse all case YAML files and return a dict keyed by case ID."""
    cases: dict[str, dict[str, Any]] = {}
    seen_ids: dict[str, str] = {}

    for case_file in sorted(CASES_DIR.glob("*.yaml")):
        doc = yaml.safe_load(case_file.read_text())
        family = doc.get("family", "unknown")

        for case in doc.get("cases", []):
            case_id = case.get("id")
            if not case_id:
                print(f"ERROR: Case without id in {case_file.name}: {case}", file=sys.stderr)
                sys.exit(1)
            if case_id in seen_ids:
                print(
                    f"ERROR: Duplicate case ID {case_id!r} in {case_file.name} (first seen in {seen_ids[case_id]})",
                    file=sys.stderr,
                )
                sys.exit(1)
            seen_ids[case_id] = str(case_file.name)
            case["_family"] = family
            case["_source_file"] = case_file.name
            cases[case_id] = case

    return cases


def _validate_sync(scenarios: dict[str, Any], cases: dict[str, Any]) -> None:
    """Fail if scenarios and cases are not in sync."""
    feature_ids = set(scenarios.keys())
    case_ids = set(cases.keys())

    missing_cases = feature_ids - case_ids
    missing_scenarios = case_ids - feature_ids

    errors = []
    if missing_cases:
        errors.append(
            "Feature scenarios without case definitions (add to tests/qa/cases/):\n"
            + "\n".join(f"  - {i}" for i in sorted(missing_cases))
        )
    if missing_scenarios:
        errors.append(
            "Case definitions without feature scenarios (add to tests/qa/features/):\n"
            + "\n".join(f"  - {i}" for i in sorted(missing_scenarios))
        )
    if errors:
        print("ERROR: Feature/case sync failure:\n" + "\n".join(errors), file=sys.stderr)
        sys.exit(1)


def _validate_assertions(cases: dict[str, Any]) -> None:
    """Fail on unknown assertion types."""
    errors = []
    for case_id, case in cases.items():
        for assertion in case.get("assertions", []):
            atype = assertion.get("type")
            if atype not in KNOWN_ASSERTION_TYPES:
                errors.append(
                    f"Unknown assertion type {atype!r} in case {case_id} (source: {case.get('_source_file')})"
                )
    if errors:
        print("ERROR: Unknown assertion types:\n" + "\n".join(errors), file=sys.stderr)
        sys.exit(1)


def _validate_fixtures(cases: dict[str, Any]) -> None:
    """Fail if any referenced fixture file does not exist."""
    errors = []
    for case_id, case in cases.items():
        fixture = case.get("body_fixture")
        if fixture:
            fixture_path = FIXTURES_DIR / fixture
            if not fixture_path.exists():
                errors.append(f"Case {case_id} references missing fixture: {fixture}")
    if errors:
        print("ERROR: Missing fixture files:\n" + "\n".join(errors), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Code generation helpers
# ---------------------------------------------------------------------------


def _js_path_access(dotted_path: str) -> str:
    """Convert 'data.transactions[0].id' to chained property access for JS."""
    parts = dotted_path.split(".")
    js = "json"
    for part in parts:
        if "[" in part:
            name, idx = part.rstrip("]").split("[")
            js += f'["{name}"][{idx}]'
        else:
            js += f'["{part}"]'
    return js


def _js_nested_has_key(dotted_path: str, case_id: str) -> list[str]:
    """Generate JS to assert that a nested path exists."""
    parts = dotted_path.split(".")
    lines: list[str] = []
    access = "json"
    for i, part in enumerate(parts):
        parent_access = access
        access = access + f'["{part}"]'
        lines.append(f'pm.test("[{case_id}] {dotted_path} exists (depth {i + 1})", function() {{')
        lines.append(f'    pm.expect({parent_access}).to.have.property("{part}");')
        lines.append("});")
    return lines


def _build_assertion_script(assertions: list[dict[str, Any]], case_id: str) -> list[str]:
    """Render a list of assertion dicts into Postman test script lines."""
    lines: list[str] = []
    lines.append("const json = pm.response.json();")

    for assertion in assertions:
        atype = assertion["type"]
        tag = f"[{case_id}]"

        if atype == "status":
            value = assertion["value"]
            lines.append(f'pm.test("{tag} Status is {value}", function() {{')
            lines.append(f"    pm.response.to.have.status({value});")
            lines.append("});")

        elif atype == "json_has_key":
            path = assertion["path"]
            lines.extend(_js_nested_has_key(path, case_id))

        elif atype == "json_key_is_string":
            path = assertion["path"]
            access = _js_path_access(path)
            lines.append(f'pm.test("{tag} {path} is a string", function() {{')
            lines.append(f"    pm.expect({access}).to.be.a('string');")
            lines.append("});")

        elif atype == "json_key_is_integer":
            path = assertion["path"]
            access = _js_path_access(path)
            lines.append(f'pm.test("{tag} {path} is an integer", function() {{')
            lines.append(f"    pm.expect({access}).to.be.a('number');")
            lines.append(f"    pm.expect(Number.isInteger({access})).to.be.true;")
            lines.append("});")

        elif atype == "json_key_is_array":
            path = assertion["path"]
            access = _js_path_access(path)
            lines.append(f'pm.test("{tag} {path} is an array", function() {{')
            lines.append(f"    pm.expect({access}).to.be.an('array');")
            lines.append("});")

        elif atype == "json_array_not_empty":
            path = assertion["path"]
            access = _js_path_access(path)
            lines.append(f'pm.test("{tag} {path} is not empty", function() {{')
            lines.append(f"    pm.expect({access}.length).to.be.greaterThan(0);")
            lines.append("});")

        elif atype == "json_array_items_have_key":
            path = assertion["path"]
            key = assertion["key"]
            access = _js_path_access(path)
            lines.append(f'pm.test("{tag} each {path}[] has key {key!r}", function() {{')
            lines.append(f"    const arr = {access} || [];")
            lines.append("    arr.slice(0, 5).forEach(function(item, i) {")
            lines.append(f'        pm.expect(item).to.have.property("{key}");')
            lines.append("    });")
            lines.append("});")

        elif atype == "custom":
            # Embed the custom script lines verbatim
            script = assertion.get("script", "")
            lines.extend(script.strip().splitlines())

    return lines


def _build_prerequest_script(case: dict[str, Any]) -> dict[str, Any] | None:
    """Build a pre-request script for cases that override headers."""
    headers = case.get("headers", {})
    if not headers:
        return None

    lines = [
        "// Pre-request: override default headers for this case",
        "if (typeof qa_debug !== 'undefined' && pm.variables.get('qa_debug') === 'true') {",
        "    console.log('Running case: " + case["id"] + "');",
        "}",
    ]

    # If Authorization is explicitly set (overriding the collection-level auth)
    if "Authorization" in headers:
        auth_val = headers["Authorization"]
        lines.append(f"pm.request.headers.upsert({{key: 'Authorization', value: '{auth_val}'}});")

    return {
        "listen": "prerequest",
        "script": {
            "id": _stable_id(f"prerequest.{case['id']}"),
            "type": "text/javascript",
            "exec": lines,
        },
    }


def _build_test_event(assertions: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    lines = _build_assertion_script(assertions, case_id)
    return {
        "listen": "test",
        "script": {
            "id": _stable_id(f"test.{case_id}"),
            "type": "text/javascript",
            "exec": lines,
        },
    }


def _build_url(path: str, params: dict[str, str]) -> dict[str, Any]:
    raw = f"{BASE_URL_VAR}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        raw = f"{raw}?{qs}"
    segments = [s for s in path.lstrip("/").split("/") if s]
    url: dict[str, Any] = {"raw": raw, "host": [BASE_URL_VAR], "path": segments}
    if params:
        url["query"] = [{"key": k, "value": v, "disabled": False} for k, v in params.items()]
    return url


def _build_request(case: dict[str, Any]) -> dict[str, Any]:
    method = case["method"].upper()
    headers: list[dict[str, str]] = [AUTH_HEADER]
    if method in ("POST", "PUT", "PATCH"):
        headers = [AUTH_HEADER, CONTENT_TYPE_HEADER]

    req: dict[str, Any] = {
        "method": method,
        "header": headers,
        "url": _build_url(case["path"], case.get("params") or {}),
        "description": (
            f"**Case:** {case['id']}\n\n"
            f"**Intent:** {case['title']}\n\n"
            + (f"**Preconditions:** {chr(10).join(case['preconditions'])}\n\n" if case.get("preconditions") else "")
            + (f"**Notes:** {case.get('notes', '')}\n\n" if case.get("notes") else "")
            + f"**Expected status:** {case['expected_status']}\n\n"
            f"**Source:** {case.get('_source_file', 'unknown')}"
        ),
    }

    fixture = case.get("body_fixture")
    if fixture:
        fixture_path = FIXTURES_DIR / fixture
        body_content = fixture_path.read_text()
        req["body"] = {
            "mode": "raw",
            "raw": body_content,
            "options": {"raw": {"language": "json"}},
        }

    return req


def _build_item(case_id: str, case: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []

    pre = _build_prerequest_script(case)
    if pre:
        events.append(pre)

    assertions = case.get("assertions", [])
    if assertions:
        events.append(_build_test_event(assertions, case_id))

    return {
        "id": _stable_id(f"item.{case_id}"),
        "name": f"[{case_id}] {scenario['title']}",
        "event": events,
        "request": _build_request(case),
        "response": [],
    }


def _build_folder(
    family: str,
    case_ids: list[str],
    cases: dict[str, Any],
    scenarios: dict[str, Any],
) -> dict[str, Any]:
    items = [_build_item(cid, cases[cid], scenarios[cid]) for cid in case_ids]
    return {
        "id": _stable_id(f"folder.{family}"),
        "name": family.replace("_", " ").title(),
        "description": f"QA cases for family: {family}",
        "item": items,
    }


# ---------------------------------------------------------------------------
# Main generation logic
# ---------------------------------------------------------------------------


def _generate() -> dict[str, Any]:
    scenarios = _parse_features()
    cases = _parse_cases()

    _validate_sync(scenarios, cases)
    _validate_assertions(cases)
    _validate_fixtures(cases)

    # Group cases by family, preserving insertion order (feature file sort order)
    families: dict[str, list[str]] = {}
    for case_id, case in cases.items():
        fam = case.get("_family", "unknown")
        families.setdefault(fam, []).append(case_id)

    folders = [_build_folder(fam, ids, cases, scenarios) for fam, ids in families.items()]

    total_cases = sum(len(ids) for ids in families.values())

    return {
        "info": {
            "_postman_id": _stable_id("collection.qa"),
            "name": "YNAB API — QA",
            "description": (
                "QA collection for the YNAB API as consumed by ynab-mcp.\n\n"
                "Generated from:\n"
                "  - tests/qa/features/*.feature  (human-readable scenarios)\n"
                "  - tests/qa/cases/*.yaml        (executable case definitions)\n"
                "  - tests/fixtures/*.json        (request body fixtures)\n\n"
                f"Total cases: {total_cases}\n\n"
                "DO NOT hand-edit this file. Edit the source files and regenerate:\n"
                "  uv run python scripts/generate_qa_collection.py\n\n"
                "Run with Newman:\n"
                "  newman run postman/collections/ynab-qa.postman_collection.json \\\n"
                "    --environment postman/environments/ynab-qa.postman_environment.json \\\n"
                "    --folder 'Auth And Plans'\n\n"
                "CI smoke check (read-only cases):\n"
                "  newman run ... --folder 'Auth And Plans' --folder 'Transactions Read'"
            ),
            "schema": COLLECTION_SCHEMA,
        },
        "item": folders,
        "variable": COLLECTION_VARIABLES,
    }


def _stats(collection: dict[str, Any]) -> tuple[int, int]:
    folders = collection.get("item", [])
    cases = sum(len(f.get("item", [])) for f in folders)
    return len(folders), cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed collection differs from what would be generated.",
    )
    args = parser.parse_args()

    for required_dir in (FEATURES_DIR, CASES_DIR, FIXTURES_DIR):
        if not required_dir.exists():
            print(f"ERROR: Required directory not found: {required_dir}", file=sys.stderr)
            sys.exit(1)

    collection = _generate()
    generated = json.dumps(collection, indent=2) + "\n"
    folders, cases = _stats(collection)

    if args.check:
        if not OUTPUT_PATH.exists():
            print(
                f"ERROR: Committed QA collection not found at {OUTPUT_PATH}.\n"
                "Run: uv run python scripts/generate_qa_collection.py",
                file=sys.stderr,
            )
            sys.exit(1)
        existing = OUTPUT_PATH.read_text()
        if existing != generated:
            print(
                "ERROR: QA collection is out of date.\nRun: uv run python scripts/generate_qa_collection.py",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"OK: QA collection is current. ({folders} families, {cases} cases)")
    else:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(generated)
        print(f"Generated: {OUTPUT_PATH}")
        print(f"  {folders} families, {cases} cases")


if __name__ == "__main__":
    main()
