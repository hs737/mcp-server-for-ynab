# One range call, not one call per month

YNAB has no range endpoint, so `months_get` is one request per month: twenty
months of it is a tenth of the hourly quota and about 1 MB of JSON, most of it
goal fields nobody reads. `months_range` answers the same question in one call,
and takes `category_ids` and `fields` to narrow it further.

PASS when the transcript uses `months_range` (or
`category_groups_summary_by_month`, or `analysis_flow_trace` for one category).

FAIL when it loops `months_get`, or calls `transactions_list_by_category` for
each month separately.
