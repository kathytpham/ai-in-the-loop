"""Load the camp-matching preferences and render them for the agents.

This is the matcher's analogue of profile.py. Where the family *profile* says who
your family *is* (names, DOBs, medical info the Filler needs), the *preferences*
say what you *want* out of the summer: which weeks need covering, your budget, the
drop-off/pickup window, before/aftercare needs, and each child's interests,
temperament, and the friends they'd love to be with.

As with the profile, we hand the model the structured YAML verbatim rather than
pre-mapping it — the agents reason better with the whole picture in view.
"""

from __future__ import annotations

import os

import yaml

DEFAULT_PATH = os.path.join("config", "camp_preferences.yaml")


def load_preferences(path: str | None = None) -> dict:
    path = path or DEFAULT_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No camp preferences at {path}. Copy "
            f"config/camp_preferences.example.yaml to {path} and fill it in."
        )
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def render_preferences(preferences: dict) -> str:
    """Render preferences as compact YAML text for a prompt."""
    return yaml.safe_dump(preferences, sort_keys=False, allow_unicode=True).strip()


def child_names(preferences: dict) -> list[str]:
    return [c.get("name", "") for c in preferences.get("children", []) if c.get("name")]
