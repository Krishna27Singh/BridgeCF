from functools import lru_cache
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pragma: no cover - compatibility for older installs
    from pydantic import BaseSettings

    SettingsConfigDict = None


APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent


if "SettingsConfigDict" in globals() and SettingsConfigDict is not None:
    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")

        llm_provider: str = "fallback"
        llm_base_url: str = "http://127.0.0.1:11434"
        llm_model: str = "llama3"
        llm_api_key: str = ""
        ollama_base_url: str = ""
        ollama_model: str = ""
        gemini_api_key: str = ""
        gemini_model: str = "gemini-1.5-flash"
        openai_api_key: str = ""
        openai_base_url: str = "https://api.openai.com/v1"
        openai_model: str = "gpt-4o-mini"
        llm_timeout: float = 30.0
        llm_retries: int = 2
        db_path: Path = BACKEND_DIR / "data" / "bridgecf.db"
        index_path: Path = BACKEND_DIR / "data" / "vector_database.index"
        native_engine_path: Path = BACKEND_DIR / "engine.so"
else:
    class Settings(BaseSettings):
        llm_provider: str = "fallback"
        llm_base_url: str = "http://127.0.0.1:11434"
        llm_model: str = "llama3"
        llm_api_key: str = ""
        ollama_base_url: str = ""
        ollama_model: str = ""
        gemini_api_key: str = ""
        gemini_model: str = "gemini-1.5-flash"
        openai_api_key: str = ""
        openai_base_url: str = "https://api.openai.com/v1"
        openai_model: str = "gpt-4o-mini"
        llm_timeout: float = 30.0
        llm_retries: int = 2
        db_path: Path = BACKEND_DIR / "data" / "bridgecf.db"
        index_path: Path = BACKEND_DIR / "data" / "vector_database.index"
        native_engine_path: Path = BACKEND_DIR / "engine.so"

        class Config:
            env_file = ".env"
            extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
