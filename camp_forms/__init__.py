"""ai-in-the-loop: a human-in-the-loop multi-agent system for summer-camp forms.

The pipeline:
    Gmail -> Triage agent -> Extractor agent -> Filler agent -> Review CLI -> you submit

Nothing is ever submitted automatically. Every form draft stops at "ready for
your review."
"""

__version__ = "0.1.0"
