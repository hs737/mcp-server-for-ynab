# Reverts through the journal rather than writing the old value back

Every write records the state that preceded it, and `history_revert` restores
it. Writing a remembered value back is not the same thing: the assistant's
memory of the previous amount can be wrong, and the journal's is not.

PASS when the assistant finds the entry (`history_list` or the
`history_entry_id` returned by the write) and calls `history_revert` on it.

FAIL when it issues a fresh write with what it believes the old value was.
