"""Checks on the seed data itself, independent of any database.

These exist because of a bug that reached the user's Postgres: a scheme's
`benefit` text was 269 characters against a VARCHAR(255) column. The test suite
did not catch it, because **SQLite silently ignores VARCHAR length limits**
while PostgreSQL enforces them — so the same data that passed here failed there.

Rather than switch the whole suite to Postgres, these tests read the column
definitions out of the SQLAlchemy models and measure the seed data against
them directly. That catches the problem on any database, including none.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import String

from app import models

SEED = json.loads(
    (Path(models.__file__).parent / "seed_data.json").read_text(encoding="utf-8")
)
VILLAGES = json.loads(
    (Path(models.__file__).parent / "villages_data.json").read_text(encoding="utf-8")
)


def varchar_limits(model) -> dict[str, int]:
    """Every VARCHAR column on a model, with its maximum length."""
    return {
        column.name: column.type.length
        for column in model.__table__.columns
        if isinstance(column.type, String) and column.type.length
    }


def overflows(rows: list[dict], model, key_field: str = "id") -> list[str]:
    limits = varchar_limits(model)
    problems = []
    for row in rows:
        for field, limit in limits.items():
            value = row.get(field)
            if isinstance(value, str) and len(value) > limit:
                problems.append(
                    f"{row.get(key_field, '?')}.{field} is {len(value)} characters, "
                    f"limit is {limit}"
                )
    return problems


def test_every_seeded_scheme_fits_its_columns():
    assert not overflows(SEED["schemes"], models.Scheme)


def test_every_seeded_citizen_fits_its_columns():
    # The seed file uses camelCase keys from the original mock data, so map the
    # handful of string fields the model constrains.
    rows = [
        {
            "id": c["id"],
            "name": c["name"],
            "name_mr": c["nameMr"],
            "gender": c["gender"],
            "gender_mr": c["genderMr"],
            "occupation": c["occupation"],
            "occupation_mr": c["occupationMr"],
            "phone": c.get("phone"),
            "social_category": c.get("social_category"),
            "ration_card_type": c.get("ration_card_type"),
            "marital_status": c.get("marital_status"),
        }
        for c in SEED["citizens"]
    ]
    assert not overflows(rows, models.Citizen)


def test_every_seeded_village_fits_its_columns():
    rows = [
        {"id": v["name"], "name": v["name"], "name_mr": v.get("name_mr") or v["name"]}
        for v in VILLAGES
    ]
    assert not overflows(rows, models.Village)


# ── Data quality ────────────────────────────────────────────────────────────

def test_every_scheme_has_a_source_url():
    """Provenance is the reason for using real data at all."""
    missing = [s["id"] for s in SEED["schemes"] if not s.get("source_url")]
    assert not missing


def test_every_scheme_is_bilingual():
    for scheme in SEED["schemes"]:
        for field in ("name", "benefit", "description"):
            assert scheme.get(field), f"{scheme['id']} has no {field}"
            assert scheme.get(f"{field}_mr"), f"{scheme['id']} has no {field}_mr"


def test_scheme_ids_are_unique():
    ids = [s["id"] for s in SEED["schemes"]]
    assert len(ids) == len(set(ids))


def test_criteria_use_only_keys_the_engine_understands():
    """A typo in a criteria key would silently make a rule do nothing —
    the engine ignores what it does not recognise."""
    known = {
        "min_age", "max_age", "min_income", "max_income", "gender",
        "marital_status_any", "ward_in", "occupation_any", "occupation_none",
        "is_head", "category_any", "requires_bpl", "requires_secc_listed",
        "ration_card_any", "min_land_hectares", "max_land_hectares",
        "min_disability_percent", "any_of", "manual_review",
    }

    def check(criteria: dict, scheme_id: str) -> list[str]:
        bad = [k for k in criteria if k not in known]
        for branch in criteria.get("any_of", []):
            bad += check(branch, scheme_id)
        return [f"{scheme_id}: unknown criteria key '{k}'" for k in bad]

    problems: list[str] = []
    for scheme in SEED["schemes"]:
        problems += check(scheme.get("criteria") or {}, scheme["id"])
    assert not problems


@pytest.mark.parametrize("village", VILLAGES, ids=lambda v: v["name"])
def test_village_codes_are_plausible(village):
    """LGD village codes are six-digit integers. A string, a float or a
    four-digit number means something went wrong in the import."""
    code = village.get("lgd_code")
    if code is not None:
        assert isinstance(code, int)
        assert 100000 <= code <= 999999
