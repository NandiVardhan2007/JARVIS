"""Email Agent — full Gmail IMAP read + SMTP send.

Extends JARVIS from send-only to a complete email assistant.
Uses imaplib + email (stdlib, zero new deps). Reuses JARVIS_EMAIL / JARVIS_EMAIL_PASSWORD.
"""

import email
import email.header
import email.utils
import imaplib
import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

SENDER_EMAIL = os.getenv("JARVIS_EMAIL", "")
SENDER_PASSWORD = os.getenv("JARVIS_EMAIL_PASSWORD", "")

IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993


# ── Helpers ───────────────────────────────────────────────────────────────────

from contextlib import contextmanager

def _get_imap():
    """Connect and login to Gmail IMAP. Caller must .logout() when done."""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise RuntimeError(
            "Email credentials not configured. "
            "Set JARVIS_EMAIL and JARVIS_EMAIL_PASSWORD in .env."
        )
    conn = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    conn.login(SENDER_EMAIL, SENDER_PASSWORD)
    return conn

@contextmanager
def imap_connection():
    """Context manager for IMAP connection to ensure proper logout."""
    conn = _get_imap()
    try:
        yield conn
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def _decode_header(raw: str) -> str:
    """Decode a MIME-encoded email header into a plain string."""
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def _extract_text(msg: email.message.Message) -> str:
    """Extract plain-text body from a (possibly multipart) email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback: try HTML
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    raw_html = payload.decode(charset, errors="replace")
                    # Strip HTML tags for a rough plaintext
                    return re.sub(r"<[^>]+>", "", raw_html).strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return "(No readable content)"


def _format_email_summary(msg: email.message.Message, uid: str) -> str:
    """Format an email into a short summary line."""
    subj = _decode_header(msg.get("Subject", "(No subject)"))
    frm = _decode_header(msg.get("From", "Unknown"))
    date = msg.get("Date", "Unknown date")
    # Shorten the date
    try:
        parsed = email.utils.parsedate_to_datetime(date)
        date = parsed.strftime("%b %d, %I:%M %p")
    except Exception:
        pass
    snippet = _extract_text(msg)[:100].replace("\n", " ").strip()
    return f"[ID:{uid}] {subj}\n  From: {frm}\n  Date: {date}\n  Preview: {snippet}..."


# ── Tools ─────────────────────────────────────────────────────────────────────

@function_tool
async def read_inbox(n: int = 5, folder: str = "INBOX") -> str:
    """
    Fetches the latest N emails from a mailbox folder.

    Args:
        n: Number of emails to fetch (default 5, max 15).
        folder: Mailbox folder name (default: "INBOX").
    """
    try:
        n = max(1, min(int(n), 15))
    except (ValueError, TypeError):
        n = 5
    logger.info(f"Reading {n} emails from {folder}")

    try:
        with imap_connection() as conn:
            conn.select(folder, readonly=True)
            _, data = conn.search(None, "ALL")
            msg_ids = data[0].split()

            if not msg_ids:
                return f"No emails found in {folder}."

            # Get the last N
            recent_ids = msg_ids[-n:][::-1]  # newest first
            results = []

            for uid in recent_ids:
                _, msg_data = conn.fetch(uid, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                results.append(_format_email_summary(msg, uid.decode()))

            return f"Latest {len(results)} emails in {folder}:\n\n" + "\n\n".join(results)
    except Exception as e:
        logger.error(f"read_inbox error: {e}")
        return f"Failed to read inbox: {e}"


@function_tool
async def read_email(email_id: str, folder: str = "INBOX") -> str:
    """
    Reads the full body of an email by its message ID.

    Args:
        email_id: The numeric message ID (from read_inbox results).
        folder: Mailbox folder (default: "INBOX").
    """
    logger.info(f"Reading email ID {email_id}")

    try:
        with imap_connection() as conn:
            conn.select(folder, readonly=True)
            _, msg_data = conn.fetch(email_id.encode(), "(RFC822)")

            if not msg_data or not msg_data[0]:
                return f"Email ID {email_id} not found."

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

        subj = _decode_header(msg.get("Subject", "(No subject)"))
        frm = _decode_header(msg.get("From", "Unknown"))
        to = _decode_header(msg.get("To", "Unknown"))
        date = msg.get("Date", "Unknown")
        body = _extract_text(msg)

        # Truncate very long emails
        if len(body) > 3000:
            body = body[:3000] + "\n\n... (truncated — email is very long)"

        return (
            f"Subject: {subj}\n"
            f"From: {frm}\n"
            f"To: {to}\n"
            f"Date: {date}\n"
            f"{'─' * 40}\n"
            f"{body}"
        )
    except Exception as e:
        logger.error(f"read_email error: {e}")
        return f"Failed to read email: {e}"


@function_tool
async def search_emails(query: str, folder: str = "INBOX", n: int = 5) -> str:
    """
    Searches emails by subject or sender keyword.

    Args:
        query: Search keyword (matched against subject and sender).
        folder: Mailbox folder (default: "INBOX").
        n: Max results to return (default 5).
    """
    n = max(1, min(n, 10))
    logger.info(f"Searching emails for: {query}")

    try:
        with imap_connection() as conn:
            conn.select(folder, readonly=True)

            # Search by subject OR from
            _, subj_data = conn.search(None, f'(SUBJECT "{query}")')
            _, from_data = conn.search(None, f'(FROM "{query}")')

            subj_ids = set(subj_data[0].split()) if subj_data[0] else set()
            from_ids = set(from_data[0].split()) if from_data[0] else set()
            all_ids = sorted(subj_ids | from_ids, key=lambda x: int(x), reverse=True)

            if not all_ids:
                return f"No emails found matching '{query}'."

            results = []
            for uid in all_ids[:n]:
                _, msg_data = conn.fetch(uid, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                results.append(_format_email_summary(msg, uid.decode()))

            return f"Found {len(results)} email(s) matching '{query}':\n\n" + "\n\n".join(results)
    except Exception as e:
        logger.error(f"search_emails error: {e}")
        return f"Failed to search emails: {e}"


@function_tool
async def reply_email(
    email_id: str,
    body: str,
    folder: str = "INBOX",
) -> str:
    """
    Replies to an email by message ID. Quotes the original message.

    Args:
        email_id: The numeric message ID to reply to.
        body: The reply body text.
        folder: Mailbox folder (default: "INBOX").
    """
    logger.info(f"Replying to email ID {email_id}")

    try:
        # Fetch original
        with imap_connection() as conn:
            conn.select(folder, readonly=True)
            _, msg_data = conn.fetch(email_id.encode(), "(RFC822)")

            if not msg_data or not msg_data[0]:
                return f"Email ID {email_id} not found."

            raw_email = msg_data[0][1]
            original = email.message_from_bytes(raw_email)

        orig_from = _decode_header(original.get("From", ""))
        orig_subj = _decode_header(original.get("Subject", ""))
        orig_body = _extract_text(original)
        orig_date = original.get("Date", "")
        orig_msg_id = original.get("Message-ID", "")

        # Extract reply-to address
        reply_to = _decode_header(original.get("Reply-To", orig_from))
        # Extract just the email address
        match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", reply_to)
        if not match:
            return f"Could not extract reply-to address from: {reply_to}"
        to_addr = match.group()

        # Build reply
        reply_subj = f"Re: {orig_subj}" if not orig_subj.startswith("Re:") else orig_subj
        quoted = "\n".join(f"> {line}" for line in orig_body[:1000].split("\n"))
        full_body = f"{body}\n\nOn {orig_date}, {orig_from} wrote:\n{quoted}"

        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_addr
        msg["Subject"] = reply_subj
        if orig_msg_id:
            msg["In-Reply-To"] = orig_msg_id
            msg["References"] = orig_msg_id
        msg.attach(MIMEText(full_body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, [to_addr], msg.as_string())

        return f"Reply sent to {to_addr} — Subject: {reply_subj}"
    except Exception as e:
        logger.error(f"reply_email error: {e}")
        return f"Failed to reply: {e}"


@function_tool
async def mark_email_read(email_id: str, folder: str = "INBOX") -> str:
    """
    Marks an email as read (sets the \\Seen flag).

    Args:
        email_id: The numeric message ID to mark as read.
        folder: Mailbox folder (default: "INBOX").
    """
    logger.info(f"Marking email {email_id} as read")

    try:
        with imap_connection() as conn:
            conn.select(folder)
            conn.store(email_id.encode(), "+FLAGS", "\\Seen")
            return f"Email ID {email_id} marked as read."
    except Exception as e:
        logger.error(f"mark_email_read error: {e}")
        return f"Failed to mark as read: {e}"


@function_tool
async def label_email(
    email_id: str,
    label: str,
    folder: str = "INBOX",
) -> str:
    """
    Moves an email to a Gmail label/folder (e.g., 'Important', 'Work').

    Args:
        email_id: The numeric message ID.
        label: Target Gmail label name.
        folder: Source folder (default: "INBOX").
    """
    logger.info(f"Moving email {email_id} to label '{label}'")

    try:
        with imap_connection() as conn:
            conn.select(folder)
            # Gmail uses COPY + delete from source to "move"
            result = conn.copy(email_id.encode(), label)
            if result[0] == "OK":
                conn.store(email_id.encode(), "+FLAGS", "\\Deleted")
                conn.expunge()
                return f"Email ID {email_id} moved to '{label}'."
            else:
                return f"Failed to copy to '{label}'. Label may not exist — create it in Gmail first."
    except Exception as e:
        logger.error(f"label_email error: {e}")
        return f"Failed to move email: {e}"


@function_tool
async def delete_emails(
    emails: str,
    folder: str = "INBOX",
) -> str:
    """
    Deletes one or multiple emails.
    
    Args:
        emails: Comma-separated list of email IDs (e.g. "132, 131" or "[ID:132], [ID:131]").
        folder: Source folder (default: "INBOX").
    """
    logger.info(f"Deleting emails '{emails}' from {folder}")
    try:
        import re
        # Extract just the numeric IDs from the string
        ids = re.findall(r'\d+', emails)
        if not ids:
            return "No valid email IDs found to delete."
            
        with imap_connection() as conn:
            conn.select(folder)
            
            deleted_count = 0
            for uid in ids:
                conn.store(uid.encode(), "+FLAGS", "\\Deleted")
                deleted_count += 1
                
            conn.expunge()
            return f"Successfully deleted {deleted_count} email(s)."
    except Exception as e:
        logger.error(f"delete_emails error: {e}")
        return f"Failed to delete emails: {e}"



__all__ = [
    "read_inbox", "read_email", "search_emails",
    "reply_email", "mark_email_read", "label_email",
    "summarize_email", "delete_emails",
]


# ── Dedicated LLM for the email agent ─────────────────────────────────────────

EMAIL_AGENT_LLM_API = os.getenv("EMAIL_AGENT_LLM_API", "")
_NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
_NIM_MODEL = "meta/llama-3.3-70b-instruct"

LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "local-model")


def _email_llm(system: str, user: str) -> str:
    """Call the LLM using local LM Studio or fallback to NVIDIA NIM."""
    import requests as _requests

    if LOCAL_LLM_URL:
        url = LOCAL_LLM_URL + "/chat/completions" if not LOCAL_LLM_URL.endswith("chat/completions") else LOCAL_LLM_URL
        api_key = "local-key"
        model = LOCAL_LLM_MODEL
    elif EMAIL_AGENT_LLM_API:
        url = _NIM_URL
        api_key = EMAIL_AGENT_LLM_API
        model = _NIM_MODEL
    else:
        raise RuntimeError(
            "Neither LOCAL_LLM_URL nor EMAIL_AGENT_LLM_API is set in .env. "
            "Cannot use LLM features in the email agent."
        )

    resp = _requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


@function_tool
async def summarize_email(email_id: str, folder: str = "INBOX") -> str:
    """
    Reads an email and produces a concise AI-generated summary highlighting
    key points, action items, and deadlines.

    Args:
        email_id: The numeric message ID (from read_inbox results).
        folder: Mailbox folder (default: "INBOX").
    """
    logger.info(f"Summarizing email ID {email_id}")

    try:
        with imap_connection() as conn:
            conn.select(folder, readonly=True)
            _, msg_data = conn.fetch(email_id.encode(), "(RFC822)")

            if not msg_data or not msg_data[0]:
                return f"Email ID {email_id} not found."

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

        subj = _decode_header(msg.get("Subject", "(No subject)"))
        frm = _decode_header(msg.get("From", "Unknown"))
        body = _extract_text(msg)[:5000]

        system = (
            "You are JARVIS, an email analyst. Provide a structured summary of this email.\n"
            "Extract and format as follows:\n"
            "**From:** sender name/org\n"
            "**Summary:** 1-2 sentence overview of the email's purpose\n"
            "**Key Points:** bullet list of important details, decisions, or data\n"
            "**Action Items:** specific tasks, deadlines, or responses needed (or 'None')\n"
            "**Urgency:** Low / Medium / High — based on deadline proximity, sender importance, and language tone\n"
            "**Tone:** Formal / Casual / Urgent / Automated\n"
            "Be precise. Extract exact dates, amounts, and names. Don't paraphrase when quoting key details."
        )
        user_prompt = (
            f"Subject: {subj}\nFrom: {frm}\n\n{body}"
        )
        summary = _email_llm(system, user_prompt)
        return f"Email Summary — {subj}\n{'─' * 40}\n{summary}"
    except Exception as e:
        logger.error(f"summarize_email error: {e}")
        return f"Failed to summarize email: {e}"

