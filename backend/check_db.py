"""Test the DATABASE_URL in .env without changing anything.

    python check_db.py

Connects, runs a harmless SELECT, and reports what it found. Nothing is
created, altered or dropped, so a wrong password costs you nothing but the
error message. The password is never printed.
"""

import re
import sys

try:
    from sqlalchemy import text

    from app.core.config import settings
    from app.db.session import engine
except ModuleNotFoundError as exc:
    sys.exit(
        f"Missing dependency: {exc.name}\n"
        "Activate the virtual environment first:\n"
        "    .venv\\Scripts\\activate\n"
        "    pip install -r requirements.txt"
    )
except Exception as exc:  # settings failed to load
    sys.exit(f"Could not read .env — {exc}")


def masked_url() -> str:
    """Show the connection string with the password replaced by asterisks."""
    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:********@", settings.DATABASE_URL)


def diagnose(message: str) -> str:
    m = message.lower()
    if "password authentication failed" in m or "invalid password" in m:
        return (
            "The password is wrong.\n"
            "  → Reset it in Supabase, or ask whoever created the project.\n"
            "  → If your password contains @ : / ? # [ ] or %, it must be\n"
            "    percent-encoded in the URL (@ becomes %40, # becomes %23)."
        )
    if "could not translate host name" in m or "name or service not known" in m:
        return (
            "The host name is wrong.\n"
            "  → Copy it again from Supabase → Connect → Session pooler."
        )
    if "timeout" in m or "timed out" in m or "connection refused" in m:
        return (
            "Reached the network but got no answer.\n"
            "  → Check you used the Session pooler (port 5432), not Direct connection.\n"
            "  → A college or office firewall may be blocking outbound 5432."
        )
    if "tenant or user not found" in m:
        return (
            "The username is wrong or incomplete.\n"
            "  → It must be postgres.<projectref>, not plain 'postgres'."
        )
    if "can't load plugin" in m or "dialect" in m:
        return (
            "The driver prefix is wrong.\n"
            "  → The URL must start with postgresql+psycopg:// not postgresql://"
        )
    if "ssl" in m:
        return "SSL problem.\n  → Make sure the URL ends with ?sslmode=require"
    return "→ Read the message above; it usually names the exact problem."


def main() -> None:
    print(f"Connecting to: {masked_url()}\n")

    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar() or ""
            database = conn.execute(text("SELECT current_database()")).scalar()
            tables = conn.execute(text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )).scalar()
    except Exception as exc:
        print("FAILED\n")
        print(f"{type(exc).__name__}: {exc}\n")
        print(diagnose(str(exc)))
        sys.exit(1)

    print("CONNECTED")
    print(f"  Server:   {version.split(',')[0]}")
    print(f"  Database: {database}")
    print(f"  Tables in public schema: {tables}")

    if tables:
        print("\n  Note: this database already has tables — probably from the old")
        print("  supabase_schema.sql. Tell Claude before running the migration.")
    else:
        print("\n  Empty and ready. Next: alembic upgrade head")


if __name__ == "__main__":
    main()
