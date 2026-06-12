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


# === Camp matching & summer scheduling ======================================
# A second pipeline, parallel to the form pipeline above: instead of "a form
# arrived, fill it," this answers "which camps should we sign up for, and how do
# they fit together across the summer?" Same philosophy — the system proposes a
# plan with its reasoning and open questions; the family decides and registers.


class CampSource(str, Enum):
    catalog = "catalog"        # a camp you put in your own catalog
    discovered = "discovered"  # found by the web-discovery agent; treat as unverified


class Camp(BaseModel):
    """One candidate camp. The same shape is used whether it came from your
    catalog or was discovered on the web (discovered ones carry needs_review)."""

    name: str
    provider: Optional[str] = Field(default=None, description="Operator/brand, if distinct from the camp name")
    activities: list[str] = Field(default_factory=list, description="Focus areas: e.g. art, soccer, STEM, nature, theater")
    description: str = ""
    location: str = Field(default="", description="Address or area the camp runs at")
    distance_miles: Optional[float] = Field(default=None, description="Driving distance from home, if known")

    # Eligibility — give whichever the camp states (grade and/or age).
    min_grade: Optional[str] = None
    max_grade: Optional[str] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None

    # Schedule. weeks are the Monday start-dates (ISO YYYY-MM-DD) the camp runs.
    weeks: list[str] = Field(default_factory=list, description="Monday start-dates this camp offers (ISO YYYY-MM-DD)")
    day_start: Optional[str] = Field(default=None, description="Core-day start time, e.g. 09:00")
    day_end: Optional[str] = Field(default=None, description="Core-day end time, e.g. 15:00")
    before_care: bool = False
    before_care_start: Optional[str] = None
    after_care: bool = False
    after_care_end: Optional[str] = None
    lunch_provided: Optional[bool] = Field(default=None, description="True if lunch is included, False if pack-your-own")
    ratio: Optional[str] = Field(default=None, description="Staff-to-camper ratio as it's stated, e.g. 1:8")
    price_per_week: Optional[float] = None
    accredited: Optional[bool] = Field(default=None, description="ACA-accredited / licensed, if known")
    url: Optional[str] = None

    source: CampSource = CampSource.catalog
    needs_review: bool = Field(default=False, description="True for discovered camps — verify details before trusting them")
    notes: str = ""


class DiscoveryResult(BaseModel):
    """Output of the Discovery agent: camps it found on the web near you."""

    camps: list[Camp] = Field(default_factory=list)
    notes: str = Field(default="", description="How the search went, and what to double-check")


class CampScore(BaseModel):
    """The Matcher's judgement of one camp for one child."""

    camp_name: str
    child_name: str
    eligible: bool = Field(description="Does the child meet the camp's age/grade requirement?")
    fit_score: int = Field(description="Overall fit 0-100, after weighing interests, logistics, distance, social")
    activity_match: str = Field(default="", description="How the camp's focus matches the child's interests")
    logistics_note: str = Field(default="", description="Fit vs. constraints: hours, before/aftercare, lunch, ratio")
    distance_note: str = Field(default="", description="How distance was weighed (soft penalty; great camps can overcome it)")
    social_note: str = Field(default="", description="Friend overlap / sibling co-location signal — always to be confirmed by the family")
    concerns: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.medium
    reasoning: str = ""


class ChildScores(BaseModel):
    """All camp scores for a single child, ranked best-first by the Matcher."""

    child_name: str
    scores: list[CampScore] = Field(default_factory=list)


class ScheduledWeek(BaseModel):
    """One child's assignment for one week of the summer."""

    week_start: str = Field(description="Monday start-date of the week (ISO YYYY-MM-DD)")
    child_name: str
    camp_name: Optional[str] = Field(default=None, description="Chosen camp, or null if no good option / gap")
    status: str = Field(default="assigned", description="assigned | gap | blocked | conflict")
    fit_score: Optional[int] = None
    cost: Optional[float] = None
    rationale: str = ""
    needs_review: bool = Field(default=False, description="True when the family must confirm something (e.g. a friend's enrollment)")


class SummerPlan(BaseModel):
    """The Scheduler's proposed week-by-week plan across all children."""

    weeks: list[ScheduledWeek] = Field(default_factory=list)
    total_cost: Optional[float] = None
    coverage_summary: str = Field(default="", description="Plain-language coverage, e.g. 'Mia 8/8 weeks, Leo 7/8 (1 gap)'")
    gaps: list[str] = Field(default_factory=list, description="Weeks left uncovered and why")
    tradeoffs: list[str] = Field(default_factory=list, description="Where the plan chose farther/pricier for a clearly better camp")
    open_questions: list[str] = Field(default_factory=list, description="Things only the family can decide or confirm")
    alternatives: str = Field(default="", description="Notable runner-up options worth knowing about")
