# Postman Collections

Two separate collections exist for different audiences and purposes.

---

## Collections

| File | Purpose | Audience |
|------|---------|----------|
| `collections/ynab-operator.postman_collection.json` | Operational exploration and debugging | Developers, operators |
| `collections/ynab-qa.postman_collection.json` | Deterministic acceptance verification | CI, regression testing |

---

## Operator Collection

**Source of truth:** `sources/operator/routes.yaml`

The operator collection is generated from `routes.yaml`. It covers all 38 HTTP routes implemented in the `ynab_client` layer, grouped into 10 folders by domain:

- User
- Plans
- Accounts
- Categories
- Months
- Transactions — Read
- Transactions — Write
- Payees
- Scheduled Transactions
- Money Movements

Read routes have lightweight smoke assertions (status 200 + `data` key present).
Write routes are documented with realistic example bodies.

**Generate:**
```bash
uv run python scripts/generate_operator_collection.py
```

**Import into Postman:**
1. Open Postman → Import → File
2. Select `postman/collections/ynab-operator.postman_collection.json`
3. Import `postman/environments/ynab-operator.postman_environment.json` as your environment
4. Set `api_key` and `plan_id` in the environment

**Workflow — first-time setup:**
1. Run `List Plans` — copy a budget ID into `plan_id`
2. Run `List Accounts` — copy an account ID into `account_id`
3. Run `List Categories` — copy a category ID into `category_id`
4. Run `List Transactions` — copy a transaction ID into `transaction_id`
5. Run `List Payees` — copy a payee ID into `payee_id`

---

## QA Collection

**Sources of truth:**
- `tests/qa/features/*.feature` — human-readable scenario titles and tags
- `tests/qa/cases/*.yaml` — machine-readable executable specs
- `tests/fixtures/*.json` — request body fixtures for write cases

**Generate:**
```bash
uv run python scripts/generate_qa_collection.py
```

**31 cases across 4 families:**

| Family | Cases | Tags |
|--------|-------|------|
| auth_and_plans | 7 | smoke, error |
| accounts_and_categories | 8 | smoke, read, error |
| transactions_read | 12 | smoke, read, error |
| error_handling | 5 | smoke, error |

**Run with Newman (smoke only — safe for CI):**
```bash
newman run postman/collections/ynab-qa.postman_collection.json \
  --environment postman/environments/ynab-qa.postman_environment.json \
  --folder "Auth And Plans" \
  --folder "Accounts And Categories" \
  --folder "Transactions Read" \
  --folder "Error Handling" \
  --env-var "api_key=$YNAB_API_KEY" \
  --env-var "plan_id=$YNAB_PLAN_ID"
```

**Import into Postman:**
1. Import `postman/collections/ynab-qa.postman_collection.json`
2. Import `postman/environments/ynab-qa.postman_environment.json`
3. Set `api_key` and `plan_id` — all other variables are optional for read cases

---

## Environments

| File | Purpose |
|------|---------|
| `environments/ynab-operator.postman_environment.json` | Manual exploration; pre-populated with helpful descriptions |
| `environments/ynab-qa.postman_environment.json` | CI use; minimal variables, debug toggle |

Both environments require `api_key` (YNAB PAT) and `plan_id` at minimum.

---

## CI Drift Detection

The generated collection JSON files are committed to the repo. CI should verify they are current:

```bash
# Fail if operator collection is stale
uv run python scripts/generate_operator_collection.py --check

# Fail if QA collection is stale
uv run python scripts/generate_qa_collection.py --check
```

Add these to your CI workflow after any change to:
- `postman/sources/operator/routes.yaml` → triggers operator check
- `tests/qa/features/*.feature` → triggers QA check
- `tests/qa/cases/*.yaml` → triggers QA check
- `tests/fixtures/*.json` → triggers QA check

---

## Maintenance Rules

### When to update the operator collection

Edit `postman/sources/operator/routes.yaml` and regenerate when:
- A new route is added to `ynab_client/`
- A route's query parameters change
- A route's request body shape changes
- A description needs improvement

Do not edit the generated JSON directly.

### When to update the QA collection

To add a new QA case:
1. Add a `@QA-FAM-NNN` tagged scenario to the relevant `.feature` file
2. Add a matching case entry (same `id`) to the relevant `.yaml` file in `tests/qa/cases/`
3. Add any required body fixtures to `tests/fixtures/`
4. Run `uv run python scripts/generate_qa_collection.py`

The generator will fail fast if the feature/case files are out of sync.

### What is NOT covered

The QA collection does not cover:
- Write paths in CI (create/update/delete produce durable data and require cleanup)
- MCP tool calls (the MCP protocol uses stdio, not HTTP)
- Response ordering (no assertions on list order unless order is a stated contract)
- Exact error message wording (only structural fields like `name`, `id`, `detail`)
- Rate limiting behavior (cannot safely reproduce 429 in CI)

These gaps are intentional. Covering them would make the collection brittle or destructive.
