"""Test fixtures.

Every test runs against a throwaway SQLite file seeded from the same
`seed_data.json` the demo uses, so the suite exercises real data rather than
hand-built stubs. The environment is set before `app` is imported, because
settings are read at import time.
"""

import os
import tempfile
from pathlib import Path

import pytest

_TMP_DB = Path(tempfile.gettempdir()) / "epanchayat_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["SECRET_KEY"] = "test-only-key"
os.environ["GEMINI_API_KEY"] = ""
os.environ["SEED_DEFAULT_PASSWORD"] = "Test@12345"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app import seed as seeder  # noqa: E402

API = "/api/v1"
PASSWORD = "Test@12345"


@pytest.fixture(scope="session", autouse=True)
def database():
    _TMP_DB.unlink(missing_ok=True)
    Base.metadata.create_all(engine)

    data = seeder.load_data()
    with SessionLocal() as db:
        seeder.seed_hierarchy(db)
        seeder.seed_villages(db)
        seeder.seed_families(db, data)
        seeder.seed_citizens(db, data)
        seeder.seed_schemes(db, data)
        seeder.seed_grievances(db, data)
        seeder.seed_grievance_history(db)
        seeder.seed_projects(db, data)
        seeder.seed_documents(db, data)
        seeder.seed_sabha(db, data)
        seeder.seed_facilities(db, data)
        seeder.assign_home_village(db)
        seeder.seed_users(db)
        seeder.seed_neighbour_officer(db)

    yield

    Base.metadata.drop_all(engine)
    # Windows will not delete a file while a handle is open, and SQLite holds
    # one until the connection pool is disposed.
    engine.dispose()
    try:
        _TMP_DB.unlink(missing_ok=True)
    except PermissionError:
        # A leftover temp file is harmless — the next run recreates it.
        pass


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


def _auth(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


@pytest.fixture(scope="session")
def officer(client: TestClient) -> dict[str, str]:
    return _auth(client, "officer@panchayat.gov.in")


@pytest.fixture(scope="session")
def neighbour_officer(client: TestClient) -> dict[str, str]:
    """An officer of Theur, a different Gram Panchayat in the same block."""
    return _auth(client, "officer.theur@panchayat.gov.in")


@pytest.fixture(scope="session")
def admin(client: TestClient) -> dict[str, str]:
    """No village — sees the whole district."""
    return _auth(client, "admin@panchayat.gov.in")


@pytest.fixture(scope="session")
def citizen(client: TestClient) -> dict[str, str]:
    """Savita Patil — cit_102."""
    return _auth(client, "savita@citizen.panchayat.gov.in")
