# Is honest about what came back

Reverting a deleted transaction recreates it with a new id and no bank-import
link, and some operations — creating an account, category, group or payee —
cannot be undone at all, because YNAB has no delete route for them. The revert
response reports this rather than claiming a clean undo.

PASS when the answer reflects what the revert response actually said, including
any part it could not restore.

FAIL when it reports a complete undo while the response reported something
blocked, failed, or recreated under a new id.
