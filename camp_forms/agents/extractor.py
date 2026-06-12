"""Extractor agent.

Given a triaged email, produce the list of fields the form is asking for.

  - inline_email   -> read the fields straight out of the email body.
  - public_website -> use Claude's server-side web_fetch to open the page and
                      read the form, then structure it.
  - portal         -> we can't (and shouldn't) log in for you. Return None so the
                      orchestrator hands it to you with guidance instead.
"""

from __future__ import annotations

from typing import Optional

from ..llm import parse_structured, run_with_tools
from ..models import CampEmail, ExtractedForm, FormLocation, TriageResult

INLINE_SYSTEM = """You extract the list of fields a camp form is requesting from an
email body. Output each distinct piece of information the parent must provide as a
field with a sensible type (text, date, email, phone, number, select, checkbox,
signature, file). Mark a field required only if the email indicates it is. Do not
invent fields that aren't asked for."""

WEB_SYSTEM = """You are reading a camp registration/health/waiver form on the web.
Use web_fetch to open the given URL (use web_search first only if you must locate
the form from a camp name). Then list every field the form asks the parent to fill
in: the visible label, a sensible field type, whether it's required, and the
options for any dropdowns/checkboxes. Report what the form actually contains; if
the page is a login wall or you cannot read the form, say so plainly."""

STRUCTURE_SYSTEM = """Convert the following description of a camp form into the
structured schema. Keep field labels as they appear. Do not add fields that aren't
described."""


def extract_form(email: CampEmail, triage: TriageResult) -> Optional[ExtractedForm]:
    if triage.form_location == FormLocation.inline_email:
        form = parse_structured(
            INLINE_SYSTEM,
            f"Subject: {email.subject}\n\nBody:\n{email.best_body()}",
            ExtractedForm,
        )
        form.source_location = FormLocation.inline_email
        form.source_ref = email.message_id
        return form

    if triage.form_location == FormLocation.public_website and triage.form_url:
        description = run_with_tools(
            WEB_SYSTEM,
            f"Open and read this camp form: {triage.form_url}\n"
            f"(Camp: {triage.camp_name or 'unknown'}.) List all of its fields.",
        )
        if not description:
            return None
        form = parse_structured(STRUCTURE_SYSTEM, description, ExtractedForm)
        form.source_location = FormLocation.public_website
        form.source_ref = triage.form_url
        return form

    # portal / unknown: nothing safe to extract automatically.
    return None
