"""Load the family profile and render it for the Filler agent.

The profile is the single source of truth the Filler draws from. Keeping it in
one YAML file means you update your kids' info once, not once per form.
"""

from __future__ import annotations

import os

import yaml

DEFAULT_PATH = os.path.join("config", "family_profile.yaml")


def load_profile(path: str = DEFAULT_PATH) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No family profile at {path}. Copy config/family_profile.example.yaml "
            f"to {path} and fill it in."
        )
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def render_profile(profile: dict) -> str:
    """Render the profile as compact YAML text for the prompt.

    We hand the model the structured profile verbatim rather than trying to
    pre-map fields — the Filler is responsible for matching profile keys to form
    labels, and it does that better with the whole picture in view.
    """
    return yaml.safe_dump(profile, sort_keys=False, allow_unicode=True).strip()
