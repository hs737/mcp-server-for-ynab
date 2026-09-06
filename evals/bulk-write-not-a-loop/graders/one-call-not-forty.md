# One bulk call, not one call per transaction

YNAB allows about 200 requests per hour per token, shared with the user's own
YNAB apps. Forty single updates is a fifth of the hour for work that costs two
requests done properly, and this is the exact pattern that produced four
rate-limit lockouts in the session this server was built from.

PASS when the transcript shows a single `transactions_bulk_update` (or
`reconcile_apply`) carrying all forty ids.

FAIL when it calls `transactions_update` repeatedly, or splits the batch into
several bulk calls without a stated reason such as a validation error on the
first attempt.
