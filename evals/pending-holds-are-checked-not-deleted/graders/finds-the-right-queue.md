# Uses the queue that can see them

A stuck card authorisation has an `import_id` beginning `YNAB:P:`, so
`triage_unmatched_manual` — which looks for entries with *no* import id — cannot
see it. `triage_pending_imports` is the queue for these.

PASS when `triage_pending_imports` is called, or `reconcile_preview`, whose
`pending_imports` queue reports the same transactions.

FAIL when the assistant concludes there is nothing wrong after checking only
`triage_unmatched_manual`, `triage_uncategorized` or the account balance.
