from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        extra="ignore",
    )

    llm_provider: str = "fallback"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    cors_origins: List[str] = ["http://localhost:3000"]
    data_dir: Path = BACKEND_DIR / "data"
    llm_timeout: float = 30.0
    llm_retries: int = 2

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("data_dir", mode="after")
    @classmethod
    def resolve_data_dir(cls, value: Path) -> Path:
        if not value.is_absolute():
            return (BACKEND_DIR / value).resolve()
        return value

    @property
    def db_path(self) -> Path:
        return self.data_dir / "bridgecf.db"

    @property
    def index_path(self) -> Path:
        return self.data_dir / "vector_database.index"

    @property
    def native_engine_path(self) -> Path:
        return BACKEND_DIR / "engine.so"


@lru_cache
def get_settings() -> Settings:
    return Settings()
