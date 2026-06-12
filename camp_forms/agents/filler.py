"""Filler agent.

Maps the family profile onto the extracted form fields and produces a draft. This
is the heart of "ai-in-the-loop": it proposes values, flags its confidence, and
calls out anything only a human can answer — but it never submits.
"""

from __future__ import annotations

from ..llm import parse_structured
from ..models import ExtractedForm, FormDraft, TriageResult

SYSTEM = """You pre-fill a camp form on a parent's behalf from their family profile.

Rules:
  - For each form field, propose a value ONLY if the family profile supports it.
    Cite which profile field you used in `source`.
  - If the profile has nothing for a field, leave `value` empty, set
    `source` to "needs_input", and set `needs_review` to true.
  - Set `needs_review` to true for anything sensitive or ambiguous (signatures,
    medical authorizations, payment, dates you inferred, anything low confidence).
  - Never guess medical information, allergies, medications, or emergency contacts
    that aren't in the profile. A missing answer is safer than a wrong one.
  - Add an entry to `open_questions` for every value the family still must supply
    or confirm.
  - Write `submission_instructions` describing exactly how the parent submits this
    once they approve it (reply to the email / paste into the web form at the URL /
    log into the named portal).

You are drafting for human review. Accuracy and honest uncertainty matter more
than completeness."""


def fill_form(form: ExtractedForm, triage: TriageResult, profile_text: str) -> FormDraft:
    fields = "\n".join(
        f"- {f.label} (type={f.field_type}, required={f.required}"
        + (f", options={f.options}" if f.options else "")
        + (f", notes={f.notes}" if f.notes else "")
        + ")"
        for f in form.fields
    )
    user = (
        f"FAMILY PROFILE:\n{profile_text}\n\n"
        f"FORM: {form.form_title}\n"
        f"Camp: {triage.camp_name or 'unknown'} | Child: {triage.child_name or 'unspecified'} | "
        f"Deadline: {triage.deadline or 'none stated'}\n"
        f"Where it lives: {form.source_location.value} ({form.source_ref or 'n/a'})\n\n"
        f"FIELDS TO FILL:\n{fields}"
    )
    draft = parse_structured(SYSTEM, user, FormDraft, max_tokens=6000)
    # Carry routing context through so the review step and submission instructions
    # stay accurate regardless of what the model echoed.
    draft.camp_name = draft.camp_name or triage.camp_name
    draft.child_name = draft.child_name or triage.child_name
    draft.deadline = draft.deadline or triage.deadline
    draft.source_location = form.source_location
    draft.source_ref = form.source_ref
    return draft
