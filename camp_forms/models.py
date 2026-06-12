"""Shared data models.

The Pydantic models double as structured-output schemas for the agents — Claude
returns JSON that validates against these, so the rest of the system works with
typed objects instead of free-form text.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FormLocation(str, Enum):
    """Where the form actually lives."""

    inline_email = "inline_email"      # the form/fields are in the email body itself
    public_website = "public_website"  # a public URL we can fetch and read
    portal = "portal"                  # behind a login (camp portal, CampMinder, etc.)
    unknown = "unknown"


class Urgency(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


# --- Raw email pulled from Gmail (or a sample file) --------------------------

class CampEmail(BaseModel):
    message_id: str
    sender: str
    subject: str
    received: str = ""
    body_text: str = ""
    body_html: str = ""

    def best_body(self) -> str:
        """Plain text if we have it, otherwise the HTML (the model can read both)."""
        return self.body_text.strip() or self.body_html.strip()


# --- Output of the Triage agent ---------------------------------------------

class TriageResult(BaseModel):
    is_camp_related: bool = Field(description="Is this email about a camp form/registration we likely need to fill out?")
    camp_name: Optional[str] = None
    child_name: Optional[str] = Field(default=None, description="Which child this is for, if the email names one")
    deadline: Optional[str] = Field(default=None, description="Deadline as an ISO date (YYYY-MM-DD) if one is stated or clearly implied")
    urgency: Urgency = Urgency.medium
    summary: str = Field(description="One or two sentences: what action this email is asking for")
    form_location: FormLocation = FormLocation.unknown
    form_url: Optional[str] = Field(default=None, description="The URL of the form/portal if one appears in the email")
    portal_name: Optional[str] = Field(default=None, description="Name of the portal/provider if behind a login")
    reasoning: str = Field(description="Brief why behind the classification")


# --- Output of the Extractor agent ------------------------------------------

class FormField(BaseModel):
    label: str
    field_type: str = Field(description="text, date, email, phone, number, select, checkbox, signature, file, etc.")
    required: bool = False
    options: list[str] = Field(default_factory=list, description="Allowed values for select/checkbox fields")
    notes: Optional[str] = None


class ExtractedForm(BaseModel):
    form_title: str
    fields: list[FormField] = Field(default_factory=list)
    source_location: FormLocation = FormLocation.unknown
    source_ref: Optional[str] = Field(default=None, description="URL or message id the form was read from")


# --- Output of the Filler agent ---------------------------------------------

class FilledField(BaseModel):
    label: str
    value: str = Field(description="Proposed value, or empty string if we have nothing to fill")
    confidence: Confidence = Confidence.medium
    source: str = Field(description="Which profile field this came from, or 'needs_input' if the family must supply it")
    needs_review: bool = Field(default=False, description="True if a human must confirm or supply this value")


class FormDraft(BaseModel):
    form_title: str
    camp_name: Optional[str] = None
    child_name: Optional[str] = None
    deadline: Optional[str] = None
    source_location: FormLocation = FormLocation.unknown
    source_ref: Optional[str] = None
    filled: list[FilledField] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list, description="Things only the family can answer")
    submission_instructions: str = Field(description="Exactly how the human should submit this once approved")
