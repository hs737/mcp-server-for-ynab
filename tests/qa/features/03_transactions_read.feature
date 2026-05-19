# Family: transactions_read
# These scenarios verify the transaction read paths.
# All scenarios are safe (read-only) and require api_key + plan_id.
# Scenarios tagged @write create durable data and require additional setup.

@family:transactions_read
Feature: Transaction Read Paths

  # -------------------------------------------------------------------------
  # List transactions — structure
  # -------------------------------------------------------------------------

  @QA-TXN-001 @smoke
  Scenario: List transactions returns transactions array with required fields
    # Verifies the basic list response shape.
    # Expected: 200 with data.transactions as array; each entry has id, date, amount.

  @QA-TXN-002
  Scenario: List transactions response includes server_knowledge integer
    # Required for delta sync to work correctly.
    # Expected: 200 with data.server_knowledge as integer.

  @QA-TXN-003
  Scenario: Transaction amounts are integers (milliunits, not floats)
    # YNAB amounts are always integers. A float in the response indicates a parsing bug.
    # Expected: 200; sampled transaction amount values are integers.

  # -------------------------------------------------------------------------
  # Filtering
  # -------------------------------------------------------------------------

  @QA-TXN-004
  Scenario: Filter by type=uncategorized returns only uncategorized transactions
    # All returned transactions should have null category_id.
    # Expected: 200 with data.transactions; all entries have category_id = null.

  @QA-TXN-005
  Scenario: Filter by type=unapproved returns only unapproved transactions
    # All returned transactions should have approved = false.
    # Expected: 200 with data.transactions; all entries have approved = false.

  @QA-TXN-006
  Scenario: Filter by since_date returns only on-or-after transactions
    # Verifies date filtering works correctly.
    # Expected: 200 with data.transactions; all entries have date >= since_date.

  # -------------------------------------------------------------------------
  # Get single transaction
  # -------------------------------------------------------------------------

  @QA-TXN-007
  Scenario: Get non-existent transaction returns 404 with error shape
    # Expected: 404 with data.error present.

  # -------------------------------------------------------------------------
  # Scheduled transactions
  # -------------------------------------------------------------------------

  @QA-SCHED-001 @smoke
  Scenario: List scheduled transactions returns scheduled_transactions array
    # Expected: 200 with data.scheduled_transactions as array.

  @QA-SCHED-002
  Scenario: Scheduled transaction entries have date_next and frequency fields
    # These fields are required for upcoming-risk analysis.
    # Expected: 200; non-empty list has date_next (string) and frequency (string).

  # -------------------------------------------------------------------------
  # Payees
  # -------------------------------------------------------------------------

  @QA-PAYEE-001 @smoke
  Scenario: List payees returns payees array
    # Expected: 200 with data.payees as array.

  @QA-PAYEE-002
  Scenario: Get non-existent payee returns 404
    # Expected: 404 with data.error present.
