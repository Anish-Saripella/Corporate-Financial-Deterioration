"""Secret-bearing runtime settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    """Credentials are optional for local tests and required only by network assets."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sec_user_agent: str | None = None
    fred_api_key: str | None = None

    def require_sec_user_agent(self) -> str:
        if not self.sec_user_agent or "@" not in self.sec_user_agent:
            raise ValueError("SEC_USER_AGENT must identify a real name and email address")
        return self.sec_user_agent

    def require_fred_api_key(self) -> str:
        if not self.fred_api_key or self.fred_api_key.startswith("replace-"):
            raise ValueError("FRED_API_KEY is required for FRED/ALFRED ingestion")
        return self.fred_api_key
