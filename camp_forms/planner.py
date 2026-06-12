"""Coordinates the camp-matching agents and persists the plan.

The matcher-side analogue of orchestrator.py. It doesn't reason itself — it loads
your preferences and camps catalog, optionally runs web discovery to widen the
field, scores every camp per child (Matcher), assembles the summer (Scheduler),
and writes the result to data/plans/ for review.

As everywhere in this project: nothing is registered. The plan is a proposal.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .agents import build_schedule, discover_camps, score_camps_for_child
from .catalog import load_catalog, save_catalog
from .models import Camp, ChildScores, SummerPlan
from .preferences import load_preferences, render_preferences

PLANS_DIR = os.path.join("data", "plans")


@dataclass
class PlanResult:
    """Everything one planning run produced, persisted as one plan file."""

    preferences: dict
    camps: list[Camp]
    scores: list[ChildScores]
    plan: SummerPlan
    discovered: list[Camp] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def path(self) -> str:
        stamp = self.created_at.replace(":", "").replace("-", "")[:15]
        return os.path.join(PLANS_DIR, f"plan-{stamp}.json")

    def save(self) -> str:
        os.makedirs(PLANS_DIR, exist_ok=True)
        payload = {
            "created_at": self.created_at,
            "camps": [c.model_dump(mode="json") for c in self.camps],
            "discovered": [c.model_dump(mode="json") for c in self.discovered],
            "scores": [s.model_dump(mode="json") for s in self.scores],
            "plan": self.plan.model_dump(mode="json"),
        }
        path = self.path()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        return path


def make_plan(
    preferences_path: str | None = None,
    catalog_path: str | None = None,
    discover: bool = False,
    save_discovered: bool = False,
    log=print,
) -> PlanResult:
    preferences = load_preferences(preferences_path)
    preferences_text = render_preferences(preferences)
    camps = load_catalog(catalog_path)
    log(f"Loaded {len(camps)} camps from the catalog.")

    discovered: list[Camp] = []
    if discover:
        log("Searching the web for more camps near you...")
        result = discover_camps(preferences_text)
        discovered = result.camps
        log(f"  found {len(discovered)} candidate camp(s) — flagged for you to verify.")
        camps = camps + discovered
        if save_discovered and discovered:
            save_catalog(camps, catalog_path)
            log("  appended discovered camps to your catalog.")

    children = preferences.get("children", [])
    if not children:
        raise ValueError("No children listed in your preferences file.")

    scores: list[ChildScores] = []
    for child in children:
        name = child.get("name", "?")
        log(f"Scoring {len(camps)} camps for {name}...")
        scores.append(score_camps_for_child(child, camps, preferences_text))

    log("Assembling the summer schedule...")
    plan = build_schedule(preferences_text, camps, scores)

    result = PlanResult(
        preferences=preferences,
        camps=camps,
        scores=scores,
        plan=plan,
        discovered=discovered,
    )
    saved = result.save()
    log(f"Saved plan to {saved}")
    return result
