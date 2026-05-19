# Family: auth_and_plans
# These scenarios verify authentication behavior and plan listing.
# All scenarios in this file make real API calls and require a valid api_key.
# Plan-scoped scenarios additionally require plan_id.

@family:auth_and_plans
Feature: Authentication and Plan Discovery

  # -------------------------------------------------------------------------
  # Authentication
  # -------------------------------------------------------------------------

  @QA-AUTH-001 @smoke
  Scenario: Valid PAT returns authenticated user object
    # Verifies the API key is accepted and returns a user record.
    # Expected: 200 with data.user.id (string).

  @QA-AUTH-002 @smoke
  Scenario: Missing Authorization header returns 401 with error shape
    # Verifies that the API rejects unauthenticated requests with a structured error.
    # Expected: 401 with data.error.name and data.error.detail.

  @QA-AUTH-003
  Scenario: Invalid PAT returns 401 with error shape
    # Uses a deliberately invalid token to verify error structure.
    # Expected: 401 with data.error.id (string) set.

  # -------------------------------------------------------------------------
  # Plans
  # -------------------------------------------------------------------------

  @QA-PLANS-001 @smoke
  Scenario: List plans returns non-empty budgets array
    # Verifies the user has at least one accessible budget.
    # Expected: 200 with data.budgets as a non-empty array.

  @QA-PLANS-002 @smoke
  Scenario: Get plan returns budget with required top-level fields
    # Verifies that a plan detail response contains the required structural fields.
    # Expected: 200 with data.budget.id, data.budget.name, data.server_knowledge.

  @QA-PLANS-003
  Scenario: Get plan settings returns currency format object
    # Verifies that the settings endpoint returns a parseable currency format.
    # Expected: 200 with data.settings.currency_format.iso_code (string).

  @QA-PLANS-004
  Scenario: Get non-existent plan returns 404 with error shape
    # Uses a known-invalid plan ID to verify 404 error structure.
    # Expected: 404 with data.error.name = "not_found".
