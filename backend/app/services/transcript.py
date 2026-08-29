"""Gram Sabha transcript processing.

Replaces the stub that returned the same pre-written summary whatever you
uploaded. Text is extracted from the actual file (PDF, DOCX or plain text) and
sent to the language model with a response schema, so the decisions and action
items that come back are grounded in the document in front of you.
"""

from __future__ import annotations

import io
import logging

from app.services.llm import LLMUnavailable, generate_json

log = logging.getLogger(__name__)

MAX_CHARS = 30_000  # keep the prompt within a sensible window

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "titleMr": {"type": "string"},
        "summary": {"type": "string"},
        "summaryMr": {"type": "string"},
        "decisions": {"type": "array", "items": {"type": "string"}},
        "decisionsMr": {"type": "array", "items": {"type": "string"}},
        "actionItems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "actionMr": {"type": "string"},
                    "responsible": {"type": "string"},
                    "responsibleMr": {"type": "string"},
                    "deadline": {"type": "string"},
                },
                "required": ["action", "actionMr", "responsible", "responsibleMr"],
            },
        },
    },
    "required": ["title", "titleMr", "summary", "summaryMr", "decisions", "actionItems"],
}

SYSTEM = (
    "You are a records clerk for a Gram Panchayat in Maharashtra, India. You read "
    "Gram Sabha meeting minutes and extract exactly what the document says. "
    "Never invent decisions, names, dates or amounts that are not in the text. "
    "If the minutes do not name a responsible person for an action, write "
    "'Not specified'. Produce every field in both English and Marathi; when the "
    "source is Marathi, translate faithfully to English rather than paraphrasing."
)


class UnsupportedTranscript(ValueError):
    pass


def extract_text(filename: str, payload: bytes) -> str:
    """Pull plain text out of a PDF, DOCX or text file."""
    lower = (filename or "").lower()

    if lower.endswith(".pdf"):
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:  # pragma: no cover
            raise UnsupportedTranscript("PDF support needs PyMuPDF installed.") from exc
        with fitz.open(stream=payload, filetype="pdf") as doc:
            text = "\n".join(page.get_text() for page in doc)

    elif lower.endswith(".docx"):
        try:
            import docx
        except ImportError as exc:  # pragma: no cover
            raise UnsupportedTranscript("DOCX support needs python-docx installed.") from exc
        document = docx.Document(io.BytesIO(payload))
        text = "\n".join(p.text for p in document.paragraphs)

    elif lower.endswith((".txt", ".md")):
        text = payload.decode("utf-8", errors="replace")

    else:
        raise UnsupportedTranscript(
            "Upload the minutes as a PDF, Word (.docx) or text file."
        )

    text = text.strip()
    if len(text) < 40:
        raise UnsupportedTranscript(
            "No readable text found. If these minutes are a scan, they need OCR first."
        )
    return text[:MAX_CHARS]


async def summarise(text: str, meeting_date: str | None = None) -> dict:
    """Ask the model for a structured reading of the minutes."""
    date_line = f"The meeting date is {meeting_date}.\n" if meeting_date else ""
    prompt = (
        f"{date_line}Read the Gram Sabha minutes below and extract:\n"
        "1. A short title for the meeting.\n"
        "2. A summary of no more than 120 words.\n"
        "3. Every formal decision taken, one per list entry.\n"
        "4. Every action item, with the person or office responsible and a "
        "deadline in YYYY-MM-DD form if the minutes state one.\n\n"
        f"MINUTES:\n{text}"
    )
    try:
        return await generate_json(prompt, EXTRACTION_SCHEMA, SYSTEM)
    except LLMUnavailable:
        raise
