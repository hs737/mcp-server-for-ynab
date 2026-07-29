---
name: live-api-verification
description: Verify response models and MCP transports against the real YNAB API before claiming a tool works.
---

# Live API Verification

Use this skill whenever a change touches how a YNAB response is parsed, or how
an agent connects to the server. The test suite cannot catch drift between a
response model and the real API, because every payload in it was written by
hand: the model and the fixture are the same guess.

## Use When

- Adding or editing a model under `src/ynab_mcp/models/ynab/`
- Adding a raw tool or a `ynab_client` wrapper for a new route
- Upgrading the `mcp` SDK, or changing transport/CLI startup
- Reviewing a claim that a tool "works" when only unit tests were run
- Investigating a tool that fails in a client but passes in CI

## The Failures This Prevents

The money movement models were written by analogy with transactions. They
required `date` on a movement and `name`/`amount` on a group. The real API
sends none of those — it sends `month`, `moved_at`, and category endpoints.
All four money movement tools failed at validation on every call, while the
suite passed, because no test used a real payload and no test touched the
family at all.

Two properties made this invisible:

1. Hand-written fixtures agree with the model by construction.
2. The tool boundary returns failures as a structured error payload with
   `isError: False`, so a caller that only checks the MCP result looks fine.

The write tools failed four more ways, each invisible to the same suite:

- `category-groups` in the path where the API wants `category_groups`, so YNAB
  answered "Invalid URI" for create and update alike
- `categories_create` could not send `category_group_id`, which the API
  requires, so no category could ever be created
- the bulk update model expected `data.bulk`, a shape this route does not
  return, so the write succeeded and the response failed to parse
- the group create and update routes return a group without its `categories`,
  which the response model required

None of these are visible from the request side. Three of the four failed
*after* YNAB had already accepted the write.

## Rules

1. Never infer a response shape from a sibling resource. Fetch the endpoint and
   read what it actually returns.
2. Record fixtures from a live response and replace the identifiers. Do not
   write fixture payloads from the model definition.
3. Profile every record in the response before setting a field required, not
   just the first one. A field that is non-null in record 1 and null in record
   40 makes a required field a guaranteed failure.
4. A tool is not verified until it has been invoked against the live API. Green
   unit tests are not evidence that a tool works.
5. When parsing fails, check whether the error is reported as a tool error or
   hidden in a success envelope, and say which in the report.
6. Accepted is not applied. YNAB takes `budgeted` on the category update route
   and ignores it, returning 200 and a `budgeted` of 0. After any write sweep,
   read the plan back and confirm the values actually changed.
7. Check both directions of a route pair. A resource's create response is
   frequently a different shape from its list response — usually thinner, as
   with a category group returned without its categories.

## Workflow

```bash
# 1. See what the endpoint really returns, across all records.
curl -s -H "Authorization: Bearer $YNAB_API_KEY" \
  "https://api.ynab.com/v1/budgets/$YNAB_PLAN_ID/<resource>" | python3 -c "
import json, sys, collections
data = json.load(sys.stdin)['data']
key = [k for k in data if isinstance(data[k], list)][0]
records = data[key]
types = collections.defaultdict(collections.Counter)
for record in records:
    for field, value in record.items():
        types[field][type(value).__name__] += 1
print(f'{len(records)} records')
for field, counts in types.items():
    print(f'  {field:28} {dict(counts)}')
"

# 2. Make the change, then verify.
make test
make verify-live                   # every read-only tool against the live API
make verify-write PLAN_ID=<uuid>   # every write tool, against a disposable plan
make verify-mcp-http               # the MCP handshake an agent performs

# 3. For writes, read the plan back and confirm the values changed.
```

A field whose type counter shows `NoneType` for any record is optional.

Never point `verify-write` at a real budget. It takes an explicit plan id, never
falls back to `YNAB_PLAN_ID`, and refuses plans whose name does not look
disposable. Keep those guards if you extend it.

## Reporting

State what was actually run. "39 read tools invoked live, 0 failures" is a
verification claim; "tests pass" is not. If a tool was skipped because the plan
has no such record, say so rather than counting it as passing.

## Related Skills

- `contract-sync` — keeping generated artifacts aligned with the source of truth
- `docs-honesty` — keeping claims in docs matched to implementation
