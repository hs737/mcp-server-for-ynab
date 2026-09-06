# Adds to the assignment instead of computing a new total

The server offers two ways to change a month's assignment: `budgeted`, which
replaces the amount, and `adjust_by`, which adds to it. Both cost the same,
because the tool reads the current amount either way to record what a revert
would restore. A caller that reads the amount itself first pays for that read on
top, and the value it read is the one most likely to be stale.

Neither is atomic — YNAB has no delta and no conditional write — so `adjust_by`
is not being scored here as a safety property, only as the cheaper and more
direct expression of "add $4,500".

PASS when the transcript shows either:

- `categories_update_for_month` called with `adjust_by: 4500000`, or
- `months_assign_many` called with an assignment carrying `adjust_by: 4500000`

FAIL when it:

- reads the current amount (`categories_get_for_month`, `months_get`,
  `months_range`) solely to compute a total, then writes `budgeted`
- writes `budgeted: 4500000`, which replaces the assignment rather than adding
  to it and is the destructive misreading of the request
