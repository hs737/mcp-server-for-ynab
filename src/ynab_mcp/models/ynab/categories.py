from __future__ import annotations

from enum import Enum

from ynab_mcp.models.ynab.common import YnabBaseModel


class GoalType(str, Enum):
    TARGET_BALANCE = "TB"
    TARGET_BALANCE_BY_DATE = "TBD"
    MONTHLY_FUNDING = "MF"
    PLAN_YOUR_SPENDING = "NEED"
    DEBT = "DEBT"


class Category(YnabBaseModel):
    id: str
    category_group_id: str
    category_group_name: str | None = None
    name: str
    hidden: bool
    original_category_group_id: str | None = None
    note: str | None = None
    budgeted: int  # milliunits
    activity: int  # milliunits
    balance: int  # milliunits
    goal_type: GoalType | None = None
    goal_day: int | None = None
    goal_cadence: int | None = None
    goal_cadence_frequency: int | None = None
    goal_creation_month: str | None = None
    goal_target: int | None = None  # milliunits
    goal_target_month: str | None = None
    goal_percentage_complete: int | None = None
    goal_months_to_budget: int | None = None
    goal_under_funded: int | None = None  # milliunits
    goal_overall_funded: int | None = None  # milliunits
    goal_overall_left: int | None = None  # milliunits
    deleted: bool


class CategoryGroup(YnabBaseModel):
    id: str
    name: str
    hidden: bool
    deleted: bool
    categories: list[Category]


class CategoriesResponse(YnabBaseModel):
    data: CategoriesData


class CategoriesData(YnabBaseModel):
    category_groups: list[CategoryGroup]
    server_knowledge: int


class CategoryResponse(YnabBaseModel):
    data: CategoryData


class CategoryData(YnabBaseModel):
    category: Category


class SaveCategory(YnabBaseModel):
    name: str | None = None
    note: str | None = None
    budgeted: int | None = None  # milliunits


class SaveCategoryWrapper(YnabBaseModel):
    category: SaveCategory


class SaveCategoryGroup(YnabBaseModel):
    name: str


class SaveCategoryGroupWrapper(YnabBaseModel):
    category_group: SaveCategoryGroup


class CategoryGroupResponse(YnabBaseModel):
    data: CategoryGroupData


class CategoryGroupData(YnabBaseModel):
    category_group: CategoryGroup


class MonthCategory(Category):
    """Category as returned in a month context — same shape."""


class MonthCategoryResponse(YnabBaseModel):
    data: MonthCategoryData


class MonthCategoryData(YnabBaseModel):
    category: Category
