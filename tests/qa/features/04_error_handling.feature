# Family: error_handling
# These scenarios verify that the API returns structured errors in expected shapes.
# They do not test happy-path behavior — they test that errors are usable.
# All scenarios are safe (no writes). Auth scenarios use deliberately invalid creds.

@family:error_handling
Feature: Error Response Shapes

  @QA-ERR-001 @smoke
  Scenario: 401 error response has expected error structure
    # All 401 responses must include data.error with name and detail fields.
    # Clients parse this shape to surface auth errors. If the shape changes,
    # error handling in ynab_mcp/models/errors.py must be updated.
    # Expected: 401 with data.error.name (string), data.error.detail (string).

  @QA-ERR-002 @smoke
  Scenario: 404 error response has expected error structure
    # All 404 responses must include data.error. The name field must be "not_found"
    # or similar — it is used by YnabMcpError.from_ynab_response to classify errors.
    # Expected: 404 with data.error.name (string), data.error.id (string).

  @QA-ERR-003
  Scenario: Request with invalid budget id returns 404 not 500
    # A random invalid UUID should produce a 404, not a 500.
    # This verifies the API handles unknown IDs gracefully.
    # Expected: 404.

  @QA-ERR-004
  Scenario: POST transaction with missing required field returns 422
    # Sending an empty transaction body should produce a 422 validation error.
    # Expected: 422 with data.error present.

  @QA-ERR-005
  Scenario: Error response data.error.id is always a string
    # The error_id field is parsed by YnabMcpError.from_ynab_response.
    # If it ever comes back as an integer, that is a breaking contract change.
    # Expected: 401 or 404 with data.error.id as a string (not integer).
