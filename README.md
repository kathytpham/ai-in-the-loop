# ai-in-the-loop

A human-in-the-loop, multi-agent assistant for the avalanche of **summer-camp
forms** every spring. You get a reminder email; the form is either *in* the
email, on a *website*, or behind a *portal login*. This system reads those
emails, figures out where the form lives, extracts what it's asking for,
pre-fills it from a family profile you maintain once — and then **stops and hands
it to you to approve and submit**.

Nothing is ever submitted automatically. That's the "in-the-loop" part.

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
| `credentials.json`, `token.json` | Gmail OAuth | **No** (gitignored) |
| `.env` | API key, query | **No** (gitignored) |
| `data/drafts/*.json` | Per-email triage + draft | **No** (gitignored) |

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

## Roadmap

- **Portal automation** (opt-in): Playwright login + fill for the big providers,
  with credentials in your OS keychain and a mandatory review-before-submit gate.
- **Auto-fill of public web forms** via Playwright once you approve the draft.
- **Deadline reminders** surfaced back into your calendar/email.
- **Per-child routing** when one email covers multiple kids.

---

## Layout

```
camp_forms/
  cli.py            # `python -m camp_forms ...`
  orchestrator.py   # routes emails through the agents, persists drafts
  gmail_client.py   # read-only Gmail wrapper
  profile.py        # load + render the family profile
  llm.py            # Anthropic client, structured-output + tool-use helpers
  models.py         # typed schemas shared across agents
  review.py         # human-in-the-loop approval CLI
  agents/
    triage.py  extractor.py  filler.py
config/family_profile.example.yaml
data/sample_emails.json
```
