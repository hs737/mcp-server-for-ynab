"""Tool registry: stores metadata about all registered tools.

The ToolRegistry maintains a catalog of tool metadata (family, classification,
tool_type, priority) keyed by tool name. This data drives overview_available_tools
and helps agents navigate the tool surface.

Actual MCP tool registration is handled by FastMCP. The ToolRegistry is a
companion metadata store that runs alongside FastMCP's own tool list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from mcp_server_for_ynab.config.settings import writes_enabled

ToolClassification = Literal["read", "write"]
ToolType = Literal["raw", "enriched"]
ToolPriority = Literal["standard", "low"]


@dataclass
class ToolMeta:
    name: str
    family: str
    classification: ToolClassification
    tool_type: ToolType
    summary: str
    priority: ToolPriority = "standard"


@dataclass
class ToolRegistry:
    _tools: dict[str, ToolMeta] = field(default_factory=dict)

    def register(
        self,
        name: str,
        family: str,
        classification: ToolClassification,
        tool_type: ToolType,
        summary: str,
        priority: ToolPriority = "standard",
    ) -> None:
        # Write tools are not registered with FastMCP when writes are disabled,
        # so they must not appear in the catalog either. Advertising a tool an
        # agent cannot call wastes its time and misleads the user.
        if classification == "write" and not writes_enabled():
            return

        self._tools[name] = ToolMeta(
            name=name,
            family=family,
            classification=classification,
            tool_type=tool_type,
            summary=summary,
            priority=priority,
        )

    def all(self) -> list[ToolMeta]:
        return list(self._tools.values())

    def by_family(self) -> dict[str, list[ToolMeta]]:
        result: dict[str, list[ToolMeta]] = {}
        for meta in self._tools.values():
            result.setdefault(meta.family, []).append(meta)
        return result

    def get(self, name: str) -> ToolMeta | None:
        return self._tools.get(name)


# Module-level singleton used by all tool registration modules.
tool_registry = ToolRegistry()
