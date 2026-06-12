"""Scheduler agent.

Takes the Matcher's per-child scores and assembles the actual summer: a week-by-
week assignment for every child that covers the weeks you need, never double-books
a child, stays within budget, and skips the weeks you've blocked out. It's a
focused Claude call (structured output) that does the constraint reasoning and,
crucially, *explains its trade-offs* and flags anything only you can decide.

Nothing here registers a child for anything. The output is a proposal you review;
once you pick, the form pipeline (triage → extract → fill) handles the signup.
"""

from __future__ import annotations

from ..llm import parse_structured
from ..models import Camp, ChildScores, SummerPlan

SYSTEM = """You assemble a family's summer camp schedule from per-child camp
scores the matcher already produced.

Hard rules:
  - Cover exactly the weeks listed in the preferences. Do NOT assign anything for
    a child on a blocked_week — mark those status="blocked".
  - A child can attend at most ONE camp per week (never double-book).
  - Only assign a camp in a week the camp actually offers (see each camp's weeks)
    and only to a child the matcher marked eligible.
  - Respect the budget: keep within total_summer if given, and prefer options
    under the per-week cap. If covering every week is impossible within budget,
    leave the least-important weeks as gaps rather than blowing the budget — and
    say which weeks and why.

Optimize for:
  - High overall fit (use fit_score), good coverage of the required weeks, and
    keeping siblings at the same camp/site in the same week when the family wants
    that and it doesn't badly hurt fit (one drop-off beats two).
  - Variety across the summer where a child has several strong options, unless
    they clearly prefer routine.

When you intentionally pick a farther or pricier camp because it's clearly better,
record it in tradeoffs. Put anything the family must confirm (a friend's actual
enrollment, an unverified discovered camp, a week you couldn't cover) into
open_questions. Fill coverage_summary in plain language and total_cost as the sum
of assigned weeks. Produce a ScheduledWeek for every (child, required-week) pair."""


def build_schedule(
    preferences_text: str,
    camps: list[Camp],
    all_scores: list[ChildScores],
) -> SummerPlan:
    from ..catalog import render_camps

    scores_block = "\n\n".join(
        f"### {cs.child_name}\n"
        + "\n".join(
            f"- {s.camp_name}: fit={s.fit_score}, eligible={s.eligible}, "
            f"conf={s.confidence.value}; {s.activity_match} "
            f"{('CONCERNS: ' + '; '.join(s.concerns)) if s.concerns else ''}".strip()
            for s in cs.scores
        )
        for cs in all_scores
    )

    user = (
        f"FAMILY PREFERENCES (weeks to cover, blocked weeks, budget, logistics):\n"
        f"{preferences_text}\n\n"
        f"CAMPS (for weeks offered, price, distance, hours):\n{render_camps(camps)}\n\n"
        f"PER-CHILD CAMP SCORES (from the matcher, ranked best-first):\n{scores_block}\n\n"
        f"Assemble the summer schedule."
    )
    return parse_structured(SYSTEM, user, SummerPlan, max_tokens=8000)
