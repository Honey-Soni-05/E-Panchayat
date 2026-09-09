"""Application settings, loaded from environment / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    PROJECT_NAME: str = "E-Panchayat AI"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str

    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI
    GEMINI_API_KEY: str = ""
    # gemini-2.5-flash was here until it started returning 404 "no longer
    # available to new users". Note that the models list endpoint still
    # advertises it — only a real generateContent call reveals the retirement,
    # which is why `llm._api_error` spells the fix out in the error text.
    #
    # Measured on a free key with a realistic prompt (a system instruction plus
    # a dozen retrieved facts), three calls each:
    #
    #   gemini-3.7-flash      3/3 ok, 3-4s     <- this
    #   gemini-3.6-flash      3/3 ok, 27-42s
    #   gemini-3.8-flash      0/3, all 503
    #   gemini-flash-latest   0/3, all 503
    #
    # Two things that reads are worth keeping in mind. The alias is not the
    # safe option: it resolves to whatever is newest, which is exactly what is
    # saturated. And a two-word probe is not a test — every one of these
    # answered "reply with ok" happily while shedding real requests, because
    # size is what gets dropped under load.
    GEMINI_MODEL: str = "gemini-3.7-flash"
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"

    # ── Sign-in throttling ──────────────────────────────────────────────────
    #
    # Two limits over the same window, because they stop different attacks.
    # The per-email limit stops one account being ground through a password
    # list. The per-IP limit stops one source spraying a common password across
    # many accounts, which the per-email limit never sees.
    #
    # The per-email limit means someone who knows an officer's address can lock
    # it for the window by failing five sign-ins. That is a real cost and it is
    # the accepted trade: the alternative is leaving an unmetered password
    # oracle open. Keeping the window short is what makes it bearable, and a
    # deployment that cares would add a CAPTCHA or an out-of-band unlock rather
    # than raise these numbers.
    LOGIN_WINDOW_MINUTES: int = 15
    LOGIN_MAX_FAILURES_PER_EMAIL: int = 5
    LOGIN_MAX_FAILURES_PER_IP: int = 20
    # Applications are cheap to file and land in an officer's queue, so this
    # caps how much noise one source can put there.
    REGISTER_MAX_PER_IP_PER_HOUR: int = 5

    # A reset code is handed over at the Panchayat counter, so it has to outlive
    # the walk home — but a code that never expires is a spare key to the
    # account left lying in the officer's browser history.
    PASSWORD_RESET_TTL_HOURS: int = 24
    # Redeeming is a guessing oracle like signing in, so it is metered the same
    # way, keyed on the account the code belongs to.
    RESET_MAX_FAILURES_PER_EMAIL: int = 5

    # CORS — comma separated in the environment
    CORS_ORIGINS: str = "http://localhost:5173"

    # Seeding
    SEED_DEFAULT_PASSWORD: str = "Panchayat@2026"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        """The server, not the browser, decides whether the LLM is available."""
        return bool(self.GEMINI_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
