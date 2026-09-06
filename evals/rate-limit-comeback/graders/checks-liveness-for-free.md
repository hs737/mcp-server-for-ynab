# Checks liveness without spending the quota it is waiting on

`ping` costs no YNAB request and needs no credentials.
`overview_request_budget` also costs nothing. Every other tool spends from the
window the assistant is waiting out.

PASS when the reachability check is `ping` (or `overview_request_budget`).

FAIL when it probes with a data call such as `overview_budget_snapshot`,
`accounts_list` or `plans_list`.
