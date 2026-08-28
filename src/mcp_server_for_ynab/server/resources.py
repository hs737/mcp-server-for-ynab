"""Reference material, exposed as MCP resources.

Tool descriptions have to be short, because every one of them is in the model's
context for the whole session. But some of what an assistant needs to work
competently in YNAB does not fit there: the method itself, the rules about
writing to someone's financial records, and the specific ways YNAB's API will
mislead a caller who assumes a 200 means the change landed.

Resources are fetched on demand, so this material costs nothing until it is
needed. A host that supports them gets the working discipline without the user
having to install a separate skill or paste in a prompt.
"""

from __future__ import annotations

from mcp_server_for_ynab.server.app import mcp

GUIDE_MIME = "text/markdown"


@mcp.resource(
    "ynab://guide/method",
    name="YNAB method",
    title="How YNAB is meant to work",
    description="The budgeting method, and what its terms actually mean.",
    mime_type=GUIDE_MIME,
)
def method_guide() -> str:
    return """# How YNAB is meant to work

YNAB budgets money you already have. Every dollar in an account is assigned to
a category, so the budget describes real money rather than a forecast. This is
why several numbers that look like they should match do not.

## The terms

- **Ready to Assign** — money in your accounts not yet given a job. Not
  savings, and not spendable-without-consequence; it is simply unassigned.
- **Budgeted** — assigned to a category this month.
- **Activity** — spent or received in that category this month.
- **Balance** — budgeted plus activity, carried forward from prior months.
- **Age of Money** — how long a dollar sits before being spent. Rising is good.
- **Plan** — YNAB's current word for what used to be called a budget. The API
  still says `budget` in its routes; this server says `plan` in tool names.

## Consequences worth knowing

**Overspending moves backwards.** A category that ends a month negative pulls
the shortfall out of the next month's Ready to Assign. So a month can look
under-funded for a reason that is entirely invisible in that month's numbers.
When Ready to Assign is lower than expected, check the prior month.

**Credit cards are not ordinary spending.** Spending on a card moves money into
that card's Payment category. If the spending category is overspent, that
transfer cannot happen in full, and the Payment category silently ends up short
of the card balance. The symptom appears at payment time, not at purchase time.

**A transfer is not two transactions.** Moving money between accounts — paying a
card from checking, for instance — is one transfer, not an outflow and an inflow
categorized separately. Recording it as two categorized transactions
double-counts the activity and has to be cleaned up by hand later.

**Assigning money is not spending it.** Moving budgeted dollars between
categories changes the plan, not the account balances. Those moves show up in
this server's money-movement tools, separately from transactions.
"""


@mcp.resource(
    "ynab://guide/write-safety",
    name="Write safety",
    title="Rules for changing someone's budget",
    description="What to confirm, what to verify, and what cannot be undone.",
    mime_type=GUIDE_MIME,
)
def write_safety_guide() -> str:
    return """# Rules for changing someone's budget

These are financial records. The cost of a wrong write is not a stack trace, it
is a number the person has to find and fix later, possibly without knowing it
changed.

## Confirm before writing

Show what you intend to change and wait for the user to agree. This applies to
bulk operations especially: "categorize these 40 transactions" should show the
proposed categories, not a count.

## A 200 is not proof

YNAB accepts `budgeted` on the category update route, returns 200, and ignores
it. This server's write tools re-read what they changed and return a
`verification` block for that reason. Read it. Treat anything listed as failed
as a real failure and re-read the record directly.

## Queue counts hide failures

When one call both categorizes and approves, the transaction leaves the
unapproved queue whether or not the category write succeeded. So a queue that
shrank is not evidence the categorization worked. Use the verification block.

## What cannot be undone

Every write this server performs is journaled with the state that preceded it,
because YNAB has no history endpoint and an overwritten value is otherwise
gone. `history_revert` reverses one entry; `history_revert_to` rolls back to a
point, newest first, since overlapping edits to one record only compose
correctly in reverse.

But some things the API simply cannot undo:

- **Creating an account, category, category group, or payee.** YNAB has no
  delete route for any of them. These are journaled as non-revertible with the
  reason, and a rollback reports them under `blocked` rather than passing over
  them silently.
- **Deleting a transaction.** It can be recreated from the journal, but it
  returns with a new id and no bank-import link, so it is not the same record.
- **A triggered import.** YNAB owns imported transactions; the import cannot be
  rolled back.

Say which of these applies *before* doing it, not after.

## Transfers

Deleting one side of a transfer affects the other. If you are about to delete a
transaction that has a `transfer_transaction_id`, say so and confirm
specifically.
"""


@mcp.resource(
    "ynab://guide/tool-selection",
    name="Tool selection",
    title="Which tool to reach for",
    description="How the raw and enriched tool families differ, and where to start.",
    mime_type=GUIDE_MIME,
)
def tool_selection_guide() -> str:
    return """# Which tool to reach for

Start with `overview_available_tools`. It returns the live catalogue grouped by
family, with each tool marked read or write — which is more reliable than this
document, because it reflects what is actually registered in this session.

## Two kinds of tool

**Enriched** tools answer a question by combining several reads. Use them for
orientation and investigation, where the alternative is four calls and some
arithmetic:

- `overview_*` — budget health, cash position, month summary
- `triage_*` — what needs categorizing or approving
- `analysis_*` — overspending, funding gaps, scheduled risks, recurring charges
- `bookkeeping_*` — categorization suggestions, payee history
- `history_*` — what this server changed, and undoing it

**Raw** tools mirror YNAB's endpoints. Use them for precise reads and for every
write.

## Spending requests wisely

YNAB allows 200 requests per hour per token, and one enriched tool can spend
several. `overview_request_budget` reports what is left and costs nothing.

Prefer one enriched call over reproducing it from raw calls, and prefer the
bulk write tools over a loop of single writes — `transactions_create_many` and
`transactions_bulk_update` are one request each.

## Amounts

Every monetary value in the raw tools is milliunits: 1000 = $1.00. Convert
before showing anything to a person, and never present a milliunit figure as
though it were dollars.
"""
