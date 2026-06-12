"""Triage agent.

Reads one email and decides: is this a camp form we need to act on, who/when is
it for, and — crucially — *where the form lives* (inline, a public website, or
behind a portal login). That last call routes the rest of the pipeline.
"""

from __future__ import annotations

from ..llm import parse_structured
from ..models import CampEmail, TriageResult

SYSTEM = """You triage a parent's incoming email about children's summer camps.

Decide whether this email is asking the parent to fill out or submit a form
(registration, waiver, medical/health form, permission slip, enrollment, payment
authorization, etc.). General newsletters, marketing, and receipts are NOT
form-related.

If it is form-related, determine where the form actually lives:
  - inline_email:   the fields to fill are written directly in the email body
                    (e.g. "reply with your child's name, DOB, allergies"), or the
                    email contains the actual form content.
  - public_website: the email links to a form/page you could open without logging in.
  - portal:         the form is behind a login (a camp portal, CampMinder, CampDoc,
                    UltraCamp, Jotform account, etc.).
  - unknown:        form-related but you can't tell where it is.

Extract a deadline as an ISO date (YYYY-MM-DD) only if one is stated or clearly
implied. Pick the single most relevant form URL if several appear. Be precise and
do not invent details that aren't in the email."""


def triage_email(email: CampEmail) -> TriageResult:
    user = (
        f"From: {email.sender}\n"
        f"Subject: {email.subject}\n"
        f"Date: {email.received}\n\n"
        f"Body:\n{email.best_body()}"
    )
    return parse_structured(SYSTEM, user, TriageResult)
