"""Discovery agent.

Finds camps you may not know about. Given your preferences (location, your kids'
interests, the weeks and hours you need), it uses Claude's server-side web tools
to search for local camps and reads their pages, then returns them as catalog
entries — flagged `needs_review`, because web data is often stale or wrong and you
should never schedule around an unverified camp.

This is the one matcher-side agent that reaches the live web, exactly like the
Extractor does in the form pipeline.
"""

from __future__ import annotations

from ..llm import parse_structured, run_with_tools
from ..models import CampSource, DiscoveryResult

SEARCH_SYSTEM = """You research summer day camps for a parent. Using web_search and
web_fetch, find real camps near the family's location that plausibly fit their
children's interests and the weeks/hours they need. For each promising camp, open
its page and read the concrete details: focus/activities, ages or grades served,
which weeks it runs this summer, daily hours, before/aftercare, lunch, staff ratio,
weekly price, and the URL.

Report only camps you actually found on the web — do not invent camps, prices, or
dates. If a detail isn't stated on the page, say it's unknown rather than guessing.
Prefer camps within or near the family's distance preference, but you may include a
clearly exceptional camp that's a bit farther. Aim for 4–8 solid candidates."""

STRUCTURE_SYSTEM = """Convert the following camp research notes into structured
catalog entries. Keep details exactly as reported; where a detail was unknown,
leave that field null. Do not add camps that weren't in the notes."""


def discover_camps(preferences_text: str) -> DiscoveryResult:
    notes = run_with_tools(
        SEARCH_SYSTEM,
        f"FAMILY PREFERENCES (use the location, interests, weeks, hours, and "
        f"distance preference):\n{preferences_text}\n\n"
        f"Find local summer camps that fit. Read each camp's page for details.",
    )
    if not notes:
        return DiscoveryResult(camps=[], notes="Web discovery returned nothing.")

    result = parse_structured(STRUCTURE_SYSTEM, notes, DiscoveryResult, max_tokens=8000)
    # Everything from the web is unverified until the family confirms it.
    for camp in result.camps:
        camp.source = CampSource.discovered
        camp.needs_review = True
    return result
