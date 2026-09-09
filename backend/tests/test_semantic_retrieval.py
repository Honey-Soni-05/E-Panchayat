"""Semantic retrieval and graph expansion.

These run without an API key. Real embeddings need a network call and a paid
quota, so the tests inject deterministic vectors instead: what is being checked
is the retrieval logic, the scoping and the graph walk, not whether Google's
embedding model works.

The scoping tests are the ones that matter. Similarity search is a new way to
reach records, and a new way to reach records is a new way to leak them.
"""

import asyncio
import math

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Citizen, Grievance, KnowledgeChunk, User
from app.services import graph
from app.services.indexer import build_drafts, reindex

API = "/api/v1"
HOME = "vil_loni_kalbhor"


# ── Building the index ───────────────────────────────────────────────────────

def test_every_non_personal_record_type_becomes_a_chunk():
    with SessionLocal() as db:
        drafts = build_drafts(db)
    kinds = {d.entity_type for d in drafts}
    assert {
        "village",
        "scheme",
        "grievance",
        "project",
        "facility",
    } <= kinds


def test_chunks_read_as_sentences_not_field_dumps():
    """The embedding has to match how a person phrases a question, so the
    content must be prose rather than 'name=X; ward=3'."""
    with SessionLocal() as db:
        drafts = build_drafts(db)
    grievances = [d for d in drafts if d.entity_type == "grievance"]
    assert grievances
    for d in grievances[:3]:
        assert len(d.content) > 60
        assert "=" not in d.content
        assert d.content.rstrip().endswith(".")


def test_reindexing_purges_resident_chunks_left_by_an_older_build():
    """The migration path. A deployment that ran the indexer before residents
    were excluded still has their embeddings in the table, and dropping them
    from `build_drafts` does not by itself remove what is already stored.
    Re-running the indexer must delete them — and must do so without an API
    key, since the deletion happens before anything is embedded."""
    stale_id = "kc_stale_resident_test"
    with SessionLocal() as db:
        db.add(
            KnowledgeChunk(
                id=stale_id,
                entity_type="citizen",
                entity_id="cit_stale_test",
                content="Someone Real is a 52-year-old resident with an income of Rs 48,000.",
                meta={"links": []},
                village_id=HOME,
                embedding=[0.1, 0.2, 0.3],
            )
        )
        db.commit()

        asyncio.run(reindex(db, force=False))

        assert db.get(KnowledgeChunk, stale_id) is None
        remaining = list(db.scalars(select(KnowledgeChunk).where(
            KnowledgeChunk.entity_type == "citizen"
        )))
        assert remaining == []

        # Leave the table as this test found it.
        for chunk in db.scalars(select(KnowledgeChunk)):
            db.delete(chunk)
        db.commit()


def test_chunk_ids_are_stable_across_rebuilds():
    """Re-indexing must update rows, not accumulate duplicates."""
    with SessionLocal() as db:
        first = {d.key: d.chunk_id for d in build_drafts(db)}
        second = {d.key: d.chunk_id for d in build_drafts(db)}
    assert first == second


def test_grievance_chunks_link_back_to_who_filed_them():
    """The links are what make expansion possible — without them this is
    ordinary vector search.

    Not every complaint has a filer: a walk-in is recorded against the office
    rather than a resident, and carries only its village link. Taking whichever
    grievance the database returned first made this test depend on row order,
    so it asks instead whether any complaint with a filer records who that is.
    """
    with SessionLocal() as db:
        drafts = build_drafts(db)
        linked = [
            d
            for d in drafts
            if d.entity_type == "grievance"
            and any(link["type"] == "citizen" for link in d.links)
        ]
    assert linked, "no grievance records who filed it"


def test_no_resident_record_is_ever_indexed():
    """Indexing means sending the text to Google to be embedded, and it runs
    over every row whether or not anyone asks a question. A resident in the
    index is a resident exported to a third party as a standing cost of the
    feature, so there must not be one."""
    with SessionLocal() as db:
        drafts = build_drafts(db)
    assert not [d for d in drafts if d.entity_type == "citizen"]


def test_no_chunk_from_any_table_quotes_a_resident_by_name():
    """The stronger version of the test above. Dropping the citizen table is not
    enough on its own — a name reaching the index through some other record,
    say a grievance rendered with its complainant, would be the same leak by a
    different route. Full names are compared, so a resident called Ganesh does
    not trip this on a facility named Ganesh Mandir."""
    with SessionLocal() as db:
        names = {c.name for c in db.scalars(select(Citizen)) if c.name}
        embedded = " ".join(d.content for d in build_drafts(db))

    leaked = sorted(n for n in names if n in embedded)
    assert not leaked, f"resident names in embedded text: {leaked}"


def test_schemes_belong_to_no_village_so_every_village_can_find_them():
    with SessionLocal() as db:
        drafts = build_drafts(db)
        schemes = [d for d in drafts if d.entity_type == "scheme"]
    assert schemes
    assert all(d.village_id is None for d in schemes)


# ── Cosine similarity ────────────────────────────────────────────────────────

def test_cosine_of_identical_vectors_is_one():
    v = [0.3, 0.4, 0.5]
    assert math.isclose(graph.cosine(v, v), 1.0, rel_tol=1e-9)


def test_cosine_of_orthogonal_vectors_is_zero():
    assert math.isclose(graph.cosine([1.0, 0.0], [0.0, 1.0]), 0.0, abs_tol=1e-9)


def test_cosine_survives_the_degenerate_cases():
    """A zero vector or a length mismatch must score zero, not raise and not
    divide by zero."""
    assert graph.cosine([], [1.0]) == 0.0
    assert graph.cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert graph.cosine([1.0, 2.0, 3.0], [1.0, 2.0]) == 0.0


# ── A fake index, so search can be tested without the network ───────────────

@pytest.fixture(scope="module")
def fake_index():
    """Give every chunk a one-hot vector keyed by entity type.

    Deterministic and inspectable: a query vector picking dimension 2 matches
    every grievance chunk exactly and nothing else.
    """
    dims = ["village", "citizen", "scheme", "grievance", "project", "facility", "sabha_meeting"]

    with SessionLocal() as db:
        asyncio.run(reindex(db, force=False))  # writes chunks; embeds nothing without a key
        chunks = list(db.scalars(select(KnowledgeChunk)))
        for chunk in chunks:
            vector = [0.0] * len(dims)
            if chunk.entity_type in dims:
                vector[dims.index(chunk.entity_type)] = 1.0
            chunk.embedding = vector
            chunk.embedding_model = "test-fake"
        db.commit()

    yield dims

    with SessionLocal() as db:
        for chunk in db.scalars(select(KnowledgeChunk)):
            db.delete(chunk)
        db.commit()


def _vector_for(dims: list[str], entity_type: str) -> list[float]:
    v = [0.0] * len(dims)
    v[dims.index(entity_type)] = 1.0
    return v


def _user(role: str) -> User:
    with SessionLocal() as db:
        stmt = select(User).where(User.role == role)
        if role == "officer":
            stmt = stmt.where(User.village_id == HOME)
        user = db.scalar(stmt)
        assert user is not None, f"no seeded {role}"
        db.expunge(user)
        return user


def test_the_index_reports_ready_once_something_is_embedded(fake_index):
    with SessionLocal() as db:
        assert graph.index_is_ready(db) is True


def test_search_finds_the_matching_entity_type(fake_index):
    officer = _user("officer")
    with SessionLocal() as db:
        hits = graph.semantic_search(
            db, _vector_for(fake_index, "project"), officer, HOME, expand=False
        )
    assert hits
    assert all(h.chunk.entity_type == "project" for h in hits)


def test_weak_matches_are_dropped_rather_than_returned(fake_index):
    """An orthogonal query scores zero against everything. Returning the
    least-bad row would hand the model irrelevant records and invite it to use
    them."""
    officer = _user("officer")
    with SessionLocal() as db:
        hits = graph.semantic_search(
            db, [0.0] * len(fake_index), officer, HOME, expand=False
        )
    assert hits == []


def test_expansion_pulls_in_the_place_a_matched_grievance_belongs_to(fake_index):
    """Expansion is what separates this from plain vector search: a matched
    complaint arrives with its context attached.

    That context used to include the resident who filed it. It no longer does,
    and deliberately — see `test_no_resident_record_is_ever_indexed`. The
    complaint still carries a 'filed by' link so the office can resolve it
    locally; what changed is that the link no longer leads to anything that was
    sent away to be embedded."""
    officer = _user("officer")
    with SessionLocal() as db:
        hits = graph.semantic_search(
            db, _vector_for(fake_index, "grievance"), officer, HOME, expand=True
        )
    kinds = {h.chunk.entity_type for h in hits}
    assert "grievance" in kinds
    assert "village" in kinds
    assert any(not h.matched_directly for h in hits)


def test_expansion_never_reaches_a_resident_record(fake_index):
    """A grievance links to whoever filed it. Walking that link must not produce
    a chunk, because no such chunk should exist to be walked to."""
    officer = _user("officer")
    with SessionLocal() as db:
        hits = graph.semantic_search(
            db, _vector_for(fake_index, "grievance"), officer, HOME, expand=True
        )
    assert not [h for h in hits if h.chunk.entity_type == "citizen"]


def test_an_expanded_record_says_why_it_is_there(fake_index):
    """The model must be able to tell a match from a neighbour, or it will
    answer about the neighbour."""
    officer = _user("officer")
    with SessionLocal() as db:
        hits = graph.semantic_search(
            db, _vector_for(fake_index, "grievance"), officer, HOME, expand=True
        )
        indirect = next(h for h in hits if not h.matched_directly)
        line = graph.describe(indirect)
    assert "included because" in line


# ── Scoping: the part that must not be wrong ────────────────────────────────

def test_an_officer_cannot_reach_another_villages_chunks(fake_index):
    officer = _user("officer")
    with SessionLocal() as db:
        visible = graph._visible_chunks(db, officer, HOME)
        for chunk in visible:
            assert chunk.village_id in (HOME, None)


def test_a_citizen_cannot_reach_another_residents_record(fake_index):
    """Similarity is a new route to a row. It must not be a route around the
    permission model."""
    citizen = _user("citizen")
    with SessionLocal() as db:
        hits = graph.semantic_search(
            db, _vector_for(fake_index, "citizen"), citizen, HOME, expand=True
        )
        for hit in hits:
            if hit.chunk.entity_type == "citizen":
                assert hit.chunk.entity_id == citizen.citizen_id


def test_a_citizen_cannot_reach_another_residents_grievance(fake_index):
    citizen = _user("citizen")
    with SessionLocal() as db:
        own = {
            g.id
            for g in db.scalars(
                select(Grievance).where(Grievance.citizen_id == citizen.citizen_id)
            )
        }
        hits = graph.semantic_search(
            db, _vector_for(fake_index, "grievance"), citizen, HOME, expand=True
        )
        for hit in hits:
            if hit.chunk.entity_type == "grievance":
                assert hit.chunk.entity_id in own


def test_expansion_cannot_smuggle_in_a_record_the_user_may_not_see(fake_index):
    """A citizen's own grievance links to their own record — fine. It must not
    become a way to walk into anyone else's."""
    citizen = _user("citizen")
    with SessionLocal() as db:
        hits = graph.semantic_search(
            db, _vector_for(fake_index, "grievance"), citizen, HOME, expand=True
        )
        others = {
            c.id
            for c in db.scalars(select(Citizen).where(Citizen.id != citizen.citizen_id))
        }
        for hit in hits:
            assert not (hit.chunk.entity_type == "citizen" and hit.chunk.entity_id in others)


def test_a_citizen_can_still_reach_public_village_facts(fake_index):
    """Scoping must not be so tight that the assistant stops being useful."""
    citizen = _user("citizen")
    with SessionLocal() as db:
        hits = graph.semantic_search(
            db, _vector_for(fake_index, "scheme"), citizen, HOME, expand=False
        )
    assert hits, "a citizen should be able to ask about government schemes"


def test_chunks_with_no_embedding_are_skipped_not_scored_as_perfect():
    """A null embedding must never be treated as distance zero — that would make
    every un-indexed row look maximally relevant."""
    officer = _user("officer")
    with SessionLocal() as db:
        db.add(
            KnowledgeChunk(
                id="kc_unindexed_test",
                entity_type="project",
                entity_id="proj_unindexed_test",
                content="A project that was never embedded.",
                meta={"links": []},
                village_id=HOME,
                embedding=None,
            )
        )
        db.commit()

        visible = graph._visible_chunks(db, officer, HOME)
        assert all(c.id != "kc_unindexed_test" for c in visible)

        db.delete(db.get(KnowledgeChunk, "kc_unindexed_test"))
        db.commit()


# ── Falling back ─────────────────────────────────────────────────────────────

def test_the_assistant_reports_keyword_mode_when_nothing_is_indexed(client, officer):
    """With no index the endpoint must still answer, and must say which path it
    used rather than implying a semantic search happened."""
    with SessionLocal() as db:
        saved = list(db.scalars(select(KnowledgeChunk)))
        for chunk in saved:
            chunk.embedding = None
        db.commit()

    resp = client.post(
        f"{API}/assistant/ask",
        headers=officer,
        json={"query": "How many grievances are pending?", "language": "en"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["retrieval"] == "keyword"
    assert body["answer"]


# ── Routing a question the way a villager actually phrases it ───────────────

def test_a_problem_described_in_plain_words_routes_to_grievances():
    """Nobody says "I wish to register a grievance". They say the tap is dry.

    This failed before: "ward" was a keyword for the resident directory, so a
    complaint was routed there — and that branch is officer-only, so a citizen
    asking got back nothing but the village's LGD code.
    """
    from app.services.retrieval import detect_topics

    for question in [
        "tap has been dry since diwali in ward 1. what to do",
        "street light not working near the temple",
        "the drain is clogged again",
        "no water supply for three days",
        "गटार तुंबले आहे",
        "नळाला पाणी येत नाही",
    ]:
        assert "grievances" in detect_topics(question), question


def test_ward_alone_no_longer_routes_to_the_resident_directory():
    from app.services.retrieval import detect_topics

    assert detect_topics("what is happening in ward 1") != ["citizens"]


def test_a_citizen_asking_about_a_problem_is_told_how_to_report_it(client, citizen):
    """The answer to "what do I do" is instructions, not a record count."""
    resp = client.post(
        f"{API}/assistant/ask",
        headers=citizen,
        json={"query": "the tap has been dry for three days, what to do", "language": "en"},
    )
    assert resp.status_code == 200, resp.text
    answer = resp.json()["answer"].lower()
    assert "grievance" in answer
    # It must say where to do it, not merely that grievances exist.
    assert "portal" in answer or "office" in answer


def test_a_citizen_is_told_they_only_see_their_own_complaints(client, citizen):
    """Otherwise an empty result reads as "nothing is wrong in the village"
    rather than "you are shown only your own"."""
    resp = client.post(
        f"{API}/assistant/ask",
        headers=citizen,
        json={"query": "any pending complaints about water?", "language": "en"},
    )
    body = resp.json()["answer"].lower()
    assert "their own" in body or "themselves" in body


# ── The privacy boundary: what may be sent to a model ───────────────────────
#
# The rule is that the model may see the village, never the villager. These
# tests check both halves, because either one failing makes the feature either
# unsafe or useless.


def test_a_residents_eligibility_facts_are_marked_personal():
    """An eligibility explanation states why the engine decided as it did, and
    those reasons are the resident's income, social category, BPL status and
    disability assessment."""
    from app.services.retrieval import gather

    citizen = _user("citizen")
    with SessionLocal() as db:
        retrieved = gather(db, "which schemes am I eligible for?", citizen, HOME)

    assert retrieved.facts
    assert retrieved.has_personal is True


def test_village_facts_are_not_marked_personal():
    """The other half of the rule. If everything were treated as personal the
    assistant would never call the model at all, which is not the design."""
    from app.services.retrieval import gather

    officer = _user("officer")
    with SessionLocal() as db:
        retrieved = gather(db, "how are the development projects going?", officer, HOME)

    assert retrieved.facts
    assert retrieved.has_personal is False


def test_a_personal_question_is_answered_without_calling_a_model(client, citizen):
    """The endpoint must report that it withheld the facts by choice, not that
    it was missing a key — those mean different things and only one of them
    would be fixed by configuring a key."""
    resp = client.post(
        f"{API}/assistant/ask",
        headers=citizen,
        json={"query": "am I eligible for a pension scheme?", "language": "en"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "retrieval_only_personal"
    # Still a real answer, not a refusal.
    assert body["answer"]


def test_the_resident_is_told_their_data_stayed_in_the_panchayat(client, citizen):
    """A privacy guarantee nobody is told about does not reassure anyone."""
    resp = client.post(
        f"{API}/assistant/ask",
        headers=citizen,
        json={"query": "which schemes do I qualify for?", "language": "en"},
    )
    answer = resp.json()["answer"].lower()
    assert "never sent outside" in answer or "rule engine" in answer


def test_an_officer_still_gets_the_village_count_not_the_filing_advice(client, officer):
    """The guidance is for residents. An officer asking about grievances wants
    the queue."""
    resp = client.post(
        f"{API}/assistant/ask",
        headers=officer,
        json={"query": "how many water complaints are unresolved?", "language": "en"},
    )
    answer = resp.json()["answer"].lower()
    assert "unresolved grievances" in answer
