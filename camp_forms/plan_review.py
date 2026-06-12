"""Human-in-the-loop review of a summer plan.

The matcher-side analogue of review.py. Loads a saved plan and lets you walk the
schedule and adjust it week by week: swap a child's camp for another that fits
that week, clear a week to a gap, then approve. Like everywhere else here, this
only edits the saved proposal — it registers nothing.

Swaps are constrained to real options: for any (child, week) you can only pick a
camp that actually runs that week and that the Matcher judged the child eligible
for, ranked by fit so the best choices come first.
"""

from __future__ import annotations

import glob
import json
import os

from rich.console import Console
from rich.prompt import Prompt

from .models import Camp, ChildScores, ScheduledWeek, SummerPlan
from .planner import PLANS_DIR
from .plan_view import print_plan
from .preferences import child_names

console = Console()


# --- Loading / saving -------------------------------------------------------

def _plan_files() -> list[str]:
    return sorted(glob.glob(os.path.join(PLANS_DIR, "*.json")))


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    data["_path"] = path
    return data


def _save(data: dict, plan: SummerPlan, status: str) -> None:
    path = data["_path"]
    data["plan"] = plan.model_dump(mode="json")
    data["status"] = status
    payload = {k: v for k, v in data.items() if k != "_path"}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


# --- Editing helpers --------------------------------------------------------

def _eligible_scores(child_name: str, scores: list[ChildScores]) -> dict[str, int]:
    """camp_name -> fit_score for camps this child is eligible for."""
    return {
        s.camp_name: s.fit_score
        for cs in scores if cs.child_name == child_name
        for s in cs.scores if s.eligible
    }


def _alternatives(child_name: str, week: str, camps: list[Camp], scores: list[ChildScores]) -> list[tuple[Camp, int]]:
    """Camps that run `week` and that `child_name` is eligible for, best fit first."""
    fits = _eligible_scores(child_name, scores)
    options = [(c, fits[c.name]) for c in camps if week in c.weeks and c.name in fits]
    return sorted(options, key=lambda t: t[1], reverse=True)


def _recost(plan: SummerPlan) -> None:
    plan.total_cost = sum(w.cost for w in plan.weeks if w.status == "assigned" and w.cost is not None)


def _cell(plan: SummerPlan, child: str, week: str) -> ScheduledWeek | None:
    for w in plan.weeks:
        if w.child_name == child and w.week_start == week:
            return w
    return None


def _swap(plan: SummerPlan, camps: list[Camp], scores: list[ChildScores], names: list[str]) -> None:
    child = Prompt.ask("  Which child", choices=names)
    weeks = sorted({w.week_start for w in plan.weeks if w.child_name == child})
    if not weeks:
        console.print("  [dim]No weeks for that child.[/dim]")
        return
    week = Prompt.ask("  Which week", choices=weeks)

    cell = _cell(plan, child, week)
    if cell and cell.status == "blocked":
        console.print("  [dim]That week is blocked (you said no camp needed). Leaving it.[/dim]")
        return

    options = _alternatives(child, week, camps, scores)
    if not options:
        console.print("  [yellow]No eligible camp runs that week for this child.[/yellow]")
        return

    console.print(f"\n  Options for [bold]{child}[/bold], week of [bold]{week}[/bold]:")
    for i, (camp, fit) in enumerate(options, 1):
        price = f"${camp.price_per_week:.0f}" if camp.price_per_week is not None else "price ?"
        dist = f"{camp.distance_miles:.0f} mi" if camp.distance_miles is not None else "dist ?"
        flag = " [yellow](discovered — verify)[/yellow]" if camp.needs_review else ""
        console.print(f"    {i}. {camp.name} — fit {fit}, {price}, {dist}{flag}")
    console.print("    0. (leave this week as a gap)")

    choice = Prompt.ask("  Pick", choices=[str(i) for i in range(len(options) + 1)], default="1")
    pick = int(choice)

    if cell is None:
        cell = ScheduledWeek(week_start=week, child_name=child)
        plan.weeks.append(cell)

    if pick == 0:
        cell.camp_name = None
        cell.status = "gap"
        cell.fit_score = None
        cell.cost = None
        cell.rationale = "Set to a gap during review."
        cell.needs_review = False
    else:
        camp, fit = options[pick - 1]
        cell.camp_name = camp.name
        cell.status = "assigned"
        cell.fit_score = fit
        cell.cost = camp.price_per_week
        cell.rationale = "Chosen by you during review."
        cell.needs_review = camp.needs_review

    _recost(plan)
    console.print("  [green]Updated.[/green]\n")


# --- Entry point ------------------------------------------------------------

def review_plan(path: str | None = None) -> None:
    files = _plan_files()
    if not files:
        console.print("No saved plans. Run `python -m camp_forms plan` first.")
        return

    if path is None:
        path = files[-1]  # most recent
        if len(files) > 1:
            console.print(f"[dim]Reviewing the latest of {len(files)} plans: {os.path.basename(path)}[/dim]")
    elif not os.path.exists(path):
        console.print(f"No plan at {path}.")
        return

    data = _load(path)
    camps = [Camp(**c) for c in data.get("camps", [])]
    scores = [ChildScores(**s) for s in data.get("scores", [])]
    plan = SummerPlan(**data["plan"])
    names = child_names(data.get("preferences", {})) or sorted({w.child_name for w in plan.weeks})

    print_plan(plan, scores, names)

    while True:
        choice = Prompt.ask(
            "Action",
            choices=["swap", "clear", "show", "approve", "quit"],
            default="approve",
        )
        if choice == "quit":
            console.print("[dim]Left unchanged.[/dim]")
            return
        if choice == "show":
            print_plan(plan, scores, names)
        elif choice == "swap":
            _swap(plan, camps, scores, names)
        elif choice == "clear":
            child = Prompt.ask("  Which child", choices=names)
            weeks = sorted({w.week_start for w in plan.weeks if w.child_name == child})
            week = Prompt.ask("  Which week to clear", choices=weeks)
            cell = _cell(plan, child, week)
            if cell and cell.status != "blocked":
                cell.camp_name, cell.status, cell.fit_score, cell.cost = None, "gap", None, None
                cell.rationale, cell.needs_review = "Cleared during review.", False
                _recost(plan)
                console.print("  [green]Cleared to a gap.[/green]\n")
        elif choice == "approve":
            _save(data, plan, status="approved")
            console.print("[green]Plan approved and saved.[/green] Nothing is registered — "
                          "use the form pipeline (`scan` → `review`) to sign up for each chosen camp.")
            return
