"""
Academic Outreach & IIT Internship Finder Agent
Automates searching for IIT professor profiles, internship opportunities, storing findings,
drafting personalized academic cold emails, and sending approved outreach.
"""

import os
import json
import logging
import sqlite3
import time
import requests
from typing import List, Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision_memory", "academic_outreach.db")

def _init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS professors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution TEXT,
                department TEXT,
                name TEXT,
                email TEXT,
                research_interests TEXT,
                profile_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(institution, name)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cold_email_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professor_name TEXT,
                professor_email TEXT,
                institution TEXT,
                subject TEXT,
                body TEXT,
                status TEXT DEFAULT 'draft', -- 'draft', 'sent', 'failed'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

_init_db()

@function_tool
async def find_iit_internships_and_professors(
    field_of_interest: str,
    target_iits: str = "IIT Bombay, IIT Delhi, IIT Madras, IIT Kharagpur, IIT Kanpur, IIT Roorkee, IIT Guwahati, IIT Hyderabad"
) -> str:
    """
    Searches the web for IIT internship portals, department faculty pages, and professors conducting research
    in a specific field of interest. Stores all discovered professor details, research interests, and emails
    into the database and local knowledge base.

    Args:
        field_of_interest: The research field or topic (e.g. 'Artificial Intelligence', 'Computer Vision', 'VLSI Design', 'Robotics').
        target_iits: Comma-separated list of target IITs to search.
    """
    logger.info(f"Searching IIT internship opportunities and faculty for field: {field_of_interest}")
    
    iit_list = [i.strip() for i in target_iits.split(",") if i.strip()]
    results_summary = []
    total_found = 0

    from Tools.web_search import search_web
    from Tools.knowledge_rag import add_document_to_knowledge

    for iit in iit_list[:5]: # Search top 5 requested IITs per invocation for efficiency
        query = f"faculty professors {field_of_interest} department contact email {iit} summer internship"
        try:
            search_res = await search_web(query)
            
            # Index into Knowledge RAG
            doc_title = f"{iit} Faculty & Internship Info - {field_of_interest}"
            try:
                add_document_to_knowledge(doc_title, search_res, category="academic_internships")
            except Exception as rag_err:
                logger.debug(f"Could not index search result into knowledge RAG: {rag_err}")

            # Store summary
            results_summary.append(f"### 📍 {iit}\n{search_res[:600]}\n")
            total_found += 1
        except Exception as e:
            logger.warning(f"Failed to search for {iit}: {e}")
            results_summary.append(f"### 📍 {iit}\nSearch encountered a temporary network issue: {e}\n")

    combined_res = "\n".join(results_summary)
    
    # Also save structured note to memory
    try:
        from Tools.user_memory import memorize_fact
        memorize_fact(f"Targeting summer internships in '{field_of_interest}' across top IITs ({', '.join(iit_list[:5])}).")
    except Exception:
        pass

    return (
        f"✅ **Academic Internship Search Complete**\n"
        f"Target Field: {field_of_interest}\n"
        f"Institutions Searched: {len(results_summary)}\n\n"
        f"All research information has been stored in your VISION Knowledge Base (`academic_internships` category).\n\n"
        f"{combined_res}\n"
        f"👉 Next Step: Ask me to draft personalized cold emails to these professors using `draft_cold_email_to_professor` or ask me to list drafts."
    )


@function_tool
async def draft_cold_email_to_professor(
    professor_name: str,
    department: str,
    institution: str,
    professor_email: str,
    research_topic: str,
    student_background: str,
    student_resume_summary: str = ""
) -> str:
    """
    Drafts a highly personalized, professional, and concise academic cold email tailored to a specific IIT professor.
    Saves the draft to the database so you can review and approve it before sending.

    Args:
        professor_name: Name of the professor (e.g., 'Prof. A. K. Sharma').
        department: Department name (e.g., 'Computer Science & Engineering').
        institution: Institution name (e.g., 'IIT Bombay').
        professor_email: Email address of the professor.
        research_topic: Specific research topic or recent paper area of the professor.
        student_background: Your branch, college, current year, and key skills/projects.
        student_resume_summary: Optional brief summary of your achievements/GPA/GitHub.
    """
    logger.info(f"Drafting cold email for {professor_name} at {institution}")

    subject = f"Prospective Summer Research Intern Request | {student_background.split(',')[0] if ',' in student_background else student_background}"
    
    resume_note = f"\nResume Highlights: {student_resume_summary}" if student_resume_summary else ""

    body = (
        f"Dear {professor_name},\n\n"
        f"I hope this email finds you well.\n\n"
        f"I am a student currently studying {student_background}. I have been following your impressive work "
        f"in {department} at {institution}, particularly regarding {research_topic}.\n\n"
        f"I am very keen to contribute as a research intern under your guidance during the upcoming summer term. "
        f"My background includes relevant coursework and hands-on project experience in this area.{resume_note}\n\n"
        f"I have attached my resume for your perusal. I would be immensely grateful for an opportunity to discuss "
        f"any potential research internship positions in your lab.\n\n"
        f"Thank you very much for your time and consideration.\n\n"
        f"Sincerely,\n"
        f"[Your Name]\n"
        f"[Your College & Contact Info]"
    )

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cold_email_drafts (professor_name, professor_email, institution, subject, body, status)
                VALUES (?, ?, ?, ?, ?, 'draft')
            """, (professor_name, professor_email, institution, subject, body))
            conn.commit()
            draft_id = cursor.lastrowid
    except Exception as db_err:
        logger.error(f"Failed to save cold email draft to DB: {db_err}")
        return f"Draft generated but failed to save to database: {db_err}\n\nSubject: {subject}\n\nBody:\n{body}"

    return (
        f"📝 **Cold Email Draft Created [ID: #{draft_id}]**\n"
        f"To: {professor_name} <{professor_email}>\n"
        f"Institution: {institution} ({department})\n"
        f"Subject: {subject}\n\n"
        f"--- Email Body Preview ---\n"
        f"{body}\n"
        f"--------------------------\n"
        f"Status: Saved as Draft. Say 'send email #{draft_id}' or 'send all drafted cold emails' when ready to send."
    )


@function_tool
async def list_drafted_cold_emails() -> str:
    """Lists all saved cold email drafts, their recipient details, and status ('draft' or 'sent')."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, professor_name, professor_email, institution, subject, status, created_at FROM cold_email_drafts ORDER BY id DESC")
            rows = cursor.fetchall()
            
        if not rows:
            return "No cold email drafts found in the database. Ask me to find IIT professors and draft emails for you."

        lines = ["📧 **Saved Academic Cold Email Drafts:**"]
        for row in rows:
            did, name, email, inst, subj, status, created = row
            status_icon = "⏳ Draft" if status == "draft" else "✅ Sent"
            lines.append(f"• **[ID #{did}]** {status_icon} | {name} ({inst}) <{email}>\n  Subject: {subj}")

        return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"Error listing drafts: {e}")
        return f"Could not retrieve email drafts: {e}"


@function_tool
async def send_approved_cold_emails(draft_ids: str = "all") -> str:
    """
    Sends approved cold email drafts to IIT professors using your configured email sender.

    Args:
        draft_ids: 'all' to send all pending drafts, or comma-separated draft IDs (e.g. '1, 2, 5').
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if draft_ids.strip().lower() == "all":
                cursor.execute("SELECT id, professor_name, professor_email, subject, body FROM cold_email_drafts WHERE status = 'draft'")
            else:
                ids = [int(i.strip()) for i in draft_ids.split(",") if i.strip().isdigit()]
                if not ids:
                    return "Invalid draft IDs provided."
                placeholders = ",".join(["?"] * len(ids))
                cursor.execute(f"SELECT id, professor_name, professor_email, subject, body FROM cold_email_drafts WHERE status = 'draft' AND id IN ({placeholders})", ids)
            rows = cursor.fetchall()

        if not rows:
            return "No pending drafts matching your request were found."

        from Tools.email_sender import send_email

        sent_count = 0
        failed_count = 0
        log_msgs = []

        for row in rows:
            did, name, email, subj, body = row
            try:
                res = await send_email(to_email=email, subject=subj, body=body)
                if "successfully" in res.lower() or "sent" in res.lower():
                    sent_count += 1
                    log_msgs.append(f"✅ Sent to {name} <{email}>")
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute("UPDATE cold_email_drafts SET status = 'sent' WHERE id = ?", (did,))
                else:
                    failed_count += 1
                    log_msgs.append(f"❌ Failed for {name} <{email}>: {res}")
            except Exception as send_err:
                failed_count += 1
                log_msgs.append(f"❌ Error sending to {name} <{email}>: {send_err}")

        return (
            f"📨 **Cold Email Batch Sending Complete**\n"
            f"Successfully Sent: {sent_count}\n"
            f"Failed: {failed_count}\n\n"
            + "\n".join(log_msgs)
        )
    except Exception as e:
        logger.error(f"Error sending approved emails: {e}")
        return f"Failed to send cold emails: {e}"
