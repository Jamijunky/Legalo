from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    database_url: str = ""
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    procedural_stale_days: int = 365
    retrieve_k: int = 6

    @property
    def data_dir(self) -> Path:
        return ROOT / "data"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
