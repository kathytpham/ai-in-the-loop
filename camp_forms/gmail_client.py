"""Minimal Gmail API wrapper (read-only).

Uses the standard installed-app OAuth flow. We request *read-only* scope on
purpose — this system reads your camp reminders, it never sends or deletes mail.

First run opens a browser to authorize; the token is cached in token.json so
later runs are non-interactive.
"""

from __future__ import annotations

import base64
import os
from typing import Optional

from .models import CampEmail

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def _service():
    # Imported lazily so the rest of the system (and demo mode) works without the
    # Google libraries installed.
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds: Optional[Credentials] = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_FILE}. Create an OAuth client (Desktop app) in "
                    "Google Cloud Console, enable the Gmail API, and download it here. "
                    "See the README's Gmail setup section."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def authorize() -> None:
    """Trigger the OAuth flow (used by the `auth` CLI command)."""
    _service()


def search(query: str, max_results: int = 25) -> list[CampEmail]:
    svc = _service()
    resp = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    out: list[CampEmail] = []
    for ref in resp.get("messages", []):
        out.append(_get_message(svc, ref["id"]))
    return out


def _get_message(svc, message_id: str) -> CampEmail:
    msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    text, html = _extract_bodies(msg["payload"])
    return CampEmail(
        message_id=message_id,
        sender=headers.get("from", ""),
        subject=headers.get("subject", "(no subject)"),
        received=headers.get("date", ""),
        body_text=text,
        body_html=html,
    )


def _extract_bodies(payload) -> tuple[str, str]:
    """Walk the MIME tree collecting the first text/plain and text/html parts."""
    text, html = "", ""

    def walk(part):
        nonlocal text, html
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data:
            decoded = base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", "replace")
            if mime == "text/plain" and not text:
                text = decoded
            elif mime == "text/html" and not html:
                html = decoded
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    return text, html
