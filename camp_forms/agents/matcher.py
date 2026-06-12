"""Matcher agent.

Scores every candidate camp for one child, given the family's preferences. It's a
focused Claude call (structured output) that weighs interests, eligibility, the
hard logistics (hours vs. your drop-off/pickup window, before/aftercare, lunch,
ratio), distance — as a *soft* penalty a great camp can overcome — and the social
signals (friends, keeping siblings together).

It does NOT decide the summer; it just ranks fit. The Scheduler assembles the
actual week-by-week plan from these scores.
"""

from __future__ import annotations

from ..llm import parse_structured
from ..models import Camp, ChildScores

SYSTEM = """You help a parent choose summer camps. For ONE child, score every camp
for fit and rank them best-first.

Weigh, in roughly this order:
  1. Eligibility — does the child meet the camp's age/grade requirement? If not,
     set eligible=false and a low fit_score; never schedule an ineligible child.
  2. Interest fit — match the camp's focus to the child's interests; penalize
     things on their "avoid" list and honor past favorites.
  3. Hard logistics — the camp's hours must fit the family's drop-off/pickup
     window; respect before/aftercare needs, lunch preference, and the ratio
     floor. A camp that can't be made to work on logistics is a poor fit even if
     the activities are perfect — say so.
  4. Distance — treat the family's max-distance as a SOFT preference. Apply a
     penalty for going farther, but if "farther_ok_if_great" is set, a clearly
     excellent camp can still score well despite distance. Explain the trade-off.
  5. Social — if the child wants to be with a named friend, or the family wants
     siblings kept together, treat that as a POSITIVE signal but you cannot know
     whether the friend is actually enrolled. Note it in social_note and add a
     concern that the family must confirm it. Never assume a friendship holds.

Be honest about uncertainty. A camp with unknown details (e.g. a discovered camp
flagged for review) should carry lower confidence and a concern to verify it.
Output a CampScore for every camp provided, ranked best-first."""


def score_camps_for_child(child: dict, camps: list[Camp], preferences_text: str) -> ChildScores:
    from ..catalog import render_camps

    name = child.get("name", "this child")
    user = (
        f"FAMILY PREFERENCES (constraints + all children for context):\n"
        f"{preferences_text}\n\n"
        f"SCORE CAMPS FOR THIS CHILD: {name}\n"
        f"(Use the per-child entry above for {name}'s interests, temperament, "
        f"friends, and any keep-with-sibling preference.)\n\n"
        f"CANDIDATE CAMPS:\n{render_camps(camps)}"
    )
    result = parse_structured(SYSTEM, user, ChildScores, max_tokens=8000)
    result.child_name = result.child_name or name
    return result
