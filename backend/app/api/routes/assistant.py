"""The Panchayat assistant.

Answers questions from the database, in English or Marathi, within whatever the
asker is allowed to see.

The shape is retrieve-then-generate: fetch the relevant records, hand them to
the language model as the only permitted source, and return the answer with the
records it drew on. The model is instructed not to use anything else, and the
sources are returned so a claim can be checked against the row it came from.

If no model key is configured, the endpoint answers from the same retrieved
facts in a plainer form rather than pretending — see `retrieval.plain_answer`.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, village_scope
from app.db.session import get_db
from app.models import User
from app.schemas import AssistantAnswer, AssistantQuery, RetrievedSource
from app.services import retrieval
from app.services.llm import LLMUnavailable, generate

router = APIRouter(prefix="/assistant", tags=["assistant"])

SYSTEM_OFFICER = """You are the assistant for a Gram Panchayat office in Maharashtra, India.

You answer questions for a Panchayat officer using ONLY the records supplied to
you. These rules are absolute:

- Never state a fact that is not in the supplied records. If the records do not
  answer the question, say plainly what is missing and suggest where the officer
  would find it.
- Never estimate, extrapolate, or fill a gap with general knowledge about
  Indian government schemes. A wrong figure in a welfare decision causes real harm.
- Quote figures exactly as given. Do not round rupee amounts or recompute totals.
- Refer to residents, wards, schemes and projects by the names and IDs in the records.
- Be brief: four sentences at most unless a list is genuinely clearer.
- Write in the requested language. When writing Marathi, use natural Marathi,
  not transliterated English."""

SYSTEM_CITIZEN = """You are the helpdesk assistant for a Gram Panchayat in Maharashtra, India.

You are speaking to a village resident about their own records. These rules are
absolute:

- Use ONLY the records supplied to you. Never state a fact that is not there.
- Never guess whether someone qualifies for a scheme. The supplied records
  already contain the decision and its reason — repeat that, do not reason afresh.
- Never mention another resident's information.
- Be warm, plain and practical. Say what the person can do next: which document
  to upload, which office to visit, which form to fill.
- Keep it to four sentences unless a short list is clearer.
- Write in the requested language, in natural Marathi where asked."""


@router.post("/ask", response_model=AssistantAnswer)
async def ask(
    body: AssistantQuery,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssistantAnswer:
    is_english = body.language == "en"

    # Retrieval runs inside the asker's permissions: a citizen's question is
    # answered from their own records, an officer's from their village.
    village_id = village_scope(user)
    if user.role == "citizen" and user.village_id:
        village_id = user.village_id

    retrieved = retrieval.gather(db, body.query, user, village_id)
    sources = [
        RetrievedSource(entity_type=s.entity_type, entity_id=s.entity_id, title=s.title)
        for s in retrieved.sources
    ]

    if not settings.ai_enabled:
        return AssistantAnswer(
            answer=retrieval.plain_answer(retrieved, body.language),
            sources=sources,
            mode="retrieval_only",
        )

    prompt = (
        f"RECORDS FROM THE PANCHAYAT DATABASE:\n{retrieved.as_context()}\n\n"
        f"QUESTION: {body.query}\n\n"
        f"Answer in {'English' if is_english else 'Marathi'}, using only the records above."
    )

    try:
        answer = await generate(
            prompt,
            SYSTEM_CITIZEN if user.role == "citizen" else SYSTEM_OFFICER,
            temperature=0.2,
        )
    except LLMUnavailable:
        # The records are still real, so answer from them rather than failing.
        return AssistantAnswer(
            answer=retrieval.plain_answer(retrieved, body.language),
            sources=sources,
            mode="retrieval_only",
        )

    return AssistantAnswer(answer=answer, sources=sources, mode="llm")


@router.post("/context", response_model=dict)
def inspect_context(
    body: AssistantQuery,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Show exactly what the assistant would retrieve for a question, without
    calling the model.

    Useful for a demo — it makes the retrieval step visible instead of leaving
    the answer looking like magic — and useful for debugging a wrong answer,
    since it separates 'retrieved the wrong records' from 'worded it badly'.
    """
    village_id = village_scope(user)
    if user.role == "citizen" and user.village_id:
        village_id = user.village_id

    retrieved = retrieval.gather(db, body.query, user, village_id)
    return {
        "topics": retrieved.topics,
        "factCount": len(retrieved.facts),
        "facts": retrieved.facts,
        "sources": [
            {"entityType": s.entity_type, "entityId": s.entity_id, "title": s.title}
            for s in retrieved.sources
        ],
        "aiEnabled": settings.ai_enabled,
    }
