"""Render a proposed summer plan for the human to review.

The matcher-side analogue of review.py's draft view. It prints the week-by-week
grid (children as columns, weeks as rows), the per-child top picks with the
matcher's reasoning, the trade-offs the scheduler made, and the open questions
only you can answer. It changes nothing — you read it and decide.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import ChildScores, SummerPlan

console = Console()

_STATUS_STYLE = {
    "assigned": "green",
    "gap": "red",
    "blocked": "dim",
    "conflict": "yellow",
}


def print_plan(plan: SummerPlan, scores: list[ChildScores], child_names: list[str]) -> None:
    # --- The week-by-week grid: weeks down, children across ------------------
    weeks = sorted({w.week_start for w in plan.weeks})
    by_cell = {(w.week_start, w.child_name): w for w in plan.weeks}

    grid = Table(title="Proposed summer schedule", show_lines=True)
    grid.add_column("Week")
    for name in child_names:
        grid.add_column(name)
    for week in weeks:
        row = [week]
        for name in child_names:
            cell = by_cell.get((week, name))
            if cell is None:
                row.append("[dim]—[/dim]")
                continue
            style = _STATUS_STYLE.get(cell.status, "white")
            if cell.status == "assigned" and cell.camp_name:
                label = cell.camp_name
                if cell.fit_score is not None:
                    label += f"\n[dim]fit {cell.fit_score}" + (
                        f", ${cell.cost:.0f}" if cell.cost is not None else ""
                    ) + "[/dim]"
                if cell.needs_review:
                    label += "\n[yellow]confirm[/yellow]"
            else:
                label = f"[{style}]{cell.status}[/{style}]"
            row.append(label)
        grid.add_row(*row)
    console.print(grid)

    # --- Coverage / cost summary --------------------------------------------
    summary = plan.coverage_summary or ""
    if plan.total_cost is not None:
        summary += f"\nEstimated total: [bold]${plan.total_cost:.0f}[/bold]"
    if summary:
        console.print(Panel(summary.strip(), title="Coverage", expand=False))

    if plan.tradeoffs:
        console.print("\n[bold]Trade-offs the plan made:[/bold]")
        for t in plan.tradeoffs:
            console.print(f"  • {t}")

    if plan.gaps:
        console.print("\n[bold red]Uncovered weeks:[/bold red]")
        for g in plan.gaps:
            console.print(f"  • {g}")

    if plan.open_questions:
        console.print("\n[bold]Needs your decision/confirmation:[/bold]")
        for q in plan.open_questions:
            console.print(f"  • {q}")

    if plan.alternatives:
        console.print(f"\n[bold]Worth knowing:[/bold] {plan.alternatives}")

    # --- Per-child top picks with the matcher's reasoning -------------------
    for cs in scores:
        top = [s for s in cs.scores if s.eligible][:3]
        if not top:
            continue
        table = Table(title=f"Top picks for {cs.child_name}")
        table.add_column("Camp")
        table.add_column("Fit")
        table.add_column("Why")
        table.add_column("Confirm?")
        for s in top:
            confirm = "[yellow]" + "; ".join(s.concerns) + "[/yellow]" if s.concerns else "ok"
            table.add_row(s.camp_name, str(s.fit_score), s.activity_match, confirm)
        console.print(table)

    console.print(
        "\n[italic]This is a proposal — nothing is registered. Once you choose, the "
        "form pipeline (scan → review) handles each signup.[/italic]\n"
    )
