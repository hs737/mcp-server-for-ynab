# Checks the months rather than reasoning from one example

`analysis_unassigned_transfers` pairs transfers between on-budget accounts
against what the named groups were assigned in the same month, and flags the
months where money moved and nothing was assigned.

PASS when the assistant uses `analysis_unassigned_transfers`, or reads
assignments per month (`months_range`, `category_groups_summary_by_month`) to
confirm which months were actually short.

FAIL when it answers from the transfer list alone without establishing what was
assigned.
