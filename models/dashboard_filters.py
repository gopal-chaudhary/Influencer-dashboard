"""Filter criteria used by the dashboard workflow."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DashboardFilters:
    """Capture the active dashboard filters and search criteria."""

    platform: str | None = None
    language: str | None = None
    niche: str | None = None
    min_followers: int = 0
    min_score: float = 0.0
    search_query: str = ""
