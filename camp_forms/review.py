"""Human-in-the-loop review.

Loads saved drafts and walks you through each one: see the proposed values, what
needs your input, and how to submit. You approve, edit, or skip. Approving marks
the draft — it does not transmit anything anywhere.
"""

from __future__ import annotations

import glob
import json
import os

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from .orchestrator import DRAFTS_DIR

console = Console()

_CONF_STYLE = {"high": "green", "medium": "yellow", "low": "red"}


def _load_all() -> list[dict]:
    items = []
    for path in sorted(glob.glob(os.path.join(DRAFTS_DIR, "*.json"))):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        data["_path"] = path
        items.append(data)
    return items


def _save(data: dict) -> None:
    path = data.pop("_path")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    data["_path"] = path


def _show_draft(data: dict) -> None:
    triage = data["triage"]
    draft = data.get("draft")

    header = (
        f"[bold]{triage.get('camp_name') or 'Unknown camp'}[/bold]  "
        f"(child: {triage.get('child_name') or '—'})\n"
        f"{triage.get('summary', '')}\n"
        f"Deadline: [bold]{triage.get('deadline') or 'none stated'}[/bold]   "
        f"Urgency: {triage.get('urgency', '—')}   "
        f"Lives in: {triage.get('form_location', '—')}"
    )
    console.print(Panel(header, title=data["email"]["subject"], expand=False))

    if data["note"]:
        console.print(f"[italic]{data['note']}[/italic]\n")

    if not draft:
        return

    table = Table(title=draft["form_title"], show_lines=False)
    table.add_column("Field")
    table.add_column("Proposed value")
    table.add_column("Conf.")
    table.add_column("Source")
    table.add_column("Review?")
    for f in draft["filled"]:
        conf = f.get("confidence", "medium")
        table.add_row(
            f["label"],
            f["value"] or "[dim](blank)[/dim]",
            f"[{_CONF_STYLE.get(conf, 'white')}]{conf}[/]",
            f["source"],
            "[red]you[/red]" if f["needs_review"] else "ok",
        )
    console.print(table)

    if draft.get("open_questions"):
        console.print("\n[bold]Needs your input:[/bold]")
        for q in draft["open_questions"]:
            console.print(f"  • {q}")

    console.print(f"\n[bold]To submit:[/bold] {draft['submission_instructions']}\n")


def _edit_values(data: dict) -> None:
    draft = data.get("draft")
    if not draft:
        console.print("Nothing to edit for this item.")
        return
    for f in draft["filled"]:
        current = f["value"] or "(blank)"
        new = Prompt.ask(f"  {f['label']} [{current}]", default=f["value"])
        if new != f["value"]:
            f["value"] = new
            f["needs_review"] = False
            f["source"] = "human_edited"
    _save(data)
    console.print("[green]Saved your edits.[/green]")


def review(only_pending: bool = True) -> None:
    items = _load_all()
    if only_pending:
        items = [d for d in items if d["status"] in ("needs_review", "flagged_portal")]

    if not items:
        console.print("No drafts to review. Run `scan` (or `demo`) first.")
        return

    console.print(f"[bold]{len(items)} item(s) to review.[/bold]\n")
    for data in items:
        _show_draft(data)
        choice = Prompt.ask(
            "Action",
            choices=["approve", "edit", "skip", "quit"],
            default="approve",
        )
        if choice == "quit":
            break
        if choice == "edit":
            _edit_values(data)
            data["status"] = "approved"
            _save(data)
        elif choice == "approve":
            data["status"] = "approved"
            _save(data)
            console.print("[green]Approved — ready for you to submit.[/green]")
        else:
            console.print("[dim]Skipped.[/dim]")
        console.rule()


def summary() -> None:
    """One-line status of every draft on disk."""
    items = _load_all()
    if not items:
        console.print("No drafts yet.")
        return
    table = Table(title="Camp form drafts")
    table.add_column("Camp")
    table.add_column("Deadline")
    table.add_column("Status")
    table.add_column("Subject")
    for d in sorted(items, key=lambda x: (x["triage"].get("deadline") or "9999")):
        table.add_row(
            d["triage"].get("camp_name") or "—",
            d["triage"].get("deadline") or "—",
            d["status"],
            d["email"]["subject"][:50],
        )
    console.print(table)
