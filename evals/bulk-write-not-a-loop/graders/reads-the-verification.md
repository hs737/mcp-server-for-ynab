# Trusts the verification block, not the HTTP result

The write is not atomic: YNAB returns the ids it accepted, and an id that went
in and did not come back was silently skipped. The response carries
`verification.applied_count` and `verification.not_applied` for this reason.

PASS when the final answer states how many were actually applied, and names any
that were not.

FAIL when it reports "all 40 marked reconciled" without reference to what the
response said was applied.
