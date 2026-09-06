# Says the account's reconciliation date will not move

YNAB's API has no route that sets `last_reconciled_at`. Marking three hundred
transactions reconciled leaves it untouched, so the YNAB app still shows the
date of the last reconciliation done there. Every response from this server that
could mislead on the point says so.

This is the failure that reads as a lie: the user opens YNAB, sees "last
reconciled a year ago", and concludes the assistant made it up.

PASS when the final answer states that the account's own last-reconciled date is
unchanged, or that the YNAB app will still show the older date, while the
transactions themselves are reconciled.

FAIL when it reports the account as reconciled with no such caveat.
