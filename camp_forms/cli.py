"""Command-line entrypoint:  python -m camp_forms <command>

Commands:
  auth     Authorize Gmail (one-time browser OAuth).
  scan     Search Gmail for camp emails and draft forms for each.
  demo     Run the whole pipeline on bundled sample emails (no Gmail needed).
  review   Walk through drafts and approve/edit them.
  status   Show a one-line summary of every draft.
  plan     Match camps to your kids and assemble a full-summer schedule.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from .models import CampEmail

load_dotenv()

DEFAULT_QUERY = os.environ.get(
    "CAMP_GMAIL_QUERY",
    'newer_than:90d (camp OR registration OR enrollment OR forms OR "summer program" OR waiver)',
)


def _cmd_auth(_args) -> None:
    from . import gmail_client

    gmail_client.authorize()
    print("Gmail authorized. Token cached in token.json.")


def _cmd_scan(args) -> None:
    from .orchestrator import scan_gmail

    items = scan_gmail(args.query, args.max, profile_path=args.profile)
    _print_scan_summary(items)


def _cmd_demo(args) -> None:
    from .orchestrator import scan

    sample_path = os.path.join("data", "sample_emails.json")
    with open(sample_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    emails = [CampEmail(**e) for e in raw]
    print(f"Loaded {len(emails)} sample emails.\n")
    items = scan(emails, profile_path=args.profile)
    _print_scan_summary(items)


def _cmd_review(_args) -> None:
    from .review import review

    review(only_pending=True)


def _cmd_status(_args) -> None:
    from .review import summary

    summary()


def _cmd_plan(args) -> None:
    from .planner import make_plan
    from .plan_view import print_plan
    from .preferences import child_names

    result = make_plan(
        preferences_path=args.preferences,
        catalog_path=args.catalog,
        discover=args.discover,
        save_discovered=args.save_discovered,
    )
    print()
    print_plan(result.plan, result.scores, child_names(result.preferences))


def _print_scan_summary(items) -> None:
    actionable = [i for i in items if i.status in ("needs_review", "flagged_portal")]
    print(f"\nDone. {len(actionable)} of {len(items)} emails need your attention.")
    print("Run `python -m camp_forms review` to go through them.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="camp_forms", description=__doc__)
    parser.add_argument("--profile", default=None, help="Path to family profile YAML")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("auth", help="Authorize Gmail (one-time)").set_defaults(func=_cmd_auth)

    p_scan = sub.add_parser("scan", help="Search Gmail and draft forms")
    p_scan.add_argument("--query", default=DEFAULT_QUERY, help="Gmail search query")
    p_scan.add_argument("--max", type=int, default=25, help="Max emails to fetch")
    p_scan.set_defaults(func=_cmd_scan)

    sub.add_parser("demo", help="Run on bundled sample emails (no Gmail)").set_defaults(func=_cmd_demo)
    sub.add_parser("review", help="Review and approve drafts").set_defaults(func=_cmd_review)
    sub.add_parser("status", help="Summarize all drafts").set_defaults(func=_cmd_status)

    p_plan = sub.add_parser("plan", help="Match camps and assemble a summer schedule")
    p_plan.add_argument("--preferences", default=None, help="Path to camp preferences YAML")
    p_plan.add_argument("--catalog", default=None, help="Path to camps catalog JSON")
    p_plan.add_argument("--discover", action="store_true", help="Also web-search for more local camps")
    p_plan.add_argument(
        "--save-discovered", action="store_true",
        help="Append discovered camps to your catalog file",
    )
    p_plan.set_defaults(func=_cmd_plan)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
