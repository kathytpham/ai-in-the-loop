# ai-in-the-loop

A human-in-the-loop, multi-agent assistant for the avalanche of **summer-camp
forms** every spring. You get a reminder email; the form is either *in* the
email, on a *website*, or behind a *portal login*. This system reads those
emails, figures out where the form lives, extracts what it's asking for,
pre-fills it from a family profile you maintain once — and then **stops and hands
it to you to approve and submit**.

Nothing is ever submitted automatically. That's the "in-the-loop" part.

It also has a second job: **deciding which camps to sign up for in the first
place.** The `plan` command scores candidate camps against your kids' interests
and your logistics, and assembles a full-summer, week-by-week schedule — then
hands *that* to you to approve too. See [Find & schedule camps](#find--schedule-camps).

---

## How it works

```
 Gmail
   │   (read-only)
   ▼
┌──────────────┐   is this a camp form? who/when for?
│ Triage agent │   where does the form live? ─────────────┐
└──────┬───────┘                                           │
       │ camp-related                                      │
       ▼                                                   ▼
┌──────────────┐  inline email → read fields from body    portal → flag for you
│  Extractor   │  website      → web_fetch the page        (no auto-login;
│    agent     │  portal       → hand off to you            we list what to prep)
└──────┬───────┘
       │ list of form fields
       ▼
┌──────────────┐  map family profile → fields
│ Filler agent │  propose values + confidence + open questions
└──────┬───────┘
       │ draft (never submitted)
       ▼
┌──────────────┐
│  Review CLI  │  you approve / edit / skip → then YOU submit
└──────────────┘
```

Each agent is a focused **Claude Opus 4.8** call:

| Agent | Job | How |
|-------|-----|-----|
| **Triage** (`agents/triage.py`) | Classify the email and locate the form | Structured output |
| **Extractor** (`agents/extractor.py`) | List the fields the form asks for | Reads the email, or `web_fetch`es a public form page |
| **Filler** (`agents/filler.py`) | Pre-fill from your profile, flag uncertainty | Structured output |
| **Orchestrator** (`orchestrator.py`) | Route each email through the agents, save drafts | — |

### Why portals are *flagged*, not auto-filled

Logging into a camp portal means storing your portal password and driving a
headless browser on your behalf — a real security and liability step. For v1 the
system **detects** portal forms (CampDoc, CampMinder, UltraCamp, etc.), tells you
which one and by when, and has the Filler list everything to have ready so the
manual login is fast. Browser automation for portals is a deliberate future
opt-in (see *Roadmap*).

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                                   # add your ANTHROPIC_API_KEY
cp config/family_profile.example.yaml config/family_profile.yaml   # fill in your kids' info
```

### Try it with no Gmail setup

The bundled sample emails exercise all three form types (inline / website /
portal) plus a newsletter that should be ignored:

```bash
python -m camp_forms demo      # runs Triage → Extract → Fill on samples
python -m camp_forms review    # walk through the drafts
python -m camp_forms status    # one-line summary of everything
```

> `demo` and `scan` call the Claude API, so `ANTHROPIC_API_KEY` must be set. The
> website sample uses an example URL; real public form pages are read live via
> `web_fetch` during `scan`.

### Connect Gmail (read-only)

1. In [Google Cloud Console](https://console.cloud.google.com): create a project,
   **enable the Gmail API**, configure the OAuth consent screen, and create an
   **OAuth client ID** of type *Desktop app*.
2. Download the client JSON to the repo root as `credentials.json`.
3. Authorize and scan:

```bash
python -m camp_forms auth                  # one-time browser consent (read-only scope)
python -m camp_forms scan                  # search Gmail, draft each camp form
python -m camp_forms review
```

Tune what counts as a camp email via `CAMP_GMAIL_QUERY` in `.env`, or
`--query`/`--max` on `scan`.

---

## What gets stored, and where

| File | Contents | Committed? |
|------|----------|------------|
| `config/family_profile.yaml` | Your real family data | **No** (gitignored) |
| `config/camp_preferences.yaml` | What you want this summer (per kid + logistics) | **No** (gitignored) |
| `credentials.json`, `token.json` | Gmail OAuth | **No** (gitignored) |
| `.env` | API key, query | **No** (gitignored) |
| `data/drafts/*.json` | Per-email triage + draft | **No** (gitignored) |
| `data/camps_catalog.json` | Your candidate camps | **No** (gitignored) |
| `data/plans/*.json` | Generated summer plans | **No** (gitignored) |

Drafts and the profile may contain children's personal/medical data — they stay
on your machine. The Gmail scope is `gmail.readonly`; the system cannot send,
delete, or modify mail.

---

## The review step

`review` shows each draft as a table: proposed value, the agent's **confidence**,
which profile field it came from, and whether **you** need to confirm it.
Signatures, payments, medical authorizations, and anything inferred are always
marked for your review. You `approve`, `edit` inline, or `skip`. Approving marks
the draft ready — submission is still your action, with exact instructions shown
("reply to the email" / "paste into the form at <url>" / "log into <portal>").

---

## Find & schedule camps

The form pipeline above handles camps you've *already chosen*. The `plan` command
handles the step before that — **which camps, and how do they fit across the
summer?** — with the same human-in-the-loop philosophy: it proposes, you decide.

You maintain two files (copy the examples, they're gitignored):

```bash
cp config/camp_preferences.example.yaml config/camp_preferences.yaml   # what you want
cp data/camps_catalog.example.json       data/camps_catalog.json       # camps you're considering
```

- **`camp_preferences.yaml`** — the weeks you need covered, weeks to skip
  (vacation), budget, your drop-off/pickup window, before/aftercare and lunch
  needs, a distance preference (soft — "farther OK if it's really cool"), and per
  child: interests, temperament, and friends they'd love to be with.
- **`camps_catalog.json`** — the candidate camps and their attributes (hours,
  ratio, price, which weeks they run, distance, eligibility).

Then:

```bash
python -m camp_forms plan              # score camps and build a summer schedule
python -m camp_forms plan --discover   # also web-search for more local camps first
python -m camp_forms plan-review       # adjust the schedule week by week, then approve
```

Three focused Claude agents do the work:

| Agent | Job | How |
|-------|-----|-----|
| **Discovery** (`agents/discovery.py`) | Find camps you don't know about near you | `web_search` + `web_fetch`; results flagged *needs-review* |
| **Matcher** (`agents/matcher.py`) | Score every camp for each child | Eligibility, interest fit, hard logistics, distance-as-soft-penalty, friend/sibling signals |
| **Scheduler** (`agents/scheduler.py`) | Assemble the week-by-week summer | No gaps, no double-booking, within budget, respects blocked weeks; explains trade-offs |

The output is a **proposed schedule** — a week × child grid with fit scores, the
trade-offs it made (where it chose farther/pricier for a clearly better camp), and
the open questions only you can answer (is Ava *actually* enrolled that week?).
Nothing is registered. Once you pick, the form pipeline handles each signup.

`plan-review` then walks that schedule with you, the way `review` walks the form
drafts. For any week you can **swap** a child's camp for another — and you're only
offered camps that actually run that week and that the Matcher judged the child
eligible for, ranked by fit — or **clear** a week to a gap. The running total
re-costs as you go, and `approve` saves your edits (still registering nothing).

Two deliberate guardrails:

- **Friends are a *signal*, never an assumption.** The matcher can't know whether
  a named friend actually enrolled, so it flags every friend/sibling pairing for
  you to confirm rather than scheduling around a guess.
- **Discovered camps are unverified.** Anything the web-discovery agent finds
  arrives flagged *needs-review* — web data is often stale, so it never silently
  schedules around a camp whose details you haven't checked.

---

## Roadmap

- **Portal automation** (opt-in): Playwright login + fill for the big providers,
  with credentials in your OS keychain and a mandatory review-before-submit gate.
- **Auto-fill of public web forms** via Playwright once you approve the draft.
- **Deadline reminders** surfaced back into your calendar/email.
- **Per-child routing** when one email covers multiple kids.
- **Plan → forms handoff**: turn an approved summer plan straight into the
  registration drafts for each chosen camp.
- **Waitlist / fill-rate awareness** in the scheduler (register-early signals).

---

## Layout

```
camp_forms/
  cli.py            # `python -m camp_forms ...`
  orchestrator.py   # routes emails through the form agents, persists drafts
  planner.py        # routes preferences+camps through the matcher agents, persists plans
  gmail_client.py   # read-only Gmail wrapper
  profile.py        # load + render the family profile
  preferences.py    # load + render the camp-matching preferences
  catalog.py        # load/save + render the candidate-camps catalog
  llm.py            # Anthropic client, structured-output + tool-use helpers
  models.py         # typed schemas shared across agents
  review.py         # human-in-the-loop approval CLI (forms)
  plan_view.py      # renders the proposed summer schedule
  plan_review.py    # human-in-the-loop summer-schedule review (swap/clear/approve)
  agents/
    triage.py  extractor.py  filler.py     # form pipeline
    discovery.py  matcher.py  scheduler.py  # camp-matching pipeline
config/family_profile.example.yaml
config/camp_preferences.example.yaml
data/sample_emails.json
data/camps_catalog.example.json
```
