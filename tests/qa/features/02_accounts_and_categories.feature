# Family: accounts_and_categories
# These scenarios verify the accounts and categories read paths.
# All scenarios require valid api_key and plan_id.

@family:accounts_and_categories
Feature: Accounts and Categories

  # -------------------------------------------------------------------------
  # Accounts
  # -------------------------------------------------------------------------

  @QA-ACCT-001 @smoke
  Scenario: List accounts returns accounts array with required fields
    # Verifies account list shape: id, name, type, balance, closed.
    # Expected: 200 with data.accounts as array; each entry has id and balance.

  @QA-ACCT-002
  Scenario: List accounts response contains server_knowledge for delta sync
    # Verifies the response includes server_knowledge for use in delta sync calls.
    # Expected: 200 with data.server_knowledge as integer.

  @QA-ACCT-003
  Scenario: Get non-existent account returns 404 with error shape
    # Expected: 404 with data.error present.

  # -------------------------------------------------------------------------
  # Categories
  # -------------------------------------------------------------------------

  @QA-CAT-001 @smoke
  Scenario: List categories returns category_groups array with nested categories
    # Verifies the nested category structure: data.category_groups[].categories[].
    # Expected: 200 with data.category_groups as non-empty array;
    # each group has categories array.

  @QA-CAT-002
  Scenario: List categories response includes budgeted activity and balance per category
    # Verifies that each category has the three core budget fields.
    # Expected: 200; at least one category has budgeted, activity, and balance (integers).

  @QA-CAT-003
  Scenario: Get non-existent category returns 404 with error shape
    # Expected: 404 with data.error present.

  @QA-CAT-004
  Scenario: Get current month returns month object with categories
    # Uses /months/current for convenience.
    # Expected: 200 with data.month.month (string) and data.month.categories (array).

  @QA-CAT-005
  Scenario: List months returns months array ordered by date
    # Expected: 200 with data.months as non-empty array; each entry has month field.
