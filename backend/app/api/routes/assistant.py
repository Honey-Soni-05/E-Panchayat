"""The Panchayat assistant.

Answers questions from the database, in English or Marathi, within whatever the
asker is allowed to see.

The shape is retrieve-then-generate: fetch the relevant records, hand them to
the language model as the only permitted source, and return the answer with the
records it drew on. The model is instructed not to use anything else, and the
sources are returned so a claim can be checked against the row it came from.

If no model key is configured, the endpoint answers from the same retrieved
facts in a plainer form rather than pretending — see `retrieval.plain_answer`.

One rule overrides the shape above: **the model may see the village, never the
villager.** Questions about the Panchayat — its projects, budgets, schemes,
meetings, grievance queue — are answered by the model as normal. Questions that
turn on one resident's own record are answered from the records directly, with
no external call, because the facts involved are their income, their social
category, their disability assessment and their documents. Those are not sent
to a third party to be phrased more nicely.
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

    # Semantic first; this falls back to keyword routing on its own if the
    # index is not built or the embedding call fails.
    retrieved = await retrieval.gather_semantic(db, body.query, user, village_id)
    sources = [
        RetrievedSource(entity_type=s.entity_type, entity_id=s.entity_id, title=s.title)
        for s in retrieved.sources
    ]

    # The privacy boundary. Everything above this line ran inside our own
    # database; everything below it is a request to Google. Facts describing one
    # identified resident — their income, social category, BPL status,
    # disability assessment, the documents in their file — do not cross it, and
    # neither does the question that asked for them.
    #
    # Nothing is withheld from the user: they get the same facts, assembled from
    # a template instead of a sentence. The decision those facts explain was
    # made by the rule engine, which never involved a model, so the only thing
    # lost is phrasing.
    #
    # This is a hard rule rather than a setting, because the alternative is
    # trusting a provider's terms about retention and training. On the free tier
    # those terms permit using submitted content to improve their products, and
    # a resident cannot consent to that on behalf of a welfare application.
    #
    # Checked before the key check below, because "we do not send this" is the
    # real reason such an answer is never model-written. Reporting a missing key
    # instead would imply that configuring one would change the outcome.
    if retrieved.has_personal:
        return AssistantAnswer(
            answer=retrieval.plain_answer(retrieved, body.language),
            sources=sources,
            mode="retrieval_only_personal",
            retrieval=retrieved.mode,
        )

    if not settings.ai_enabled:
        return AssistantAnswer(
            answer=retrieval.plain_answer(retrieved, body.language),
            sources=sources,
            mode="retrieval_only",
            retrieval=retrieved.mode,
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
        #
        # Reported as 'unavailable', not 'retrieval_only'. They look the same to
        # a reader and mean opposite things: one is a server with no key
        # configured, the other is a key that works and an upstream that just
        # refused. Collapsing them cost real time here — a retired model name
        # was returning 404 while the UI insisted no key was configured.
        return AssistantAnswer(
            answer=retrieval.plain_answer(retrieved, body.language, reason="unavailable"),
            sources=sources,
            mode="unavailable",
            retrieval=retrieved.mode,
        )

    return AssistantAnswer(
        answer=answer, sources=sources, mode="llm", retrieval=retrieved.mode
    )


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
