# Asks what changed instead of reading everything again

Every list response carries `server_knowledge`, and `changes_since` turns that
into "what moved" across categories, months and transactions for three requests
regardless of how much changed. Re-reading a range costs one request per month
and still cannot say what is different.

PASS when the assistant calls `changes_since`, or passes
`last_knowledge_of_server` to a list tool.

FAIL when it re-reads the budget wholesale — `months_range` over the earlier
window, repeated `months_get`, or a full `transactions_list` — to refresh
itself.
