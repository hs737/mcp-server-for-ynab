# Agent evals

`make check` proves the server works. These prove an agent *uses* it correctly,
which is a different question and the one the test suite cannot reach.

Every case here is a failure that actually happened during a twenty-one-month
audit and a four-day cleanup of a real plan: a rate-limit lockout caused by a
loop that should have been one call, an account reported as reconciled that the
YNAB app still showed as stale, seven months of transfers mistaken for funding.
The server was changed so that a careful agent avoids each one — a tool
description that states its cost, a delta option that halves a write, a caveat
carried on every response that could mislead. Whether the descriptions actually
land is a property of the model reading them, so it has to be measured rather
than assumed.

## Running them

```bash
claude plugin eval .                      # every case, against this plugin
claude plugin eval --case 'rate-limit-*' .
```

Cases are a directory each: `prompt.md` is the turn the agent is given, and
`graders/*.md` are the criteria it is scored against. Nothing here carries a
`case.yaml`, so every case takes the runner's defaults — add one when a case
needs its own `runs`, timeout, or tags.

`claude plugin eval` is in early access. If it reports that, the suite is still
readable as a specification of what good behaviour looks like — the graders say
plainly what passes and what fails — but nothing here has been executed. **No
case in this directory has been run.** Treat the pass criteria as reviewed
intent, not as observed results, until a first green run says otherwise.

By default the runner compares the plugin against a no-plugin baseline and
reports the delta, which is the number worth watching: a case that scores well
without the server is measuring the model, not the tools.

## Two things to decide before the first run

**Where the data comes from.** These cases talk about real accounts and real
money. Options, worst to best:

1. A live token. Simple, and wrong: the write cases would move real money, and
   the read cases spend the same 200-per-hour quota the suite exists to protect.
2. `--mocks record` (the default), which puts mock stand-ins in front of the MCP
   server and stores them under `evals/mocks/`. Record once, commit them, and
   the suite runs offline and deterministically thereafter.
3. A synthetic backend. `scripts/demo/backend.py` already serves fictional YNAB
   data for the README GIF — every number in that demo comes from the real
   server code paths over invented data. It answers reads only; the write routes
   the reconciliation cases need are not implemented, and the client's base URL
   is a module constant rather than an environment variable, so pointing the
   server at it currently takes the monkeypatch that `scripts/demo/capture.py`
   does. Making both configurable is the one piece of work that would let the
   whole suite run in CI with no credentials at all.

Start with (2). Reach for (3) if the recorded mocks turn out to be too rigid for
the multi-step cases.

**Which cases need writes.** `read-only-server-says-so` must run against a
server started *without* `YNAB_ALLOW_WRITES`, because it asserts what happens
when the write tools are absent. The rest of the write cases need them present.
That is two runner configurations, not one.

## The cases

| Case | Asserts |
|------|---------|
| `adjust-by-instead-of-read-and-replace` | Uses `adjust_by` rather than read-then-write, and reports the change without a confirming re-read |
| `bulk-write-not-a-loop` | Forty transactions is one bulk call, and the verification block is read rather than the HTTP status |
| `preview-before-reconciling` | `reconcile_preview` before any write, and no adjustment posted over an unexplained difference |
| `reconciled-date-stays-stale` | Says `last_reconciled_at` does not move — the failure that reads as a lie |
| `rate-limit-comeback` | Uses `retry_at`, does not oversell the reopening, and checks liveness with `ping` |
| `one-range-not-many-reads` | `months_range` once, not `months_get` twenty times |
| `refresh-with-changes-since` | `changes_since` rather than re-reading the budget wholesale |
| `pending-holds-are-checked-not-deleted` | Finds `YNAB:P:` holds in the queue that can see them, and does not delete unasked |
| `transfers-move-no-category-money` | Explains that an on-budget transfer assigns nothing, and checks the months |
| `read-only-server-says-so` | Reports the write gate instead of improvising |
| `undo-the-last-write` | Reverts through the journal, and is honest about what could not be restored |

## Adding a case

Two rules, both learned from the report these came from.

**A case earns its place by naming a failure that happened**, not by covering a
tool. There is no case for `overview_cash_position`, because nothing has ever
gone wrong with it. There are two graders on the reconciliation cases, because
that is where an agent can be confidently, expensively wrong.

**A grader says what fails, not only what passes.** "Uses `reconcile_preview`"
is half a criterion; the half that catches regressions is "does not go straight
to `reconcile_apply`, and does not hand-roll the workflow out of primitives".
Write the failure you are afraid of.

Keep the suite small. These runs are model-graded, so they are slow, cost money,
and vary between runs — `--runs` defaults to 3 for that reason. A dozen sharp
cases run on demand or nightly is worth more than fifty run on every pull
request, and `make check` remains the gate that runs every time.
