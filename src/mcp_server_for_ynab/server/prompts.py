"""Guided workflows, exposed as MCP prompts.

Tools are what the server can do; prompts are how someone finds out. Most
clients surface these as slash commands, so a person who has never read the
tool catalogue can pick "Monthly review" and get a competent pass over their
budget. That is a discovery mechanism the tool list cannot provide — nobody
browses sixty tool descriptions to work out where to start.

Each prompt returns instructions for the assistant, not an answer. They name
the tools to call and, more importantly, the traps: reading a net total as a
single charge, treating an approval count as proof a category write landed,
approving both halves of a credit card payment as ordinary spending.
"""

from __future__ import annotations

from mcp_server_for_ynab.server.app import mcp

_AMOUNTS = (
    "All amounts are milliunits: 1000 = $1.00. Convert them for the reader; "
    "never show a raw milliunit figure as if it were dollars."
)


@mcp.prompt(
    name="monthly_review",
    title="Monthly review",
    description="Walk this month's budget: health, overspending, and what needs attention.",
)
def monthly_review(month: str = "current") -> str:
    """Guided pass over a single budget month."""
    return f"""Review the {month} budget month and report what needs the user's attention.

Work in this order:

1. `overview_month_health` for income, budgeted, activity, and to-be-budgeted.
2. `analysis_overspent_categories` for categories that finished negative.
3. `analysis_target_funding_gaps` for targets that will not be met.
4. `triage_summary` for the size of the cleanup queue.

Then write a short report: how the month is going, what is overspent and by
how much, which targets are short, and what to do first. Lead with the one or
two things that actually matter rather than listing everything you found.

{_AMOUNTS}

Overspending in a prior month reduces this month's Ready to Assign, so if you
find it, say so explicitly — the cause is usually not visible in the current
month's numbers alone."""


@mcp.prompt(
    name="weekly_triage",
    title="Weekly triage",
    description="Clear the uncategorized and unapproved queues for the week.",
)
def weekly_triage() -> str:
    """Guided pass over the transaction cleanup queues."""
    return f"""Help the user clear their transaction queues.

1. `triage_summary` for the counts.
2. `triage_uncategorized` — these need a category before anything else.
3. `triage_unapproved` — these are waiting on review.

For each uncategorized transaction, suggest a category using
`bookkeeping_categorization_suggestions`, which bases its suggestion on how the
same payee was categorized before. Show the user your proposed categories and
wait for them to confirm before writing anything.

{_AMOUNTS}

Two things to be careful about:

- Do not approve anything the user has not seen. An imported transaction can be
  a duplicate, a wrong amount, or a payee they do not recognise, and approval is
  the step where that gets caught.
- If a pair of transactions looks like a credit card payment and the matching
  outflow from a checking account, they should be a transfer, not two
  categorized transactions. Flag the pair instead of approving it."""


@mcp.prompt(
    name="categorize_and_approve",
    title="Categorize and approve",
    description="Categorize uncategorized transactions, then approve what is ready.",
)
def categorize_and_approve(payee: str = "") -> str:
    """Guided categorize-then-approve pass, optionally scoped to one payee."""
    scope = f" Restrict this to transactions for the payee '{payee}'." if payee else ""
    return f"""Categorize and approve transactions for the user.{scope}

1. `triage_uncategorized` for what is missing a category.
2. `bookkeeping_categorization_suggestions` for each one, which looks at how the
   same payee was handled previously.
3. Present your proposed categories and wait for explicit confirmation.
4. Apply them with `transactions_update` or `transactions_bulk_update`.

{_AMOUNTS}

After writing, do not use the queue count as your success check. An approved
transaction leaves the unapproved queue whether or not its category write
landed, so a shrinking queue can hide a failed categorization. Read the
`verification` block the write tools return, and treat anything it reports as
failed as a real failure — re-read that transaction with `transactions_get`.

Every write is journaled. If the user wants any of it undone, `history_list`
shows what changed and `history_revert` reverses one entry."""


@mcp.prompt(
    name="subscription_audit",
    title="Subscription audit",
    description="Find recurring charges and what they cost per year.",
)
def subscription_audit(months: int = 12) -> str:
    """Guided review of recurring charges."""
    return f"""Find the user's recurring charges over the last {months} months and
report what they cost.

Use `analysis_recurring_charges` with months={months}. It groups by YNAB's payee
id and reports a cadence, a typical amount, and an estimated annual cost.

Present them sorted by annual cost, highest first. Call out anything that looks
worth questioning: a charge whose amount has risen, something that has not been
seen recently and may have lapsed, or a payee the user is unlikely to recognise.

{_AMOUNTS}

Be honest about confidence. A charge seen twice is a weaker signal than one
seen twelve times on a steady cadence, and the tool reports how many times it
saw each one — carry that into what you say rather than presenting every row
as an established subscription."""


@mcp.prompt(
    name="cash_position",
    title="Cash position",
    description="Summarize balances across every account.",
)
def cash_position() -> str:
    """Guided account balance summary."""
    return f"""Summarize the user's cash position.

Use `overview_cash_position` for on-budget, off-budget, and per-account
balances, and `accounts_list` if you need account detail beyond that.

Report on-budget and off-budget totals separately — they answer different
questions, and combining them overstates what is actually available to spend.
Note any account with a negative balance, and treat credit card balances as
money owed rather than money held.

{_AMOUNTS}"""


@mcp.prompt(
    name="undo_last_changes",
    title="Review and undo recent changes",
    description="Show what this server changed, and reverse it if asked.",
)
def undo_last_changes() -> str:
    """Guided review of the write journal."""
    return """Show the user what this server has changed in their budget.

1. `history_list` for recent writes, newest first, each marked revertible or not.
2. `history_show` for the full before-and-after of anything they ask about.

If they want something undone, use `history_revert` for a single entry, or
`history_revert_to` to roll back everything after a chosen point.

Be clear about what cannot be undone. YNAB has no delete route for accounts,
categories, category groups, or payees, so creating one is permanent; those
entries are marked non-revertible with the reason. A recreated transaction also
gets a new id and loses any bank-import link, so it is not identical to the one
that was deleted. Say so before reverting rather than after."""
