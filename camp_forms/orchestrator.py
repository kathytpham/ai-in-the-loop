"""Coordinates the agents and persists drafts.

This is the "coordinator" of the multi-agent system. It doesn't do any reasoning
itself — it routes each email through Triage -> Extract -> Fill and writes the
result to data/drafts/ for the review step.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import gmail_client
from .agents import extract_form, fill_form, triage_email
from .models import CampEmail, FormDraft, FormLocation, TriageResult
from .profile import load_profile, render_profile

DRAFTS_DIR = os.path.join("data", "drafts")


@dataclass
class PipelineItem:
    """Everything we learned about one email, persisted as one draft file."""

    email: CampEmail
    triage: TriageResult
    draft: FormDraft | None = None
    status: str = "needs_review"  # needs_review | flagged_portal | not_actionable
    note: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def path(self) -> str:
        return os.path.join(DRAFTS_DIR, f"{self.email.message_id}.json")

    def save(self) -> None:
        os.makedirs(DRAFTS_DIR, exist_ok=True)
        payload = {
            "status": self.status,
            "note": self.note,
            "created_at": self.created_at,
            "email": self.email.model_dump(),
            "triage": self.triage.model_dump(mode="json"),
            "draft": self.draft.model_dump(mode="json") if self.draft else None,
        }
        with open(self.path(), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)


def process_email(email: CampEmail, profile_text: str, log=print) -> PipelineItem:
    log(f"  triaging: {email.subject!r}")
    triage = triage_email(email)

    if not triage.is_camp_related:
        return PipelineItem(email, triage, status="not_actionable", note="Not a camp form.")

    log(f"    -> camp form for {triage.camp_name or '?'} | lives in: {triage.form_location.value}")

    if triage.form_location == FormLocation.portal:
        return PipelineItem(
            email, triage, status="flagged_portal",
            note=f"Form is behind the {triage.portal_name or 'camp'} portal. "
                 "You'll need to log in; the draft below lists what to have ready.",
        )

    form = extract_form(email, triage)
    if form is None or not form.fields:
        return PipelineItem(
            email, triage, status="flagged_portal" if triage.form_location == FormLocation.portal else "not_actionable",
            note="Couldn't read the form automatically (login wall or unreadable page). "
                 "Open it manually; triage details above tell you where.",
        )

    log(f"    -> extracted {len(form.fields)} fields, drafting...")
    draft = fill_form(form, triage, profile_text)
    return PipelineItem(email, triage, draft=draft, status="needs_review")


def scan(emails: list[CampEmail], profile_path: str | None = None, log=print) -> list[PipelineItem]:
    profile = load_profile(profile_path) if profile_path else load_profile()
    profile_text = render_profile(profile)

    items: list[PipelineItem] = []
    for i, email in enumerate(emails, 1):
        log(f"[{i}/{len(emails)}] {email.subject!r}")
        try:
            item = process_email(email, profile_text, log=log)
        except Exception as exc:  # one bad email shouldn't sink the whole run
            item = PipelineItem(
                email,
                TriageResult(is_camp_related=False, summary="error during processing", reasoning=str(exc)),
                status="not_actionable",
                note=f"Error: {exc}",
            )
        item.save()
        items.append(item)
    return items


def scan_gmail(query: str, max_results: int, profile_path: str | None = None, log=print) -> list[PipelineItem]:
    log(f"Searching Gmail: {query}")
    emails = gmail_client.search(query, max_results=max_results)
    log(f"Found {len(emails)} candidate emails.\n")
    return scan(emails, profile_path=profile_path, log=log)
