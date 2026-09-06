# Reports the result without a confirming re-read

Every assignment write returns `previous_budgeted`, `budgeted` and `change`,
precisely so the caller can state the outcome without spending another request.

PASS when the final answer gives the new assigned total, and the transcript
contains no read of that category issued after the write.

FAIL when the assistant re-reads the category to find out what it just wrote, or
reports the change without saying what the category now holds.
