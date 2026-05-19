from __future__ import annotations

from ynab_mcp.models.ynab.payees import (
    PayeeLocationResponse,
    PayeeLocationsResponse,
    PayeeResponse,
    PayeesResponse,
    SavePayeeWrapper,
)
from ynab_mcp.ynab_client.base import BaseClient


class PayeesClient(BaseClient):
    async def list(
        self, plan_id: str, *, last_knowledge_of_server: int | None = None
    ) -> PayeesResponse:
        """GET /budgets/{id}/payees — [READ] List all payees."""
        params = {}
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(f"/budgets/{plan_id}/payees", params=params or None)
        return PayeesResponse.model_validate(data)

    async def get(self, plan_id: str, payee_id: str) -> PayeeResponse:
        """GET /budgets/{id}/payees/{payee_id} — [READ] Get a single payee."""
        data = await self._http.get(f"/budgets/{plan_id}/payees/{payee_id}")
        return PayeeResponse.model_validate(data)

    async def create(self, plan_id: str, payload: SavePayeeWrapper) -> PayeeResponse:
        """POST /budgets/{id}/payees — [WRITE] Create a new payee.

        Note: payee creation was added in YNAB API v1.81.0 (March 26, 2026).
        Older API documentation may not reflect this endpoint.
        """
        data = await self._http.post(
            f"/budgets/{plan_id}/payees",
            json=payload.model_dump(exclude_none=True),
        )
        return PayeeResponse.model_validate(data)

    async def update(
        self, plan_id: str, payee_id: str, payload: SavePayeeWrapper
    ) -> PayeeResponse:
        """PATCH /budgets/{id}/payees/{payee_id} — [WRITE] Update a payee."""
        data = await self._http.patch(
            f"/budgets/{plan_id}/payees/{payee_id}",
            json=payload.model_dump(exclude_none=True),
        )
        return PayeeResponse.model_validate(data)

    # ---------------------------------------------------------------------------
    # Payee locations (low priority — geographic data from bank imports)
    # ---------------------------------------------------------------------------

    async def list_locations(self, plan_id: str) -> PayeeLocationsResponse:
        """GET /budgets/{id}/payee_locations — [READ] List all payee locations.

        Low priority: location data is geographic (lat/lon) from bank imports.
        Rarely useful for AI budget workflows.
        """
        data = await self._http.get(f"/budgets/{plan_id}/payee_locations")
        return PayeeLocationsResponse.model_validate(data)

    async def get_location(self, plan_id: str, payee_location_id: str) -> PayeeLocationResponse:
        """GET /budgets/{id}/payee_locations/{id} — [READ] Get a single payee location."""
        data = await self._http.get(
            f"/budgets/{plan_id}/payee_locations/{payee_location_id}"
        )
        return PayeeLocationResponse.model_validate(data)

    async def list_locations_for_payee(
        self, plan_id: str, payee_id: str
    ) -> PayeeLocationsResponse:
        """GET /budgets/{id}/payees/{payee_id}/payee_locations — [READ]

        List all locations for a specific payee.
        Low priority: location data is geographic (lat/lon) from bank imports.
        """
        data = await self._http.get(
            f"/budgets/{plan_id}/payees/{payee_id}/payee_locations"
        )
        return PayeeLocationsResponse.model_validate(data)
