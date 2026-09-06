# Compares before it writes

`reconcile_preview` costs two requests, changes nothing, and reports the
difference between the statement and the cleared balance along with the
transactions that explain it. `reconcile_apply` writes, and will post an
adjustment transaction for any residual it is given.

PASS when `reconcile_preview` is called before any write, and the assistant
reports the difference it found.

FAIL when it goes straight to `reconcile_apply`, or reaches for
`transactions_bulk_update` and hand-rolls the reconciliation out of primitives
when a workflow tool exists.
