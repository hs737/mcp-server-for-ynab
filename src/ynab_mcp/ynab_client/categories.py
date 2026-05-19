from __future__ import annotations

from ynab_mcp.models.ynab.categories import (
    CategoriesResponse,
    CategoryGroupResponse,
    CategoryResponse,
    MonthCategoryResponse,
    SaveCategoryGroupWrapper,
    SaveCategoryWrapper,
)
from ynab_mcp.ynab_client.base import BaseClient


class CategoriesClient(BaseClient):
    async def list(
        self, plan_id: str, *, last_knowledge_of_server: int | None = None
    ) -> CategoriesResponse:
        """GET /budgets/{id}/categories — [READ] List all categories grouped by category group.

        Note: category group listing is embedded here — YNAB returns categories
        already grouped. There is no standalone 'list category groups' endpoint.
        """
        params = {}
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(f"/budgets/{plan_id}/categories", params=params or None)
        return CategoriesResponse.model_validate(data)

    async def get(self, plan_id: str, category_id: str) -> CategoryResponse:
        """GET /budgets/{id}/categories/{category_id} — [READ] Get a single category."""
        data = await self._http.get(f"/budgets/{plan_id}/categories/{category_id}")
        return CategoryResponse.model_validate(data)

    async def get_for_month(
        self, plan_id: str, month: str, category_id: str
    ) -> MonthCategoryResponse:
        """GET /budgets/{id}/months/{month}/categories/{category_id} — [READ]

        Get category data for a specific month, including budgeted/activity/balance
        values as of that month.
        """
        data = await self._http.get(
            f"/budgets/{plan_id}/months/{month}/categories/{category_id}"
        )
        return MonthCategoryResponse.model_validate(data)

    async def create(self, plan_id: str, payload: SaveCategoryWrapper) -> CategoryResponse:
        """POST /budgets/{id}/categories — [WRITE] Create a new category."""
        data = await self._http.post(
            f"/budgets/{plan_id}/categories",
            json=payload.model_dump(exclude_none=True),
        )
        return CategoryResponse.model_validate(data)

    async def update(
        self, plan_id: str, category_id: str, payload: SaveCategoryWrapper
    ) -> CategoryResponse:
        """PATCH /budgets/{id}/categories/{category_id} — [WRITE] Update a category."""
        data = await self._http.patch(
            f"/budgets/{plan_id}/categories/{category_id}",
            json=payload.model_dump(exclude_none=True),
        )
        return CategoryResponse.model_validate(data)

    async def update_for_month(
        self, plan_id: str, month: str, category_id: str, payload: SaveCategoryWrapper
    ) -> MonthCategoryResponse:
        """PATCH /budgets/{id}/months/{month}/categories/{category_id} — [WRITE]

        Update a category's budgeted amount for a specific month.
        """
        data = await self._http.patch(
            f"/budgets/{plan_id}/months/{month}/categories/{category_id}",
            json=payload.model_dump(exclude_none=True),
        )
        return MonthCategoryResponse.model_validate(data)

    async def create_group(
        self, plan_id: str, payload: SaveCategoryGroupWrapper
    ) -> CategoryGroupResponse:
        """POST /budgets/{id}/category-groups — [WRITE] Create a new category group."""
        data = await self._http.post(
            f"/budgets/{plan_id}/category-groups",
            json=payload.model_dump(exclude_none=True),
        )
        return CategoryGroupResponse.model_validate(data)

    async def update_group(
        self, plan_id: str, category_group_id: str, payload: SaveCategoryGroupWrapper
    ) -> CategoryGroupResponse:
        """PATCH /budgets/{id}/category-groups/{id} — [WRITE] Update a category group.

        Note: YNAB does not support deleting category groups directly.
        """
        data = await self._http.patch(
            f"/budgets/{plan_id}/category-groups/{category_group_id}",
            json=payload.model_dump(exclude_none=True),
        )
        return CategoryGroupResponse.model_validate(data)
