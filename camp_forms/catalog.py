"""Load the candidate-camps catalog.

The catalog is the set of camps the Matcher scores and the Scheduler draws from.
You maintain it as JSON (one entry per camp); the web-discovery agent can append
*proposed* camps to consider, which arrive flagged `needs_review` so you never
schedule around a camp whose details haven't been verified.
"""

from __future__ import annotations

import json
import os

from .models import Camp

DEFAULT_PATH = os.path.join("data", "camps_catalog.json")


def load_catalog(path: str | None = None) -> list[Camp]:
    path = path or DEFAULT_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No camps catalog at {path}. Copy data/camps_catalog.example.json to "
            f"{path} (or pass --catalog) and list the camps you're considering."
        )
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return [Camp(**c) for c in raw]


def save_catalog(camps: list[Camp], path: str | None = None) -> None:
    path = path or DEFAULT_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([c.model_dump(mode="json") for c in camps], fh, indent=2)


def render_camps(camps: list[Camp]) -> str:
    """Compact, prompt-friendly listing of the camps for the agents."""
    lines = []
    for c in camps:
        elig = _grade_age(c)
        weeks = ", ".join(c.weeks) if c.weeks else "weeks unknown"
        hours = f"{c.day_start or '?'}–{c.day_end or '?'}"
        care = []
        if c.before_care:
            care.append(f"before-care from {c.before_care_start or '?'}")
        if c.after_care:
            care.append(f"aftercare to {c.after_care_end or '?'}")
        care_s = "; ".join(care) if care else "no extended care"
        lunch = {True: "lunch provided", False: "pack lunch"}.get(c.lunch_provided, "lunch unknown")
        price = f"${c.price_per_week:.0f}/wk" if c.price_per_week is not None else "price unknown"
        dist = f"{c.distance_miles:.0f} mi" if c.distance_miles is not None else "distance unknown"
        flag = "  [DISCOVERED — verify]" if c.needs_review else ""
        lines.append(
            f"- {c.name} ({c.provider or 'independent'}){flag}\n"
            f"    focus: {', '.join(c.activities) or 'general'} | eligibility: {elig} | {dist}\n"
            f"    weeks: {weeks}\n"
            f"    hours: {hours}; {care_s} | {lunch} | ratio {c.ratio or '?'} | {price}"
            f"{' | ACA-accredited' if c.accredited else ''}\n"
            f"    {c.description}".rstrip()
        )
    return "\n".join(lines)


def _grade_age(c: Camp) -> str:
    parts = []
    if c.min_grade or c.max_grade:
        parts.append(f"grades {c.min_grade or '?'}–{c.max_grade or '?'}")
    if c.min_age or c.max_age:
        parts.append(f"ages {c.min_age or '?'}–{c.max_age or '?'}")
    return ", ".join(parts) if parts else "any age"
