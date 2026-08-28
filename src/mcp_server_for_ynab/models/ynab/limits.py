"""Field length limits from YNAB's API specification.

Enforced locally so an over-long memo comes back as a validation error naming
the field, rather than as a 400 from YNAB relayed through two layers. It also
matters for bulk writes: YNAB rejects the whole request, so one over-long memo
in a batch of forty fails the other thirty-nine, and finding out before the
request is sent is the difference between a clear message and a partial write
the caller has to reconstruct.

The two payee limits genuinely differ. YNAB caps `payee_name` at 200 on the
transaction endpoints, while the payee resource itself allows 500.
"""

from __future__ import annotations

# Transaction and scheduled-transaction endpoints.
TRANSACTION_PAYEE_NAME_MAX = 200
MEMO_MAX = 500

# Payee resource endpoints.
PAYEE_NAME_MAX = 500

# Category and category-group endpoints.
CATEGORY_GROUP_NAME_MAX = 50
CATEGORY_NAME_MAX = 50
